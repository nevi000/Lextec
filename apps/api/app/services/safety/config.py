"""Schema of knowledge_base/safety/safety_signals.yaml (how safety signals are recognised)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Modifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    negation: list[str] = []
    historical: list[str] = []
    hypothetical: list[str] = []
    professional: list[str] = []
    quote_markers: list[str] = []


class SafetyCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label_de: str
    acute: list[str] = []
    mention: list[str] = []


class SafetyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headline_de: str
    explanation_de: str
    steps_de: list[str] = []


class SafetySignalsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    version: str
    content_status: str | None = None
    modifiers: Modifiers = Field(default_factory=Modifiers)
    categories: list[SafetyCategory]
    responses: dict[str, SafetyResponse] = {}
