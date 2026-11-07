"""Plain input structures for the pure decision engine (no DB, no AI)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.domain.enums import FactStatus, IssueStatus


@dataclass
class FactState:
    status: FactStatus = FactStatus.MISSING
    value: Any = None
    deferred: bool = False


@dataclass
class IssueState:
    status: IssueStatus
    issue_id: str | None = None
    confidence: float | None = None
    description: str | None = None


@dataclass
class CaseSnapshot:
    has_user_input: bool = False
    issues: list[IssueState] = field(default_factory=list)
    facts: dict[str, FactState] = field(default_factory=dict)
    today: date | None = None  # reference date for derived values; None = derived values unknown
    safety_events: list[Any] = field(
        default_factory=list
    )  # SafetyEventState rows (persisted detections)
