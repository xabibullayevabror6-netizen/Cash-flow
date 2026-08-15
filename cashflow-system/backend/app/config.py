import warnings

from pydantic_settings import BaseSettings

# Repoda tarqatilgan namunaviy qiymatlar. Bular bilan ishga tushirish xavfli:
# JWT kaliti ma'lum bo'lsa, istalgan odam istalgan kompaniya nomidan token yasaydi.
INSECURE_SECRETS = {
    "change-this-to-a-random-secret-key-in-production",
    "secret",
    "changeme",
    "",
}


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    anthropic_api_key: str = ""
    ai_confidence_threshold: float = 0.85
    # Vergul bilan bir nechta manzil berish mumkin:
    #   FRONTEND_ORIGIN=http://localhost:5173,http://192.168.1.5:5173
    frontend_origin: str = "http://localhost:5173"

    # Development'da lokal tarmoqdagi boshqa kompyuterlardan kirishga ruxsat.
    # Production'da ALBATTA false bo'lishi kerak — u holda faqat
    # frontend_origin ro'yxatidagi aniq manzillar qabul qilinadi.
    cors_allow_lan: bool = True

    # "production" bo'lsa, xavfsizlik talablari qat'iy tekshiriladi
    environment: str = "development"

    class Config:
        env_file = ".env"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in ("production", "prod")

    @property
    def cors_origins(self) -> list:
        """FRONTEND_ORIGIN dagi vergul bilan ajratilgan manzillar ro'yxati."""
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def cors_origin_regex(self):
        """
        Lokal tarmoq manzillari (192.168.x.x, 10.x.x.x, 172.16-31.x.x) uchun shablon.
        Faqat cors_allow_lan yoqilgan va production bo'lmaganda ishlaydi.
        """
        if not self.cors_allow_lan or self.is_production:
            return None
        return (
            r"^https?://("
            r"localhost|127\.0\.0\.1|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?$"
        )

    @property
    def ai_enabled(self) -> bool:
        """AI kategoriyalash haqiqatan sozlanganmi (placeholder kalit hisobga olinmaydi)."""
        key = self.anthropic_api_key.strip()
        return bool(key) and not key.startswith("sk-ant-xxx")


settings = Settings()


def _validate() -> None:
    if settings.jwt_secret_key.strip() in INSECURE_SECRETS or len(settings.jwt_secret_key) < 32:
        message = (
            "JWT_SECRET_KEY xavfsiz emas (namunaviy yoki juda qisqa). "
            "Yangi kalit yarating: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
        if settings.is_production:
            raise RuntimeError(message)
        warnings.warn(f"XAVFSIZLIK OGOHLANTIRISHI: {message}", stacklevel=2)

    if settings.is_production and "*" in settings.frontend_origin:
        raise RuntimeError("Ishlab chiqarishda FRONTEND_ORIGIN aniq manzil bo'lishi kerak, '*' emas.")

    if not settings.ai_enabled:
        warnings.warn(
            "ANTHROPIC_API_KEY sozlanmagan — AI kategoriyalash o'chirilgan, "
            "barcha operatsiyalar qo'lda tasdiqlashga tushadi.",
            stacklevel=2,
        )


_validate()
