from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationError(ValueError):
    pass


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, Any]
    request_id: str = Field(default="unknown", min_length=1)
    source: str = Field(default="local", min_length=1)

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError("payload must be a dict")
        return value

    @field_validator("request_id", "source")
    @classmethod
    def validate_non_empty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValidationError("string field must be non-empty")
        return value


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_score: float
    item_count: int
    numeric_sum: float
    text_weight: float
    bonuses: Mapping[str, float] = Field(default_factory=dict)
    numeric_fields_count: int = 0
    text_fields_count: int = 0
    collection_fields_count: int = 0
    nested_fields_count: int = 0
    bool_true_fields_count: int = 0


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    final_score: float
    capped: bool
    used_fallback: bool
    reason: str | None
    breakdown: ScoreBreakdown
    request_id: str
    source: str
    diagnostics: tuple[str, ...] = ()
    version: str = "2.0.0"


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approved: bool
    label: str
    reason: str


class ScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result: ScoreResult
    review: ReviewDecision


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detail: str
