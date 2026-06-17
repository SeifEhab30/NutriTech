from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    TokenResponse,
    UserPublic
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ==============================
# Register
# ==============================
@router.post("/register", response_model=UserPublic)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        nationality=(data.nationality or "").lower().strip() or None
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ==============================
# Login (OAuth2 compatible)
# ==============================
@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Swagger يبعث username = email
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token(subject=user.email)

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ==============================
# Current user (used by the frontend to know premium status)
# ==============================
@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ==============================
# Subscribe / unsubscribe (mock — no real payment)
# ==============================
@router.post("/subscribe", response_model=UserPublic)
def subscribe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.is_premium = True
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/unsubscribe", response_model=UserPublic)
def unsubscribe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.is_premium = False
    db.commit()
    db.refresh(current_user)
    return current_user