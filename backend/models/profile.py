from typing import Optional

from pydantic import BaseModel, Field, field_validator


GENDER_OPTIONS = ("Female", "Male", "Non-Binary", "Prefer not to say")


class ProfileUpdate(BaseModel):
    gender: str
    city: Optional[str] = None
    country: Optional[str] = None
    about_me: Optional[str] = None
    tag_preferences: list[str] = Field(default_factory=list)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        if value not in GENDER_OPTIONS:
            print(value)
            raise ValueError("Please choose a valid gender option.")
        return value

    @field_validator("city", "country")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("about_me")
    @classmethod
    def clean_about_me(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("About me must be 500 characters or fewer.")
        return value or None

    @field_validator("tag_preferences")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            tag = str(tag).strip()
            if tag and tag not in cleaned:
                cleaned.append(tag)
        return cleaned