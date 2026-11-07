"""SQLAlchemy ORM models. UTC timestamps; JSON columns for flexible payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


def _uuid() -> str:
    return str(uuid4())


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    current_action: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True
    )


class CaseMessage(Base):
    __tablename__ = "case_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20), default="DESCRIPTION")
    content: Mapped[str] = mapped_column(Text)
    answers_fact_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # provenance of answers entered through the Sprachbrücke (None = typed by the social worker)
    origin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseIssue(Base):
    __tablename__ = "case_issues"
    __table_args__ = (Index("ix_case_issues_case", "case_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    issue_definition_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_status: Mapped[str] = mapped_column(String(20), default="DETECTED")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("case_messages.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseFact(Base):
    __tablename__ = "case_facts"
    __table_args__ = (UniqueConstraint("case_id", "fact_id", name="uq_case_facts_case_fact"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    fact_id: Mapped[str] = mapped_column(String(100))
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="MISSING")
    origin: Mapped[str] = mapped_column(String(30), default="AI_EXTRACTED")
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("case_messages.id", ondelete="SET NULL"), nullable=True
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    documented: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    deferred_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicting_values: Mapped[list] = mapped_column(JSON, default=list)
    history: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    case_version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    main_reason_code: Mapped[str] = mapped_column(String(100))
    reason_codes: Mapped[list] = mapped_column(JSON)
    triggered_rule_ids: Mapped[list] = mapped_column(JSON)
    knowledge_base_version: Mapped[str] = mapped_column(String(40))
    signature: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)  # full DecisionResult
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BriefingVersion(Base):
    __tablename__ = "briefings"
    __table_args__ = (UniqueConstraint("case_id", "version", name="uq_briefings_case_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    case_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Handover(Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), unique=True, index=True
    )
    professional_types: Mapped[list] = mapped_column(JSON, default=list)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="RECOMMENDED")
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SourceSnapshot(Base):
    """An official law text retrieved from Fedlex (one row per source, version and content).

    Rows are never overwritten when a statute changes: a new version (or changed content) creates a new
    row, so older wording stays reproducible. ``origin`` separates a real Fedlex retrieval from test fixtures."""

    __tablename__ = "source_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "version_identifier",
            "language",
            "content_hash",
            name="uq_snapshot_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    origin: Mapped[str] = mapped_column(String(12), default="FEDLEX")  # FEDLEX | FIXTURE
    sr_number: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(4))
    law_abbreviation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    law_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    article: Mapped[str] = mapped_column(String(20))
    paragraph: Mapped[str | None] = mapped_column(String(40), nullable=True)
    letter: Mapped[str | None] = mapped_column(String(4), nullable=True)
    article_label: Mapped[str] = mapped_column(String(80))
    requested_reference_date: Mapped[str] = mapped_column(String(10))
    version_identifier: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    valid_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    abstract_uri: Mapped[str | None] = mapped_column(String(300), nullable=True)
    eli_uri: Mapped[str | None] = mapped_column(String(300), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    article_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    article_eid: Mapped[str | None] = mapped_column(String(80), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    structure: Mapped[list] = mapped_column(JSON, default=list)  # paragraphs with numbered items
    content_hash: Mapped[str] = mapped_column(String(64))
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceSyncState(Base):
    """Result of the latest sync attempt per source (also records failures, which have no snapshot)."""

    __tablename__ = "source_sync_state"

    source_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(24))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceWordingCheck(Base):
    """Comparison of the knowledge-base wording (quoted fragments) with an official snapshot."""

    __tablename__ = "source_wording_checks"
    __table_args__ = (
        UniqueConstraint("source_id", "snapshot_id", "kb_text_hash", name="uq_wording_check"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("source_snapshots.id", ondelete="CASCADE"))
    kb_text_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))  # MATCHED | MISMATCH | NO_COMPARABLE_TEXT
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    method: Mapped[str] = mapped_column(String(60), default="normalized-quoted-fragments")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIUsage(Base):
    """One row per real AI provider call attempt (or blocked attempt). No message content stored."""

    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    case_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    function: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(12))  # RESERVED | OK | ERROR | BLOCKED
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    est_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    thinking_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reserved_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_known: Mapped[bool] = mapped_column(Boolean, default=False)


class SafetyEvent(Base):
    """A safety signal detected in a user message (persisted so it survives reloads; never silently deleted).

    ``acknowledged_*`` documents that a human looked at it. It does NOT clear the warning."""

    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    certainty: Mapped[str] = mapped_column(String(10))  # ACUTE | UNCLEAR
    action: Mapped[str] = mapped_column(String(40))  # configured consequence at detection time
    rule_id: Mapped[str] = mapped_column(String(80))
    evidence: Mapped[str] = mapped_column(Text)
    modifiers: Mapped[list] = mapped_column(JSON, default=list)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class VoiceBridgeSession(Base):
    """One temporary phone connection per case (Sprachbrücke). The token is stored only as a hash; ``join_token`` is
    kept just until the phone has connected so a reloaded desktop can draw the QR code again."""

    __tablename__ = "bridge_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    join_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="WAITING_FOR_CONNECTION")
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str | None] = mapped_column(String(5), nullable=True)
    rev: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # the concrete question instance currently shown on the phone (derived from the question selection engine)
    question_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    question_fact_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    question_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    translation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    translation_status: Mapped[str] = mapped_column(String(10), default="NONE")
    translation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # the proposal from the phone; applied to the case only after the social worker accepts it
    answer_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answer_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TranslationCache(Base):
    """Machine translations of fixed question texts (never of case content)."""

    __tablename__ = "translation_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_lang: Mapped[str] = mapped_column(String(5))
    target_lang: Mapped[str] = mapped_column(String(5))
    source_text: Mapped[str] = mapped_column(Text)
    translated: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
