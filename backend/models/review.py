from pydantic import BaseModel, Field, field_validator


class ReviewUpsert(BaseModel):
    rating: float = Field(ge=0.5, le=5)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("rating")
    @classmethod
    def validate_half_star_rating(cls, value: float) -> float:
        if value * 2 != int(value * 2):
            raise ValueError("Rating must use half-star increments.")
        return value
