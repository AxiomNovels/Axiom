import re

from pydantic import BaseModel, EmailStr, Field, field_validator


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")


class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.match(value):
            raise ValueError(
                "Username must be 3-20 characters long and contain only "
                "letters, numbers, and underscores."
            )
        return value


class LoginRequest(BaseModel):
    identifier: str
    password: str


class RefreshSessionRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    refresh_token: str = Field(min_length=1)
