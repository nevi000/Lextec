"""Google Gemini provider (official `google-genai` SDK) with structured JSON output and cost control.

Every attempt (including a retry) is reserved against the usage limits BEFORE the request is sent and
completed with the real usage metadata afterwards (see `usage.py`). A blocked attempt never reaches Google.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.core.config import Settings
from app.services.ai.base import (
    AIBudgetExceededError,
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AIUnavailableError,
    CallContext,
)
from app.services.ai.prompts import CLARIFICATION_WORDING_V1, EXTRACTION_SYSTEM_PROMPT
from app.services.ai.schemas import ExtractionInput, ExtractionResult
from app.services.ai.usage import estimate_tokens

if TYPE_CHECKING:
    from app.services.ai.usage import UsageGate

log = logging.getLogger(__name__)


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings, gate: UsageGate | None = None):
        if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
            raise AIConfigurationError(
                "AI_PROVIDER=gemini, aber GEMINI_API_KEY ist nicht gesetzt. "
                "Setzen Sie den Schlüssel in der .env-Datei oder wechseln Sie auf AI_PROVIDER=mock."
            )
        from google import genai
        from google.genai import types

        self._types = types
        self._gate = gate  # None only in unit tests of the provider itself
        self.model = settings.gemini_model
        self._timeout = settings.ai_timeout_seconds
        self._retries = settings.ai_max_retries
        self._max_out = settings.ai_max_output_tokens_per_call
        self._thinking_level = settings.ai_thinking_level
        self._client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(settings.ai_timeout_seconds * 1000)),
        )

    # ---- low level -----------------------------------------------------------------------
    def _config(self, system: str, json_schema: dict | None):
        t = self._types
        kwargs: dict = {
            "system_instruction": system,
            "temperature": 0.0,
            "max_output_tokens": self._max_out,
        }
        # Extraction does not need reasoning: keep thinking minimal so tokens (and cost) stay small.
        if self.model.startswith("gemini-3"):
            # MINIMAL is rejected by gemini-3.8-flash (HTTP 400, verified); LOW is the default.
            level = getattr(t.ThinkingLevel, self._thinking_level.upper(), t.ThinkingLevel.LOW)
            kwargs["thinking_config"] = t.ThinkingConfig(thinking_level=level)
        elif self.model.startswith("gemini-2.5"):
            kwargs["thinking_config"] = t.ThinkingConfig(thinking_budget=0)
        if json_schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_json_schema"] = json_schema
        return t.GenerateContentConfig(**kwargs)

    def _call(
        self, *, system: str, contents: str, json_schema: dict | None, ctx: CallContext | None
    ) -> str:
        from google.genai import errors

        config = self._config(system, json_schema)
        est = estimate_tokens(system + contents)
        function = ctx.function if ctx else "unknown"
        case_id = ctx.case_id if ctx else None

        last: Exception | None = None
        for attempt in range(self._retries + 1):
            usage_id = None
            if self._gate is not None:
                usage_id = self._gate.reserve(  # may raise AIBudgetExceededError: nothing is sent
                    case_id=case_id, function=function, model=self.model, est_input_tokens=est
                )
            try:
                resp = self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except errors.APIError as exc:
                last = exc
                code = getattr(exc, "code", None)
                if self._gate is not None and usage_id:
                    self._gate.complete(
                        usage_id, usage_metadata=None, status="ERROR", error_code=f"http_{code}"
                    )
                retryable = code in (408, 429, 500, 502, 503, 504)
                log.warning("Gemini API error code=%s attempt=%d", code, attempt + 1)
                if not retryable or attempt >= self._retries:
                    if code == 429:
                        raise AIRateLimitError(
                            "Gemini-Kontingent bzw. Ratenlimit erreicht. Bitte später erneut versuchen.",
                            retryable=True,
                        ) from exc
                    if code in (401, 403):
                        raise AIConfigurationError(
                            "Gemini hat den API-Schlüssel abgelehnt. Bitte GEMINI_API_KEY prüfen."
                        ) from exc
                    if code == 404:
                        raise AIConfigurationError(
                            f"Gemini-Modell '{self.model}' nicht gefunden. Bitte GEMINI_MODEL prüfen."
                        ) from exc
                    if code == 400:
                        detail = str(getattr(exc, "message", "") or "")[:300]
                        raise AIConfigurationError(
                            "Gemini hat die Anfrage als ungültig abgelehnt (HTTP 400). Bitte Modell und "
                            f"Konfiguration prüfen. Meldung von Google: {detail}"
                        ) from exc
                    raise AIUnavailableError(
                        f"Gemini-Anfrage fehlgeschlagen (HTTP {code}).", retryable=retryable
                    ) from exc
            except Exception as exc:  # network errors, timeouts
                last = exc
                if self._gate is not None and usage_id:
                    self._gate.complete(
                        usage_id, usage_metadata=None, status="ERROR", error_code=type(exc).__name__
                    )
                log.warning("Gemini transport error %s attempt=%d", type(exc).__name__, attempt + 1)
                if attempt >= self._retries:
                    raise AIUnavailableError(
                        "Gemini ist nicht erreichbar oder die Anfrage hat das Zeitlimit überschritten.",
                        retryable=True,
                    ) from exc
            else:
                if self._gate is not None and usage_id:
                    self._gate.complete(
                        usage_id, usage_metadata=getattr(resp, "usage_metadata", None), status="OK"
                    )
                text = resp.text
                if not text:
                    raise AIInvalidResponseError("Gemini lieferte eine leere Antwort.")
                return text
            time.sleep(min(2**attempt, 8) * 0.5)
        raise AIUnavailableError("Gemini-Anfrage fehlgeschlagen.") from last

    # ---- tasks ---------------------------------------------------------------------------
    def extract(self, data: ExtractionInput, ctx: CallContext | None = None) -> ExtractionResult:
        payload = json.dumps(data.model_dump(exclude_defaults=True), ensure_ascii=False)
        text = self._call(
            system=EXTRACTION_SYSTEM_PROMPT,
            contents=payload,
            json_schema=ExtractionResult.model_json_schema(),
            ctx=ctx,
        )
        try:
            return ExtractionResult.model_validate_json(text)
        except ValidationError as exc:
            raise AIInvalidResponseError(
                "Die Gemini-Antwort entsprach nicht dem erwarteten Schema."
            ) from exc

    def rephrase_question(
        self, question_de: str, context: str, ctx: CallContext | None = None
    ) -> str:
        text = self._call(
            system=CLARIFICATION_WORDING_V1,
            contents=f"Kontext: {context}\nFrage: {question_de}",
            json_schema=None,
            ctx=ctx,
        ).strip()
        if not text or len(text) > 400:
            raise AIInvalidResponseError("Umformulierte Frage unbrauchbar.")
        return text


_ = (AIBudgetExceededError, AIProviderError)  # re-exported for callers that import from here
