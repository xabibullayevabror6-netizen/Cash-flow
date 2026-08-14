# Cash Flow Boshqaruv Tizimi — Texnik Hujjat

**Versiya:** 1.0
**Sana:** 2026-08-10
**Loyiha turi:** Bank operatsiyalari asosida Cash Flow, Dashboard va Forecast tizimi

---

## 1. Loyihaning maqsadi va qamrovi

### 1.1 Muammo
CFO va moliya menejerlari kundalik ishida quyidagi savollarga tez javob topa olmaydi:
- Pul qayerdan keldi, qayerga ketdi?
- Qaysi xarajat toifasi oshib ketmoqda?
- Oy oxirigacha pul yetadimi?

### 1.2 Yechim (MVP qamrovi)
1C dan eksport qilingan bank operatsiyalari (Excel) tizimga yuklanadi → avtomatik kategoriyalanadi → Cash Flow dashboard va 13 haftalik forecast sifatida ko'rsatiladi.

### 1.3 MVP chegaralari (nima kirmaydi)
- P&L, Balance, Debitor/Kreditor, Ombor — keyingi bosqichlar
- Avtomatik bank integratsiyasi (API) — MVP faqat Excel import
- Real vaqtli sinxronizatsiya

---

## 2. Manba ma'lumot tuzilishi (1C Excel export)

Haqiqiy namunaviy fayl asosida aniqlangan tuzilma:

| Ustun | Turi | Tavsif | Muammo/Eslatma |
|---|---|---|---|
| N | int | Qator raqami | — |
| Вид движения | string | `Списание` / `Поступление` | Direction aniqlash manbai |
| Кор. счет | int | Kontragent turi kodi (4310, 6310, 9430, va h.k.) | **Vaqt o'tishi bilan o'zgaruvchan** — faqat referens sifatida ishlatiladi, qattiq klassifikator emas |
| Аналитика | string | Kontragent nomi (erkin matn, ko'p tilli) | Asosiy kategoriyalash kaliti |
| Приход | float / NaN | Kirim summasi | Har bir qatorda faqat bittasi to'ldirilgan |
| Расход | float / NaN | Chiqim summasi | Import paytida `amount` + `direction`ga normallashtiriladi |
| Детали платежа | string | To'lov tavsifi (uzun, erkin matn, o'zbek/rus/lotin aralash) | AI kategoriyalash uchun asosiy manba |

**Kritik cheklov:** faylda operatsiya sanasi yo'q. Sana faqat matn ichida tartibsiz shaklda uchraydi (hujjat/shartnoma sanasi, operatsiya sanasi emas). **Yechim:** foydalanuvchi import paytida davr sanasini qo'lda kiritadi, tizim uni butun faylga (yoki tanlangan qatorlar guruhiga) biriktiradi.

---

## 3. Texnologik stack

| Qatlam | Texnologiya | Asoslash |
|---|---|---|
| Backend | Python + FastAPI | Excel/pandas bilan tabiiy ishlaydi, AI chaqiruvlar uchun qulay |
| Frontend | React + Tailwind + Recharts | Dashboard va grafiklar uchun standart |
| Baza | PostgreSQL | Tranzaksion, moliyaviy ma'lumot uchun ishonchli |
| Excel parsing | pandas + openpyxl | — |
| AI kategoriyalash | Claude API (Sonnet) | Ko'p tilli erkin matnni tushunish qobiliyati |
| Auth | JWT + bcrypt | Standart, oddiy |
| Deploy (MVP) | Railway / Render / VPS | Tez ishga tushirish, keyin scale |
| Background jobs | Celery + Redis (yoki APScheduler, MVP uchun yetarli) | Forecast va AI kategoriyalash navbatlari uchun |

---

## 4. Ma'lumotlar bazasi sxemasi

### 4.1 companies
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| name | varchar | |
| tariff_plan | enum(start, pro, enterprise) | |
| created_at | timestamp | |

### 4.2 users
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK → companies | |
| email | varchar unique | |
| password_hash | varchar | |
| role | enum(admin, accountant, viewer) | |

### 4.3 bank_accounts
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK | |
| bank_name | varchar | |
| account_number | varchar | |
| currency | varchar(3) | default UZS |

### 4.4 branches
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK | |
| name | varchar | Masalan "Yunusobod" |
| code | varchar | |

### 4.5 import_batches
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK | |
| bank_account_id | FK | |
| file_name | varchar | |
| period_date | date | **Foydalanuvchi qo'lda kiritadi** — import paytidagi majburiy maydon |
| uploaded_by | FK → users | |
| uploaded_at | timestamp | |
| row_count | int | |
| status | enum(processing, completed, failed) | |

