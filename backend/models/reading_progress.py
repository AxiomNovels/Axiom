# backend/models/reading_progress.py

from pydantic import BaseModel, Field


class ReadingProgressUpdate(BaseModel):
    current_chapter: int = Field(ge=1, le=1_000_000)