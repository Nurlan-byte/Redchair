from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


class PaginatedResponse[T](BaseModel):
    items: list[T]
    limit: int
    offset: int
    has_more: bool


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserOut(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str):
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
