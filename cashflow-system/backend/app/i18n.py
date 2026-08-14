"""
Backend xabarlarini tarjima qilish.

Foydalanuvchiga ko'rinadigan xato matnlari (HTTPException detail) shu yerda
saqlanadi va Accept-Language sarlavhasi bo'yicha tanlanadi. Interfeys tilini
almashtirganda xato xabari o'zbekchada qolib ketmasligi uchun kerak.

Qo'llash:
    from app.i18n import translator
    ...
    _ = translator(request)
    raise HTTPException(404, detail=_("import.not_found"))
"""
from typing import Callable, Optional

from fastapi import Request

DEFAULT_LANG = "uz"
SUPPORTED = ("uz", "uz-Cyrl", "ru", "en")

MESSAGES = {
    "uz": {
        "auth.unauthorized": "Avtorizatsiya muvaffaqiyatsiz",
        "auth.email_taken": "Bu email allaqachon ro'yxatdan o'tgan",
        "auth.bad_credentials": "Email yoki parol noto'g'ri",
        "auth.password_too_short": "Parol kamida {min} belgidan iborat bo'lishi kerak",
        "auth.password_too_common": "Bu parol juda ko'p ishlatiladi — boshqasini tanlang",
        "auth.password_too_simple": "Parol juda oddiy — turli belgilardan foydalaning",
        "auth.too_many_attempts": "Juda ko'p muvaffaqiyatsiz urinish. {minutes} daqiqadan so'ng qayta urinib ko'ring.",
        "auth.wrong_current_password": "Joriy parol noto'g'ri",
        "auth.password_unchanged": "Yangi parol eskisidan farq qilishi kerak",
        "auth.too_many_registrations": "Juda ko'p ro'yxatdan o'tish urinishi. {minutes} daqiqadan so'ng qayta urinib ko'ring.",
        "bank_account.not_found": "Bank hisobi topilmadi",
        "import.not_found": "Import topilmadi",
        "import.duplicate": "«{bank} — {account}» hisobiga {date} sanasi uchun fayl allaqachon yuklangan ({file}). Cheklov faqat shu hisob raqamiga tegishli — boshqa hisob raqamga bu sana uchun yuklashingiz mumkin.",
        "import.duplicate_short": "«{bank} — {account}» hisobiga {date} sanasi uchun fayl allaqachon yuklangan. Boshqa hisob raqamga bu sana uchun yuklashingiz mumkin.",
        "import.processing_failed": "Importni qayta ishlashda xato yuz berdi",
        "transaction.not_found": "Tranzaksiya topilmadi",
        "category.not_found": "Kategoriya topilmadi",
        "category.name_required": "Kategoriya nomini kiriting",
        "category.duplicate": "«{name}» nomli kategoriya allaqachon mavjud",
        "category.in_use": "Bu kategoriya {count} ta operatsiyada ishlatilmoqda — avval ularni boshqa kategoriyaga o'tkazing",
        "excel.unreadable": "Faylni o'qib bo'lmadi: {error}",
        "excel.missing_columns": "Faylda quyidagi ustunlar topilmadi: {columns}. 1C eksport formatini tekshiring.",
        "excel.no_rows": "Faylda haqiqiy operatsiya qatorlari topilmadi.",
    },
    "uz-Cyrl": {
        "auth.unauthorized": "Авторизация муваффақиятсиз",
        "auth.email_taken": "Бу email аллақачон рўйхатдан ўтган",
        "auth.bad_credentials": "Email ёки парол нотўғри",
        "auth.password_too_short": "Парол камида {min} белгидан иборат бўлиши керак",
        "auth.password_too_common": "Бу парол жуда кўп ишлатилади — бошқасини танланг",
        "auth.password_too_simple": "Парол жуда оддий — турли белгилардан фойдаланинг",
        "auth.too_many_attempts": "Жуда кўп муваффақиятсиз уриниш. {minutes} дақиқадан сўнг қайта уриниб кўринг.",
        "auth.wrong_current_password": "Жорий парол нотўғри",
        "auth.password_unchanged": "Янги парол эскисидан фарқ қилиши керак",
        "auth.too_many_registrations": "Жуда кўп рўйхатдан ўтиш уриниши. {minutes} дақиқадан сўнг қайта уриниб кўринг.",
        "bank_account.not_found": "Банк ҳисоби топилмади",
        "import.not_found": "Импорт топилмади",
        "import.duplicate": "«{bank} — {account}» ҳисобига {date} санаси учун файл аллақачон юкланган ({file}). Чеклов фақат шу ҳисоб рақамига тегишли — бошқа ҳисоб рақамга бу сана учун юклашингиз мумкин.",
        "import.duplicate_short": "«{bank} — {account}» ҳисобига {date} санаси учун файл аллақачон юкланган. Бошқа ҳисоб рақамга бу сана учун юклашингиз мумкин.",
        "import.processing_failed": "Импортни қайта ишлашда хато юз берди",
        "transaction.not_found": "Транзакция топилмади",
        "category.not_found": "Категория топилмади",
        "category.name_required": "Категория номини киритинг",
        "category.duplicate": "«{name}» номли категория аллақачон мавжуд",
        "category.in_use": "Бу категория {count} та операцияда ишлатилмоқда — аввал уларни бошқа категорияга ўтказинг",
        "excel.unreadable": "Файлни ўқиб бўлмади: {error}",
        "excel.missing_columns": "Файлда қуйидаги устунлар топилмади: {columns}. 1C экспорт форматини текширинг.",
        "excel.no_rows": "Файлда ҳақиқий операция қаторлари топилмади.",
    },
    "ru": {
        "auth.unauthorized": "Авторизация не пройдена",
        "auth.email_taken": "Этот email уже зарегистрирован",
        "auth.bad_credentials": "Неверный email или пароль",
        "auth.password_too_short": "Пароль должен содержать минимум {min} символов",
        "auth.password_too_common": "Этот пароль слишком распространён — выберите другой",
        "auth.password_too_simple": "Пароль слишком простой — используйте разные символы",
        "auth.too_many_attempts": "Слишком много неудачных попыток. Повторите через {minutes} мин.",
        "auth.wrong_current_password": "Текущий пароль неверен",
        "auth.password_unchanged": "Новый пароль должен отличаться от старого",
        "auth.too_many_registrations": "Слишком много попыток регистрации. Повторите через {minutes} мин.",
        "bank_account.not_found": "Банковский счёт не найден",
        "import.not_found": "Импорт не найден",
        "import.duplicate": "Для счёта «{bank} — {account}» файл за {date} уже загружен ({file}). Ограничение действует только для этого счёта — на другой счёт за эту дату загрузить можно.",
        "import.duplicate_short": "Для счёта «{bank} — {account}» файл за {date} уже загружен. На другой счёт за эту дату загрузить можно.",
        "import.processing_failed": "Произошла ошибка при обработке импорта",
        "transaction.not_found": "Транзакция не найдена",
        "category.not_found": "Категория не найдена",
        "category.name_required": "Укажите название категории",
        "category.duplicate": "Категория «{name}» уже существует",
        "category.in_use": "Категория используется в {count} операциях — сначала перенесите их в другую категорию",
        "excel.unreadable": "Не удалось прочитать файл: {error}",
        "excel.missing_columns": "В файле не найдены столбцы: {columns}. Проверьте формат выгрузки из 1С.",
        "excel.no_rows": "В файле не найдено ни одной реальной операции.",
    },
    "en": {
        "auth.unauthorized": "Authorisation failed",
        "auth.email_taken": "This email is already registered",
        "auth.bad_credentials": "Incorrect email or password",
        "auth.password_too_short": "Password must be at least {min} characters",
        "auth.password_too_common": "This password is too common — choose another",
        "auth.password_too_simple": "Password is too simple — use a wider range of characters",
        "auth.too_many_attempts": "Too many failed attempts. Try again in {minutes} min.",
        "auth.wrong_current_password": "Current password is incorrect",
        "auth.password_unchanged": "The new password must differ from the old one",
        "auth.too_many_registrations": "Too many registration attempts. Try again in {minutes} min.",
        "bank_account.not_found": "Bank account not found",
        "import.not_found": "Import not found",
        "import.duplicate": "A file for {date} has already been uploaded to «{bank} — {account}» ({file}). The limit applies to this account only — you can still upload this date to a different account.",
        "import.duplicate_short": "A file for {date} has already been uploaded to «{bank} — {account}». You can still upload this date to a different account.",
        "import.processing_failed": "An error occurred while processing the import",
        "transaction.not_found": "Transaction not found",
        "category.not_found": "Category not found",
        "category.name_required": "Enter a category name",
        "category.duplicate": "A category named «{name}» already exists",
        "category.in_use": "This category is used by {count} transactions — move them to another category first",
        "excel.unreadable": "Could not read the file: {error}",
        "excel.missing_columns": "These columns were not found in the file: {columns}. Check the 1C export format.",
        "excel.no_rows": "No actual transaction rows were found in the file.",
    },
}


