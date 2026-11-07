"""Sprachbrücke endpoints.

* ``/api/cases/{id}/voice-bridge/*``  - social worker (full app, local machine only)
* ``/api/bridge/*``                    - the phone: authenticated ONLY by the session token (header
  ``X-Bridge-Token``; it travels in the URL fragment of the page, never in a URL the server sees), returns
  nothing but the current question, and writes nothing to the case.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, Request

from app.api.deps import AppContext, get_ctx, get_service
from app.core.errors import AppError
from app.schemas.bridge import (
    MobileAnswer,
    MobileLanguage,
    MobileState,
    WorkerAccept,
    WorkerState,
)
from app.services.bridge.service import BridgeService, BridgeUnauthorized, hash_token
from app.services.cases.service import CaseService


class TooManyRequests(AppError):
    status_code = 429
    code = "too_many_requests"


class RateLimiter:
    """Small in-process sliding window (single API process). Protects the phone endpoints from token guessing and from
    runaway clients; normal polling (one request every 2 s) stays far below every limit."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def over(self, key: str, limit: int, window: float, *, count: bool = True) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return True
            if count:
                q.append(now)
            return False

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


LIMITER = RateLimiter()
FAILED_AUTH_LIMIT = (15, 60.0)  # failed token lookups per client and minute
CLIENT_LIMIT = (200, 10.0)  # all phone requests per client and 10 s
TOKEN_LIMIT = (80, 10.0)  # per token and 10 s
ANSWER_LIMIT = (20, 60.0)  # answer submissions per token and minute


def _client(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "?")


def mobile_guard(request: Request) -> None:
    c = _client(request)
    if LIMITER.over(f"fail:{c}", *FAILED_AUTH_LIMIT, count=False) or LIMITER.over(
        f"ip:{c}", *CLIENT_LIMIT
    ):
        raise TooManyRequests("Zu viele Anfragen. Bitte einen Moment warten.")


worker = APIRouter(prefix="/api/cases/{case_id}/voice-bridge", tags=["voice-bridge"])
mobile = APIRouter(
    prefix="/api/bridge", tags=["voice-bridge-mobile"], dependencies=[Depends(mobile_guard)]
)


def get_bridge(
    svc: CaseService = Depends(get_service), ctx: AppContext = Depends(get_ctx)
) -> BridgeService:
    return BridgeService(
        svc.s,
        svc,
        ttl_minutes=ctx.settings.bridge_ttl_minutes,
        session_factory=ctx.session_factory,
        inline_translation=ctx.settings.bridge_translate_inline,
    )


def _state(b: BridgeService, row, ctx: AppContext) -> WorkerState:
    return b.worker_state(row, public_base_url=ctx.settings.bridge_public_base_url)


def _active(b: BridgeService, case_id: str):
    b.cases.get_case(case_id)
    row = b.active_for_case(case_id)
    if row is None:
        raise AppError("Es ist keine Sprachbrücke aktiv.", code="bridge_not_active")
    return row


# ---- social worker ---------------------------------------------------------------------------
@worker.get("", response_model=WorkerState)
def get_state(
    case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)
) -> WorkerState:
    b.cases.get_case(case_id)
    row = b.active_for_case(case_id)
    if row is not None:
        b.sync(row)  # also reflects answers/skips made at the desk
    return _state(b, row, ctx)


@worker.post("", response_model=WorkerState, status_code=201)
def start(
    case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)
) -> WorkerState:
    row, _token = b.start(case_id)
    return _state(b, row, ctx)


@worker.post("/pause", response_model=WorkerState)
def pause(case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)):
    row = _active(b, case_id)
    b.set_paused(row, True)
    return _state(b, row, ctx)


@worker.post("/resume", response_model=WorkerState)
def resume(
    case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)
):
    row = _active(b, case_id)
    b.set_paused(row, False)
    b.sync(row)
    return _state(b, row, ctx)


@worker.post("/end", response_model=WorkerState)
def end(case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)):
    row = _active(b, case_id)
    b.end(row)
    return _state(b, None, ctx)


@worker.post("/answer/accept", response_model=WorkerState)
def accept(
    case_id: str,
    body: WorkerAccept,
    b: BridgeService = Depends(get_bridge),
    ctx: AppContext = Depends(get_ctx),
):
    row = _active(b, case_id)
    b.accept(row, body.corrected_value, body.corrected_text_de)
    return _state(b, row, ctx)


@worker.post("/answer/reask", response_model=WorkerState)
def reask(case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)):
    row = _active(b, case_id)
    b.reask(row)
    return _state(b, row, ctx)


@worker.post("/skip", response_model=WorkerState)
def skip(case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)):
    row = _active(b, case_id)
    b.skip(row)
    return _state(b, row, ctx)


@worker.post("/retry-translation", response_model=WorkerState)
def retry_translation(
    case_id: str, b: BridgeService = Depends(get_bridge), ctx: AppContext = Depends(get_ctx)
):
    row = _active(b, case_id)
    b.retry_translation(row)
    return _state(b, row, ctx)


# ---- phone ------------------------------------------------------------------------------------
def _session(b: BridgeService, token: str | None, request: Request, *, answer: bool = False):
    try:
        row = b.by_token(token)
    except BridgeUnauthorized:
        LIMITER.over(f"fail:{_client(request)}", *FAILED_AUTH_LIMIT)  # count the failed guess
        raise
    tk = hash_token(token or "")[:16]
    if LIMITER.over(f"tok:{tk}", *TOKEN_LIMIT) or (
        answer and LIMITER.over(f"ans:{tk}", *ANSWER_LIMIT)
    ):
        raise TooManyRequests("Zu viele Anfragen. Bitte einen Moment warten.")
    return row


@mobile.get("/state", response_model=MobileState)
def mobile_state(
    request: Request,
    x_bridge_token: str | None = Header(default=None),
    b: BridgeService = Depends(get_bridge),
) -> MobileState:
    row = _session(b, x_bridge_token, request)
    b.touch(row)
    b.sync(row)
    return b.mobile_state(row)


@mobile.post("/language", response_model=MobileState)
def mobile_language(
    body: MobileLanguage,
    request: Request,
    x_bridge_token: str | None = Header(default=None),
    b: BridgeService = Depends(get_bridge),
) -> MobileState:
    row = _session(b, x_bridge_token, request)
    b.set_language(row, body.language)
    b.touch(row)
    return b.mobile_state(row)


@mobile.post("/answer", response_model=MobileState)
def mobile_answer(
    body: MobileAnswer,
    request: Request,
    x_bridge_token: str | None = Header(default=None),
    b: BridgeService = Depends(get_bridge),
) -> MobileState:
    row = _session(b, x_bridge_token, request, answer=True)
    b.touch(row)
    b.sync(
        row
    )  # the question may have changed at the desk: a stale answer must be rejected, not misfiled
    b.submit(row, body.instance_id, body.request_id, body.kind, body.value)
    return b.mobile_state(row)
