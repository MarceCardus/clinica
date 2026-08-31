from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy.orm import Session

from app.api.deps import authenticate, get_db
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterResponse, Token
from app.schemas.user import UserCreate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> RegisterResponse:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email ya registrado")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        dob=payload.dob,
        password_hash=get_password_hash(payload.password),
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    return RegisterResponse(message="Usuario creado", created_at=datetime.utcnow())


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    user = authenticate(db, email=payload.email, password=payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta deshabilitada")
    access_token = create_access_token(str(user.id), extra={"role": user.role.value})
    refresh_token = create_access_token(
        str(user.id),
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
        extra={"role": user.role.value, "type": "refresh"},
    )
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    try:
        decoded = jwt.decode(payload.refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido") from exc
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token incorrecto")
    user_id = decoded["sub"]
    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    access_token = create_access_token(str(user.id), extra={"role": user.role.value})
    refresh_token = create_access_token(
        str(user.id),
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
        extra={"role": user.role.value, "type": "refresh"},
    )
    return Token(access_token=access_token, refresh_token=refresh_token)