### 4.6 categories
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK (nullable — global default kategoriyalar uchun) | |
| name | varchar | Masalan "Dori xaridi", "Ish haqi" |
| type | enum(income, expense) | |
| parent_category_id | FK self (nullable) | Kategoriya guruhlash uchun |

### 4.7 transactions (markaziy jadval)
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK | |
| import_batch_id | FK | |
| bank_account_id | FK | |
| date | date | `import_batches.period_date`dan meros |
| direction | enum(in, out) | `Вид движения`dan aniqlanadi |
| amount | numeric(18,2) | `Приход`/`Расход`dan normallashtirilgan |
| counterparty | varchar | `Аналитика` |
| corr_account_code | varchar | `Кор. счет` — **faqat referens, kategoriyalash uchun qattiq qoida emas** |
| raw_description | text | `Детали платежа` |
| branch_id | FK (nullable) | Agar tavsifda filial kodi topilsa |
| category_id | FK → categories (nullable, qoralama import paytida bo'sh) | |
| category_source | enum(rule, ai, manual) | Kategoriya qanday belgilanganini kuzatish uchun |
| confidence_score | float (nullable) | AI ishonch darajasi (0–1) |
| review_status | enum(pending_review, confirmed) | Past ishonchli AI natijalar buxgalter tasdig'ini kutadi |
| created_at | timestamp | |

### 4.8 category_rules
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK | |
| counterparty_pattern | varchar | `Аналитика` nomiga bog'lanadi (kodga emas — 2-bo'limdagi qarorga ko'ra) |
| category_id | FK | |
| match_count | int | Necha marta ishlatilgan (statistika, ishonch uchun) |
| last_used_at | timestamp | |

### 4.9 forecasts
| Ustun | Turi | Izoh |
|---|---|---|
| id | UUID PK | |
| company_id | FK | |
| forecast_week_start | date | 13 haftalik forecast uchun |
| predicted_cash_in | numeric | |
| predicted_cash_out | numeric | |
| predicted_balance | numeric | |
| actual_balance | numeric (nullable) | Plan/Fakt taqqoslash uchun keyin to'ldiriladi |
| model_version | varchar | |
| generated_at | timestamp | |

---

## 5. Asosiy jarayon oqimlari (workflows)

### 5.1 Import jarayoni
```
1. Foydalanuvchi bank hisobini tanlaydi (yoki yangisini yaratadi)
2. Excel faylni yuklaydi
3. Tizim davr sanasini so'raydi (majburiy maydon)
4. Backend faylni pandas bilan o'qiydi:
   a. Ustunlarni normallashtiradi (Приход/Расход → amount + direction)
   b. Har bir qatorni import_batch_id bilan bog'laydi
   c. date = period_date barcha qatorlarga
5. transactions jadvaliga review_status=pending_review bilan yoziladi
6. Kategoriyalash navbatiga qo'yiladi (5.2-bosqich)
```

### 5.2 Kategoriyalash jarayoni (ikki bosqichli)
```
Har bir yangi tranzaksiya uchun:

BOSQICH 1 — Rule-based (tez, arzon, aniq):
  category_rules jadvalidan counterparty nomi bo'yicha qidiriladi
  Agar mos kelsa → category_id belgilanadi, category_source=rule,
                    review_status=confirmed (yuqori ishonch)

BOSQICH 2 — AI fallback (agar rule topilmasa):
  Claude API'ga yuboriladi:
    - counterparty (Аналитика)
    - raw_description (Детали платежа)
    - corr_account_code (qo'shimcha kontekst sifatida, qoida emas)
    - mavjud kategoriyalar ro'yxati (company uchun)
  AI qaytaradi: category + confidence_score

  Agar confidence >= 0.85:
    category_id belgilanadi, review_status=confirmed
    → shu counterparty uchun category_rules ga YANGI qoida qo'shiladi
      (keyingi safar bosqich 1 da tez topiladi — o'z-o'zini o'rgatuvchi tizim)

  Agar confidence < 0.85:
    category_id belgilanadi (taklif sifatida), review_status=pending_review
    → buxgalter UI'da tasdiqlash/o'zgartirish oynasida ko'radi
```

**Muhim qoida:** Kor. счет kodi hech qachon yagona asos sifatida ishlatilmaydi, chunki u vaqt o'tishi bilan o'zgarishi mumkin (2-bo'limdagi tasdiqlangan qaror). U faqat AI promptiga qo'shimcha signal sifatida beriladi.

### 5.3 Dashboard hisoblash
```
Cash In (davr bo'yicha) = SUM(amount) WHERE direction='in'
Cash Out (davr bo'yicha) = SUM(amount) WHERE direction='out'
Net Cash Flow = Cash In - Cash Out
Oy boshi qoldig'i, Oy oxiri qoldig'i = kumulyativ hisob

Kategoriya kesimida guruhlash: GROUP BY category_id
Filial kesimida guruhlash: GROUP BY branch_id (agar mavjud bo'lsa)
Kontragent reytingi: GROUP BY counterparty ORDER BY SUM(amount) DESC LIMIT 20
```

### 5.4 Forecast jarayoni (background job, oyiga/haftaga bir marta)
```
1. Oxirgi 12 oy transactions olinadi
2. Kategoriya bo'yicha guruhlanadi (masalan Payroll har oy taxminan bir xil)
3. Oddiy modelь (MVP): moving average + oxirgi 3 oy trendi
4. Har bir kategoriya uchun keyingi 13 hafta prognozlanadi
5. forecasts jadvaliga yoziladi
6. Agar predicted_balance < 0 (yoki belgilangan minimal chegaradan past) →
   ogohlantirish yaratiladi (dashboard'da va/yoki email orqali)
```

---

## 6. KPI formulalar

| KPI | Formula |
|---|---|
| Operating Cash Flow | Cash In − Operating Cash Out |
| Burn Rate | O'rtacha oylik xarajat (oxirgi 3 oy) |
| Runway | Joriy Cash / Burn Rate |
| Cash Ratio | Cash / Current Liabilities |
| Payroll Share | Payroll xarajati / Revenue |
| Rent Share | Ijara xarajati / Revenue |
| Top-20 kontragent | Xarajat/tushum bo'yicha reytinglangan ro'yxat |

---

## 7. API endpoint tuzilishi (asosiy)

```
POST   /api/auth/login
POST   /api/auth/register

GET    /api/bank-accounts
POST   /api/bank-accounts

POST   /api/imports                    # Excel yuklash + period_date
GET    /api/imports/{id}/status

GET    /api/transactions               # filter: date range, category, branch, review_status
PATCH  /api/transactions/{id}          # kategoriya qo'lda tuzatish (buxgalter tasdig'i)
POST   /api/transactions/{id}/confirm

GET    /api/categories
POST   /api/categories
GET    /api/category-rules

GET    /api/dashboard/summary          # Cash In/Out, Net CF, KPI
GET    /api/dashboard/by-category
GET    /api/dashboard/by-branch
GET    /api/dashboard/top-counterparties

GET    /api/forecast                   # 13 haftalik prognoz
GET    /api/forecast/plan-vs-actual
```

---

## 8. Xavfsizlik va ma'lumot yaxlitligi

- Har bir so'rov `company_id` bo'yicha izolyatsiya qilinadi (multi-tenant, row-level filtering)
- Moliyaviy ma'lumotlar — audit log majburiy (`transactions` jadvaliga har qanday `category_id` o'zgarishi tarixi saqlanadi, alohida `audit_log` jadvali keyingi bosqichda)
- Excel import — fayl hajmi va format validatsiyasi (xato holatda aniq xabar, qisman import yo'q qilinmaydi)
- AI API chaqiruvlarida moliyaviy summalar yuborilmaydi (faqat matn kontekst — counterparty, description), maxfiylik uchun

---

## 9. Rivojlanish bosqichlari va vaqt taxmini

| Bosqich | Ish | Muddat |
|---|---|---|
| 1 | Baza sxemasi + auth + bank_accounts | 1 hafta |
| 2 | Excel import (davr sanasi bilan) + normalizatsiya | 1 hafta |
| 3 | Rule-based kategoriyalash + tasdiqlash UI | 1 hafta |
| 4 | AI kategoriyalash integratsiyasi (Claude API) | 1 hafta |
| 5 | Dashboard (Cash In/Out, KPI, kategoriya/filial kesimi) | 1.5 hafta |
| 6 | Top-20 kontragent + Plan/Fakt hisobot | 0.5 hafta |
| 7 | Forecast (13 hafta, moving average modeli) | 1.5 hafta |
| 8 | Multi-company, tariflar, billing (SaaS uchun) | 1.5 hafta |

**Jami MVP:** ~8–9 hafta, bitta full-stack dasturchi bilan.

---

## 10. Ochiq savollar (keyingi bosqichda aniqlashtirish kerak)

1. Bitta import faylida bir nechta kun bo'lishi mumkinmi, yoki har doim bitta kunga tegishlimi? (Hozircha: bitta `period_date` butun faylga qo'llanadi)
2. Filial kodini tavsifdan avtomatik ajratib olish qoidalari qanday bo'ladi? (Namunaviy faylda aniq filial belgisi ko'rinmadi — buxgalter bilan aniqlashtirish kerak)
3. Bir nechta bank hisobi bo'lsa, ular orasida transfer (bank1→bank2) qanday aniqlanadi — takroriy hisoblanmasligi kerak
4. Tariflar narxi va to'lov integratsiyasi (Click, Payme va h.k.) — Enterprise bosqichida
