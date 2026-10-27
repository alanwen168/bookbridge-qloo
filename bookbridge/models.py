from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["book", "movie", "artist"]


class Anchor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    kind: Kind

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("name is required")
        return value


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=120)
    kind: Kind
    mode: Literal["live", "sample"] = "live"

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("query is required")
        return value


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    members: list[Annotated[list[Anchor], Field(min_length=1, max_length=3)]] = Field(min_length=2, max_length=2)
    top_k: int = Field(default=3, ge=1, le=5)
    mode: Literal["live", "sample"] = "live"

    @field_validator("members")
    @classmethod
    def exactly_two(cls, value: list[list[Anchor]]) -> list[list[Anchor]]:
        if len(value) != 2 or any(not 1 <= len(m) <= 3 for m in value):
            raise ValueError("exactly two members with 1–3 anchors each are required")
        if any(len({a.id for a in group}) != len(group) for group in value):
            raise ValueError("choose distinct anchors for each member")
        return value
