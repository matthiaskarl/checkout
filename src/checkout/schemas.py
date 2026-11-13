"""Pydantic schemas: the shape of data going in and out of the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    # Both optional (PATCH: send only what changes), so the defaults are None. But only
    # `description` may be set to null; the `name` column is NOT NULL.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_not_null(cls, value: str | None) -> str:
        # Validators don't run for defaults, only for values the client actually sent,
        # so this rejects an explicit {"name": null} but still allows leaving name out.
        if value is None:
            raise ValueError("name cannot be null")
        return value


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class DicesimResult(BaseModel):
    goal: list[str]
    method: str
    probability: float = Field(ge=0, le=1)
    # Only set for method=simulation:
    trials: int | None = None
    successes: int | None = None
    standard_error: float | None = None


class LoginRequest(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=1024)  # argon2 doesn't need a limit; this caps abuse


class SessionInfo(BaseModel):
    """What an SPA needs to know about its login (it can't read the HttpOnly cookie)."""

    username: str
    csrf_token: str  # send back as X-CSRF-Token on POST/PATCH/DELETE
