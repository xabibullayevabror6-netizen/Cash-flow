"""
Autentifikatsiya himoyasi: parol talablari va login urinishlarini cheklash.

Cheklash xotirada saqlanadi — bu bitta jarayon uchun yetarli. Bir necha
nusxada ishlatilsa, hisoblagichni Redis'ga ko'chirish kerak (har nusxa o'z
hisobini yuritsa, chegara nusxalar soniga ko'payib ketadi).
"""
import time
import threading
from typing import Dict, Tuple

# --- Parol talablari ---
MIN_PASSWORD_LENGTH = 10

# Eng ko'p uchraydigan parollar — uzunligi yetsa ham qabul qilinmaydi
COMMON_PASSWORDS = {
    "password", "parol123456", "1234567890", "qwertyuiop", "password123",
    "12345678901", "111111111111", "adminadmin", "letmein123",
}


def validate_password(password: str) -> str | None:
    """
    Parol talablarga javob bermasa — xato kaliti, javob bersa — None.

    Talablar ataylab sodda: uzunlik asosiy himoya, murakkablik qoidalari
    (belgi turlari) foydalanuvchini oson taxmin qilinadigan naqshlarga
    ("Parol1!") itaradi va real himoyani deyarli oshirmaydi.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return "auth.password_too_short"
    if password.lower() in COMMON_PASSWORDS:
        return "auth.password_too_common"
    if len(set(password)) < 4:
        return "auth.password_too_simple"
    return None


# --- Login urinishlarini cheklash ---
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300      # 5 daqiqa ichida
LOCKOUT_SECONDS = 900     # keyin 15 daqiqa kutish

_lock = threading.Lock()
_attempts: Dict[str, Tuple[int, float]] = {}   # kalit -> (urinishlar, birinchi urinish vaqti)
_locked_until: Dict[str, float] = {}


def _key(email: str, ip: str) -> str:
    return f"{email.lower()}|{ip}"


def check_lockout(email: str, ip: str) -> int:
    """Bloklangan bo'lsa qolgan soniyalarni, aks holda 0 ni qaytaradi."""
    key = _key(email, ip)
    now = time.time()
    with _lock:
        until = _locked_until.get(key)
        if until and until > now:
            return int(until - now)
        if until:
            # Blok muddati tugadi — tozalaymiz
            _locked_until.pop(key, None)
            _attempts.pop(key, None)
    return 0


def register_failure(email: str, ip: str) -> None:
    key = _key(email, ip)
    now = time.time()
    with _lock:
        count, first = _attempts.get(key, (0, now))
        if now - first > WINDOW_SECONDS:
            count, first = 0, now      # oyna tugadi — noldan boshlanadi
        count += 1
        _attempts[key] = (count, first)
        if count >= MAX_ATTEMPTS:
            _locked_until[key] = now + LOCKOUT_SECONDS


def register_success(email: str, ip: str) -> None:
    key = _key(email, ip)
    with _lock:
        _attempts.pop(key, None)
        _locked_until.pop(key, None)


def reset_all() -> None:
    """Testlar uchun."""
    with _lock:
        _attempts.clear()
        _locked_until.clear()
        _registrations.clear()


# --- Ro'yxatdan o'tishni cheklash ---
# Bitta IP dan cheksiz akkaunt ochib, bazani to'ldirib yuborishning oldini oladi.
MAX_REGISTRATIONS = 3
REGISTRATION_WINDOW = 3600      # 1 soat ichida

_registrations: Dict[str, list] = {}


def check_registration_limit(ip: str) -> int:
    """Chegara oshib ketgan bo'lsa qolgan soniyalarni, aks holda 0 ni qaytaradi."""
    now = time.time()
    with _lock:
        stamps = [t for t in _registrations.get(ip, []) if now - t < REGISTRATION_WINDOW]
        _registrations[ip] = stamps
        if len(stamps) >= MAX_REGISTRATIONS:
            return int(REGISTRATION_WINDOW - (now - stamps[0]))
    return 0


def register_registration(ip: str) -> None:
    with _lock:
        _registrations.setdefault(ip, []).append(time.time())
