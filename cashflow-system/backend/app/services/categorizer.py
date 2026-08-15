"""
Ikki bosqichli kategoriyalash:
  1. Rule-based — category_rules jadvalidan counterparty nomi bo'yicha (tez, arzon)
  2. AI fallback — Claude API orqali, Кор. счет faqat qo'shimcha kontekst sifatida
     (qattiq qoida sifatida ISHLATILMAYDI, chunki kodlar vaqt o'tishi bilan o'zgaradi)

Yuqori ishonchli AI natijasi keyingi safar tezroq topilishi uchun
avtomatik ravishda yangi qoida sifatida category_rules ga yoziladi.
"""
import json
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from anthropic import Anthropic

from app.config import settings
from app.services.chart_of_accounts import lookup as lookup_account
from app.services.provodka_categories import category_for
from app import models

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def find_rule_match(db: Session, company_id: str, counterparty: str) -> Optional[models.CategoryRule]:
    """Aniq mos kelish (keyinchalik fuzzy/normalizatsiya qo'shsa bo'ladi)."""
    return (
        db.query(models.CategoryRule)
        .filter(
            models.CategoryRule.company_id == company_id,
            models.CategoryRule.counterparty_pattern == counterparty.strip(),
        )
        .first()
    )


def categorize_with_ai(
    counterparty: str,
    raw_description: str,
    corr_account_code: Optional[str],
    direction: str,
    available_categories: list[str],
) -> Tuple[str, float, str]:
    """
    Claude API orqali kategoriya, ishonch darajasi va kategoriya turini qaytaradi.
    Returns: (category_name, confidence_score, category_type)
    """
    categories_str = ", ".join(available_categories)

    account_name = lookup_account(corr_account_code)
    if account_name:
        account_context = f"{corr_account_code} — {account_name}"
    else:
        account_context = corr_account_code or "yo'q"

    prompt = f"""Sen moliyaviy tranzaksiyalarni kategoriyalovchi yordamchisan.
Quyidagi bank operatsiyasini eng mos kategoriyaga ajrat va uning turini (asosiy faoliyat daromadimi yoki xarajatimi) aniqla.

Kontragent: {counterparty}
To'lov tavsifi: {raw_description}
Pul yo'nalishi: {"kirim (pul kelgan)" if direction == "in" else "chiqim (pul ketgan)"}
Buxgalteriya provodkasi — Kor. счет (qo'shimcha kontekst, qat'iy qoida emas — kod vaqt o'tishi bilan o'zgarishi mumkin): {account_context}

Mavjud kategoriyalar: {categories_str}

Agar hech biri mos kelmasa, "Boshqa" deb belgila va yangi nom taklif qil.
"type" maydonida operatsiya "income" (asosiy faoliyatdan tushum) yoki "expense" (xarajat) ekanini bergan
provodka va pul yo'nalishidan kelib chiqib belgila (masalan kredit qaytarilishi kabi asosiy faoliyatga
aloqasi bo'lmagan kirimlarni ham "income" dan farqlab, kontekstga qarab eng mosini tanla).

Faqat JSON qaytar, boshqa hech narsa yozma:
{{"category": "...", "confidence": 0.0-1.0 oralig'ida raqam, "type": "income" yoki "expense"}}"""

    fallback_type = "income" if direction == "in" else "expense"

    if not settings.ai_enabled:
        return "Boshqa", 0.0, fallback_type

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return "Boshqa", 0.0, fallback_type

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(text)
        category_type = parsed.get("type") if parsed.get("type") in ("income", "expense") else fallback_type
        return parsed["category"], float(parsed["confidence"]), category_type
    except (json.JSONDecodeError, KeyError, ValueError):
        return "Boshqa", 0.3, fallback_type


def categorize_transaction(
    db: Session,
    company_id: str,
    counterparty: str,
    raw_description: str,
    corr_account_code: Optional[str],
    direction: str,
) -> dict:
    """
    Kategoriyalash uch bosqichda, arzondan qimmatga qarab:

      1. Kontragent qoidasi — avval tasdiqlangan bilim, eng ishonchli
      2. Provodka (Кор. счет) — buxgalteriya fakti, bepul va darhol
      3. AI — faqat yuqoridagilar hal qila olmagan holatlar uchun

    Returns dict: {category_id, category_source, confidence_score, review_status}
    """
    # BOSQICH 1 — kontragent bo'yicha o'rganilgan qoida
    rule = find_rule_match(db, company_id, counterparty)
    if rule:
        rule.match_count += 1
        rule.last_used_at = datetime.utcnow()
        db.commit()
        return {
            "category_id": rule.category_id,
            "category_source": models.CategorySource.rule,
            "confidence_score": 1.0,
            "review_status": models.ReviewStatus.confirmed,
        }

    categories = db.query(models.Category).filter(
        (models.Category.company_id == company_id) | (models.Category.company_id.is_(None))
    ).all()
    category_names = [c.name for c in categories]

    # BOSQICH 2 — provodka bo'yicha
    provodka_match = category_for(corr_account_code, direction)
    if provodka_match:
        name, confidence = provodka_match
        category = next((c for c in categories if c.name == name), None)
        if category is not None:
            confirmed = confidence >= settings.ai_confidence_threshold
            return {
                "category_id": category.id,
                "category_source": models.CategorySource.provodka,
                "confidence_score": confidence,
                # Ishonch past bo'lsa kategoriya baribir qo'yiladi, lekin
                # buxgalter tasdig'iga yuboriladi — kod yo'nalishni ko'rsatadi,
                # tafsilotni emas.
                "review_status": (
                    models.ReviewStatus.confirmed if confirmed
                    else models.ReviewStatus.pending_review
                ),
            }

    # BOSQICH 3 — AI

    category_name, confidence, category_type = categorize_with_ai(
        counterparty, raw_description, corr_account_code, direction, category_names
    )

    category = next((c for c in categories if c.name == category_name), None)
    if category is None:
        # yangi kategoriya avtomatik yaratiladi — turi provodka/pul yo'nalishidan AI tomonidan aniqlanadi
        category = models.Category(
            company_id=company_id,
            name=category_name,
            type=models.CategoryType.income if category_type == "income" else models.CategoryType.expense,
        )
        db.add(category)
        db.commit()
        db.refresh(category)

    is_confident = confidence >= settings.ai_confidence_threshold

    if is_confident:
        # Yangi qoida sifatida saqlanadi — keyingi safar bosqich 1 da tez topiladi
        new_rule = models.CategoryRule(
            company_id=company_id,
            counterparty_pattern=counterparty.strip(),
            category_id=category.id,
            match_count=1,
        )
        db.add(new_rule)
        db.commit()

    return {
        "category_id": category.id,
        "category_source": models.CategorySource.ai,
        "confidence_score": confidence,
        "review_status": models.ReviewStatus.confirmed if is_confident else models.ReviewStatus.pending_review,
    }
