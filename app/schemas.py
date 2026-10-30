from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.core.security import MAX_PASSWORD_BYTES

# Unknown names raise ZoneInfoNotFoundError; empty or path-like ones raise ValueError.
ZONEINFO_ERRORS = (ZoneInfoNotFoundError, ValueError)


class PaginatedResponse[T](BaseModel):
    items: list[T]
    limit: int
    offset: int
    has_more: bool


class UserPublic(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPrivate(UserPublic):
    email: EmailStr
    timezone: str


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, timezone: str):
        try:
            ZoneInfo(timezone)
        except ZONEINFO_ERRORS:
            raise ValueError(f"Unknown time zone: {timezone!r}") from None
        return timezone

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str):
        if len(password.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        has_upper = has_digit = has_lower = False
        for char in password:
            has_upper |= char.isupper()
            has_lower |= char.islower()
            has_digit |= char.isdigit()

        if not has_upper:
            raise ValueError("Password must contain at least one uppercase letter")
        if not has_digit:
            raise ValueError("Password must contain at least one digit")
        if not has_lower:
            raise ValueError("Password must contain at least one lowercase letter")
        return password

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class Token(BaseModel):
    access_token: str
    token_type: str
