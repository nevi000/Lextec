from __future__ import annotations

from enum import StrEnum


class Action(StrEnum):
    ASK = "ASK"
    PROCEED = "PROCEED"
    ESCALATE = "ESCALATE"


class FactStatus(StrEnum):
    KNOWN = "KNOWN"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTORY = "CONTRADICTORY"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    # Asked, but the person does not know. Different from MISSING (never asked) - never re-asked.
    UNKNOWN = "UNKNOWN"


class FactOrigin(StrEnum):
    AI_EXTRACTED = "AI_EXTRACTED"
    USER_ANSWER = "USER_ANSWER"
    USER_CORRECTION = "USER_CORRECTION"


class IssueStatus(StrEnum):
    DETECTED = "DETECTED"  # supported by the knowledge base
    UNSUPPORTED = "UNSUPPORTED"  # recognised by the AI, but not covered by the knowledge base


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class MessageRole(StrEnum):
    SOCIAL_WORKER = "SOCIAL_WORKER"
    SYSTEM = "SYSTEM"


class MessageKind(StrEnum):
    DESCRIPTION = "DESCRIPTION"
    ANSWER = "ANSWER"
    NOTE = "NOTE"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"
    FAILED = "FAILED"


class HandoverStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    HANDOFF_REQUESTED = "HANDOFF_REQUESTED"
    HANDOFF_COMPLETED = "HANDOFF_COMPLETED"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
