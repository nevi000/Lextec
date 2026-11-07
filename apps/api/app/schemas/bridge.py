from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BridgeStatus = Literal[
    "WAITING_FOR_CONNECTION",
    "WAITING_FOR_QUESTION",
    "QUESTION_ACTIVE",
    "AWAITING_WORKER_REVIEW",
    "PAUSED",
    "COMPLETED",
    "EXPIRED",
]


class BridgeOption(BaseModel):
    value: str
    label: str  # already in the language of the reader


class MobileQuestion(BaseModel):
    instance_id: str
    data_type: Literal["string", "boolean", "date", "integer", "enum"]
    text: str
    why: str = ""
    options: list[BridgeOption] = []
    optional: bool = False


class MobileState(BaseModel):
    """Everything the phone may see: no case id, no title, no facts, no decision."""

    status: BridgeStatus
    rev: int
    language: str | None
    rtl: bool = False
    question: MobileQuestion | None = None
    notice: Literal["translation_failed", "translation_pending"] | None = None


class MobileLanguage(BaseModel):
    language: str = Field(min_length=2, max_length=5)


class MobileAnswer(BaseModel):
    instance_id: str = Field(min_length=8, max_length=64)
    request_id: str = Field(min_length=8, max_length=64)
    kind: Literal["value", "unknown", "text"]
    value: str | None = Field(default=None, max_length=2000)


class PendingAnswer(BaseModel):
    kind: Literal["value", "unknown", "text"]
    original: str  # as entered on the phone (readable form)
    language: str
    german: str  # structured: canonical German text; free text: machine translation (or the text itself)
    machine_translated: bool
    translation_status: Literal["STRUCTURED", "ORIGINAL_GERMAN", "MACHINE", "FAILED"]
    submitted_at: str


class WorkerQuestion(BaseModel):
    instance_id: str
    fact_id: str
    text_de: str
    text_translated: str | None
    translation_status: Literal["NONE", "PENDING", "OK", "FAILED"]
    translation_error: str | None = None
    translation_error_code: str | None = (
        None  # limit | rate_limited | unavailable | config | invalid | error
    )
    data_type: str
    options: list[BridgeOption] = []
    options_de: list[BridgeOption] = []  # German labels (for correcting an answer at the desk)


class WorkerState(BaseModel):
    active: bool
    session_id: str | None = None
    status: BridgeStatus | None = None
    rev: int = 0
    language: str | None = None
    language_name: str | None = None
    phone_connected: bool = False  # phone polled recently
    last_seen_seconds: int | None = None  # age of the phone's last poll (None = never connected)
    join_token: str | None = (
        None  # only until the phone has connected (to redraw the QR after a reload)
    )
    join_path: str = "/bridge"
    lan_ip: str | None = None
    lan_candidates: list[
        str
    ] = []  # private IPv4 addresses of this machine, default-route address first
    public_base_url: str | None = None
    expires_at: str | None = None
    question: WorkerQuestion | None = None
    answer: PendingAnswer | None = None


class WorkerAccept(BaseModel):
    corrected_value: str | None = Field(default=None, max_length=2000)  # structured answers
    corrected_text_de: str | None = Field(default=None, max_length=5000)  # free text
