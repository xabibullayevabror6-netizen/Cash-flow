from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.i18n import translator
from app import security

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # Reverse proxy ortida haqiqiy IP shu sarlavhada keladi
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=schemas.TokenResponse)
def register(request: Request, payload: schemas.UserRegister, db: Session = Depends(get_db)):
    _ = translator(request)
    ip = _client_ip(request)

    remaining = security.check_registration_limit(ip)
    if remaining:
        raise HTTPException(
            status_code=429,
            detail=_("auth.too_many_registrations", minutes=max(1, remaining // 60)),
            headers={"Retry-After": str(remaining)},
        )

    password_error = security.validate_password(payload.password)
    if password_error:
        raise HTTPException(
            status_code=400,
            detail=_(password_error, min=security.MIN_PASSWORD_LENGTH),
        )

    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail=_("auth.email_taken"))

    # Kompaniya va foydalanuvchi BITTA tranzaksiyada yaratiladi.
    # Ilgari kompaniya alohida commit qilinardi: foydalanuvchi yaratish xato bersa
    # (masalan email bandligi poygasi yoki parol xeshlash xatosi), bazada egasiz
    # kompaniya qolib ketardi.
    company = models.Company(name=payload.company_name)
    db.add(company)
    db.flush()          # company.id oladi, lekin hali commit qilmaydi

    user = models.User(
        company_id=company.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=models.UserRole.admin,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        # Bir vaqtda kelgan ikkinchi so'rov — bazadagi unique indeks ushlab qoldi.
        # rollback kompaniyani ham bekor qiladi, yetim yozuv qolmaydi.
        db.rollback()
        raise HTTPException(status_code=400, detail=_("auth.email_taken"))

    db.refresh(user)
    security.register_registration(ip)
    return schemas.TokenResponse(access_token=create_access_token(user))


@router.post("/login", response_model=schemas.TokenResponse)
def login(request: Request, payload: schemas.UserLogin, db: Session = Depends(get_db)):
    _ = translator(request)
    ip = _client_ip(request)

    remaining = security.check_lockout(payload.email, ip)
    if remaining:
        raise HTTPException(
            status_code=429,
            detail=_("auth.too_many_attempts", minutes=max(1, remaining // 60)),
            headers={"Retry-After": str(remaining)},
        )

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        security.register_failure(payload.email, ip)
        raise HTTPException(status_code=401, detail=_("auth.bad_credentials"))

    security.register_success(payload.email, ip)
    return schemas.TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=schemas.MeOut)
def me(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    company = db.query(models.Company).filter(models.Company.id == user.company_id).first()
    return schemas.MeOut(
        id=user.id,
        email=user.email,
        role=user.role.value if user.role else "accountant",
        company_name=company.name if company else "",
    )


@router.post("/change-password", response_model=schemas.TokenResponse)
def change_password(
    request: Request,
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """
    Parolni almashtiradi va BARCHA eski tokenlarni bekor qiladi.

    Token versiyasi oshirilgani uchun boshqa qurilmalardagi ochiq seanslar
    ham darhol uziladi — parol o'g'irlangan deb hisoblanadigan holatda
    aynan shu kerak. Chaqiruvchiga yangi token qaytariladi.
    """
    _ = translator(request)

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail=_("auth.wrong_current_password"))

    password_error = security.validate_password(payload.new_password)
    if password_error:
        raise HTTPException(
            status_code=400,
            detail=_(password_error, min=security.MIN_PASSWORD_LENGTH),
        )

    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail=_("auth.password_unchanged"))

    user.password_hash = hash_password(payload.new_password)
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)

    return schemas.TokenResponse(access_token=create_access_token(user))
