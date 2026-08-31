import re

from pydantic import BaseModel, EmailStr, field_validator


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