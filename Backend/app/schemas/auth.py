import re

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal, Optional


# Complexity rules: 8-72 chars (bcrypt cap), at least one each of
# lowercase, uppercase, digit, and symbol.
_PWD_RULES = [
    (re.compile(r"[a-z]"), "one lowercase letter"),
    (re.compile(r"[A-Z]"), "one uppercase letter"),
    (re.compile(r"\d"), "one digit"),
    (re.compile(r"[^A-Za-z0-9]"), "one symbol"),
]


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    nationality: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        missing = [label for rx, label in _PWD_RULES if not rx.search(v)]
        if missing:
            raise ValueError("Password must contain at least " + ", ".join(missing) + ".")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserPublic(BaseModel):
    id: int
    name: str
    email: EmailStr
    nationality: Optional[str] = None
    is_premium: bool = False

    class Config:
        from_attributes = True
