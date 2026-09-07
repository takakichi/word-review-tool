"""Pydantic models for validated review results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewItem(BaseModel):
    """A single issue identified by the language model."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    page: int = Field(ge=1)
    category: str = Field(min_length=1)
    severity: Literal["high", "medium", "low"]
    target_text: str = Field(min_length=1)
    issue: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class ReviewResponse(BaseModel):
    """Expected top-level Ollama JSON response."""

    model_config = ConfigDict(extra="ignore")

    reviews: list[ReviewItem] = Field(default_factory=list)


class ParseFailure(BaseModel):
    """Non-fatal information retained when an LLM response is invalid."""

    chunk_number: int = Field(ge=1)
    error: str
    raw_response: str


class ReviewRunResult(BaseModel):
    """Aggregated output from all review chunks."""

    reviews: list[ReviewItem] = Field(default_factory=list)
    failures: list[ParseFailure] = Field(default_factory=list)
    raw_responses: list[str] = Field(default_factory=list)

