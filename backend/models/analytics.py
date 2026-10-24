import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, StrictInt, field_validator


class BrowserEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    session_id: UUID
    event: Literal["page_view", "heartbeat"]
    path: str = Field(max_length=240)
    active_seconds: StrictInt = Field(default=0, ge=0, le=30)

    @field_validator("path")
    @classmethod
    def page_path(cls, value):
        if not re.fullmatch(r"/(?:[a-zA-Z0-9_-]+(?:\.html)?/?)?", value):
            raise ValueError("Use a page path without query parameters.")
        return value


class EdgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(max_length=240)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    ip: IPvAnyAddress | None = None
    kind: Literal["page", "asset", "other"]
    status: StrictInt = Field(ge=100, le=599)
