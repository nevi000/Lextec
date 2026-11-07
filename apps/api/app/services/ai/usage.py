"""Server-side AI usage tracking and hard limits (cost control).

Every real provider call is *reserved* before it is made (worst-case cost counted immediately,
under a process-wide lock, so parallel requests cannot slip past the limits) and *completed* with the
actual usage metadata afterwards.

IMPORTANT: these are APPLICATION limits based on our own accounting and an estimated price. They are not a
guaranteed upper bound of what Google bills (billing may differ, e.g. other clients using the same key).
Set a budget cap in Google AI Studio / Cloud billing as the real safety net.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.tables import AIUsage
from app.services.ai.base import AIBudgetExceededError

# Official standard (paid tier) prices, USD per 1M tokens (output includes thinking tokens).
# Source: Google AI pricing page, retrieved 2026-11-07. Schedule entries: (valid_until, input, output);
# valid_until None = open-ended. Unknown models -> cost "unknown" (never guessed).
PRICE_SCHEDULE: dict[str, list[tuple[date | None, float, float]]] = {
    "gemini-3.8-flash": [(date(2026, 12, 31), 0.75, 3.75), (None, 1.50, 7.50)],
    "gemini-3.5-flash-lite": [(None, 0.30, 2.50)],
    "gemini-2.5-flash": [(None, 0.30, 2.50)],
}

_LOCK = threading.Lock()
STALE_RESERVATION = timedelta(minutes=15)


@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok
        ) / 1_000_000


def pricing_for(model: str, settings: Settings, on: date | None = None) -> Pricing | None:
    if (
        settings.ai_price_input_per_mtok is not None
        and settings.ai_price_output_per_mtok is not None
    ):
        return Pricing(settings.ai_price_input_per_mtok, settings.ai_price_output_per_mtok)
    on = on or datetime.now(UTC).date()
    for until, inp, out in PRICE_SCHEDULE.get(model, []):
        if until is None or on <= until:
            return Pricing(inp, out)
    return None


def estimate_tokens(text: str) -> int:
    """Conservative local estimate (German text ~3.5 chars/token; we assume 3)."""
    return max(1, len(text) // 3 + 1)


def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


class UsageGate:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings):
        self._sf = session_factory
        self._s = settings

    # ---- accounting --------------------------------------------------------------------
    @staticmethod
    def _counted_cost(row: AIUsage) -> float:
        if row.cost_usd is not None:
            return row.cost_usd
        return row.reserved_cost_usd or 0.0

    def _rows(self, session: Session, since: datetime, until: datetime, case_id: str | None = None):
        stmt = select(AIUsage).where(
            AIUsage.created_at >= since,
            AIUsage.created_at < until,
            AIUsage.status != "BLOCKED",
        )
        if case_id:
            stmt = stmt.where(AIUsage.case_id == case_id)
        return list(session.scalars(stmt))

    def reserve(
        self, *, case_id: str | None, function: str, model: str, est_input_tokens: int
    ) -> str:
        s = self._s
        now = datetime.now(UTC)
        price = pricing_for(model, s)
        max_out = s.ai_max_output_tokens_per_call
        worst = price.cost(est_input_tokens, max_out) if price else None

        with _LOCK, self._sf() as session:
            # expire stale reservations (crashed request) so they do not block forever
            for r in session.scalars(
                select(AIUsage).where(
                    AIUsage.status == "RESERVED", AIUsage.created_at < now - STALE_RESERVATION
                )
            ):
                r.status = "ERROR"
                r.error_code = "stale_reservation"

            def block(reason: str) -> AIBudgetExceededError:
                session.add(
                    AIUsage(
                        case_id=case_id,
                        function=function,
                        model=model,
                        status="BLOCKED",
                        error_code=reason,
                        input_tokens=0,
                        output_tokens=0,
                        thinking_tokens=0,
                        total_tokens=0,
                        cost_known=False,
                    )
                )
                session.commit()
                return AIBudgetExceededError(
                    _MESSAGES[reason], code="ai_limit_reached", reason=reason
                )

            if est_input_tokens > s.ai_max_input_tokens_per_call:
                raise block("input_tokens_per_call")
            day_start, day_end = _day_bounds(now)
            day = self._rows(session, day_start, day_end)
            if len(day) >= s.ai_daily_request_limit:
                raise block("daily_requests")
            if (
                sum(r.total_tokens or r.est_input_tokens or 0 for r in day)
                + est_input_tokens
                + max_out
                > s.ai_daily_token_limit
            ):
                raise block("daily_tokens")
            if case_id:
                case_rows = self._rows(session, datetime(2000, 1, 1, tzinfo=UTC), day_end, case_id)
                if len(case_rows) >= s.ai_max_calls_per_case:
                    raise block("case_calls")
                if (
                    worst is not None
                    and sum(self._counted_cost(r) for r in case_rows) + worst > s.ai_case_budget_usd
                ):
                    raise block("case_budget")
            if (
                worst is not None
                and sum(self._counted_cost(r) for r in day) + worst > s.ai_daily_budget_usd
            ):
                raise block("daily_budget")

            row = AIUsage(
                case_id=case_id,
                function=function,
                model=model,
                status="RESERVED",
                est_input_tokens=est_input_tokens,
                reserved_cost_usd=worst,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                total_tokens=0,
                cost_known=worst is not None,
            )
            session.add(row)
            session.commit()
            return row.id

    def complete(
        self,
        usage_id: str,
        *,
        usage_metadata: Any | None,
        status: str,
        error_code: str | None = None,
    ) -> None:
        with _LOCK, self._sf() as session:
            row = session.get(AIUsage, usage_id)
            if row is None:
                return
            row.status = status
            row.error_code = error_code
            if usage_metadata is not None:
                inp = int(getattr(usage_metadata, "prompt_token_count", 0) or 0)
                out = int(getattr(usage_metadata, "candidates_token_count", 0) or 0)
                think = int(getattr(usage_metadata, "thoughts_token_count", 0) or 0)
                total = int(getattr(usage_metadata, "total_token_count", 0) or (inp + out + think))
                row.input_tokens, row.output_tokens, row.thinking_tokens, row.total_tokens = (
                    inp,
                    out,
                    think,
                    total,
                )
                price = pricing_for(row.model, self._s)
                if price:
                    row.cost_usd = price.cost(
                        inp, out + think
                    )  # thinking tokens are billed as output
                    row.cost_known = True
                else:
                    row.cost_known = False
            elif status == "ERROR":
                # no usage reported: count the input side only (conservative for errors that may be billed)
                price = pricing_for(row.model, self._s)
                row.cost_usd = price.cost(row.est_input_tokens or 0, 0) if price else None
            session.commit()

    # ---- reporting ---------------------------------------------------------------------
    def summary(self) -> dict:
        now = datetime.now(UTC)
        day_start, day_end = _day_bounds(now)
        with self._sf() as session:
            rows = self._rows(session, day_start, day_end)
            blocked = (
                session.scalar(
                    select(func.count())
                    .select_from(AIUsage)
                    .where(
                        AIUsage.status == "BLOCKED",
                        AIUsage.created_at >= day_start,
                        AIUsage.created_at < day_end,
                    )
                )
                or 0
            )
        known = all(r.cost_known for r in rows) if rows else True
        return {
            "calls_today": len(rows),
            "blocked_today": blocked,
            "input_tokens_today": sum(r.input_tokens or 0 for r in rows),
            "output_tokens_today": sum(
                (r.output_tokens or 0) + (r.thinking_tokens or 0) for r in rows
            ),
            "estimated_cost_today_usd": round(sum(self._counted_cost(r) for r in rows), 6)
            if known
            else None,
            "cost_known": known,
            "daily_request_limit": self._s.ai_daily_request_limit,
            "daily_budget_usd": self._s.ai_daily_budget_usd,
            "case_budget_usd": self._s.ai_case_budget_usd,
            "max_calls_per_case": self._s.ai_max_calls_per_case,
        }

    def recent(self, limit: int = 25) -> list[AIUsage]:
        with self._sf() as session:
            return list(
                session.scalars(select(AIUsage).order_by(AIUsage.created_at.desc()).limit(limit))
            )


_MESSAGES = {
    "input_tokens_per_call": "Die Anfrage wäre für ein einzelnes KI-Aufruf-Limit (Eingabe-Tokens) zu gross und wurde nicht gesendet.",
    "daily_requests": "Das tägliche Limit an KI-Aufrufen ist erreicht. Es wurde nichts an Gemini gesendet.",
    "daily_tokens": "Das tägliche Token-Limit für KI-Aufrufe ist erreicht. Es wurde nichts an Gemini gesendet.",
    "case_calls": "Für diesen Fall ist die maximale Anzahl KI-Aufrufe erreicht. Es wurde nichts an Gemini gesendet.",
    "case_budget": "Das KI-Kostenbudget für diesen Fall ist erreicht. Es wurde nichts an Gemini gesendet.",
    "daily_budget": "Das tägliche KI-Kostenbudget ist erreicht. Es wurde nichts an Gemini gesendet.",
}
