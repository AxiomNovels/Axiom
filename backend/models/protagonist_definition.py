"""Validated inputs for the versioned protagonist definition editor."""
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


RESERVED_KEYS = {"id", "novel_id", "protagonist_name", "scores_locked", "created_at", "updated_at"}


class TraitDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,47}$")
    name: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=12000)

    @field_validator("key")
    @classmethod
    def safe_key(cls, value):
        if value in RESERVED_KEYS or value.startswith("pg_"):
            raise ValueError("This trait key is reserved.")
        return value


class DefinitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: StrictInt = Field(ge=1)
    instructions: str = Field(min_length=1, max_length=20000)
    traits: list[TraitDefinition] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_traits(self):
        if len({trait.key for trait in self.traits}) != len(self.traits):
            raise ValueError("Trait keys must be unique.")
        if len({trait.name.casefold() for trait in self.traits}) != len(self.traits):
            raise ValueError("Trait names must be unique.")
        return self