def resolve_lang(accept_language: Optional[str]) -> str:
    """
    Accept-Language sarlavhasidan tilni aniqlaydi.
    Frontend aniq kod yuboradi (masalan "uz-Cyrl"), brauzer esa
    "ru-RU,ru;q=0.9" ko'rinishida yuborishi mumkin.
    """
    if not accept_language:
        return DEFAULT_LANG

    for part in accept_language.split(","):
        code = part.split(";")[0].strip()
        if not code:
            continue
        # Aniq moslik (katta-kichik harfga sezgir emas)
        for supported in SUPPORTED:
            if code.lower() == supported.lower():
                return supported
        # Faqat til qismi bo'yicha: "ru-RU" -> "ru"
        base = code.split("-")[0].lower()
        if base == "ru":
            return "ru"
        if base == "en":
            return "en"
        if base == "uz":
            return "uz"
    return DEFAULT_LANG


def translate(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    table = MESSAGES.get(lang) or MESSAGES[DEFAULT_LANG]
    text = table.get(key) or MESSAGES[DEFAULT_LANG].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def translator(request: Optional[Request]) -> Callable[..., str]:
    """So'rov tiliga bog'langan tarjima funksiyasini qaytaradi."""
    header = request.headers.get("accept-language") if request else None
    lang = resolve_lang(header)

    def _(key: str, **kwargs) -> str:
        return translate(key, lang, **kwargs)

    return _
