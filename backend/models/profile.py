from typing import Optional

from pydantic import BaseModel, Field, field_validator


GENDER_OPTIONS = ("♀️Female", "♂️Male", "⚧️Non-Binary", "Prefer not to say")

# Every social field defaults to "friends_only" -- a reader opts a
# platform in to "everyone" visibility individually, not the reverse.
SOCIAL_VISIBILITY_OPTIONS = ("everyone", "friends_only")
SOCIAL_PLATFORMS = ("discord", "instagram", "reddit", "tiktok")


class ProfileUpdate(BaseModel):
    gender: str
    city: Optional[str] = None
    country: Optional[str] = None
    about_me: Optional[str] = None
    tag_preferences: list[str] = Field(default_factory=list)

    discord_username: Optional[str] = None
    discord_visibility: str = "friends_only"
    instagram_username: Optional[str] = None
    instagram_visibility: str = "friends_only"
    reddit_username: Optional[str] = None
    reddit_visibility: str = "friends_only"
    tiktok_username: Optional[str] = None
    tiktok_visibility: str = "friends_only"

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        if value not in GENDER_OPTIONS:
            raise ValueError("Please choose a valid gender option.")
        return value

    @field_validator(
        "city",
        "country",
        "discord_username",
        "instagram_username",
        "reddit_username",
        "tiktok_username",
    )
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

    @field_validator(
        "discord_visibility",
        "instagram_visibility",
        "reddit_visibility",
        "tiktok_visibility",
    )
    @classmethod
    def validate_social_visibility(cls, value: str) -> str:
        if value not in SOCIAL_VISIBILITY_OPTIONS:
            raise ValueError("Please choose a valid visibility option.")
        return value


class AvatarUpdate(BaseModel):
    image_data: str

    @field_validator("image_data")
    @classmethod
    def validate_image_data(cls, value: str) -> str:
        if not value.startswith("data:image/"):
            raise ValueError("Avatar image data is invalid.")
        return value