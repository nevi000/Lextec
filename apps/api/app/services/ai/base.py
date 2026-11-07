from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.core.config import Settings
from app.core.errors import AppError
from app.services.ai.schemas import ExtractionInput, ExtractionResult

if TYPE_CHECKING:
    from app.services.ai.usage import UsageGate


class AIProviderError(AppError):
    status_code = 502
    code = "ai_error"

    def __init__(self, message: str, *, code: str | None = None, retryable: bool = False):
        super().__init__(message, code=code)
        self.retryable = retryable


class AIConfigurationError(AIProviderError):
    status_code = 500
    code = "ai_configuration_error"


class AIRateLimitError(AIProviderError):
    status_code = 429
    code = "ai_rate_limited"


class AIUnavailableError(AIProviderError):
    code = "ai_unavailable"


class AIInvalidResponseError(AIProviderError):
    code = "ai_invalid_response"


class AIOutputTruncatedError(AIInvalidResponseError):
    """The model stopped because it hit the output token limit: the JSON is incomplete and is never «repaired»."""

    code = "ai_output_truncated"


class AIBudgetExceededError(AIProviderError):
    """A local application limit (calls, tokens, budget) blocked the request BEFORE it was sent."""

    status_code = 429
    code = "ai_limit_reached"

    def __init__(self, message: str, *, code: str | None = None, reason: str = "limit"):
        super().__init__(message, code=code, retryable=False)
        self.reason = reason


@dataclass(frozen=True)
class CallContext:
    """Who/what a provider call is for (usage accounting)."""

    case_id: str | None
    function: str  # e.g. "extract", "rephrase_question"


class AIProvider(Protocol):
    name: str
    model: str

    def extract(
        self, data: ExtractionInput, ctx: CallContext | None = None
    ) -> ExtractionResult: ...

    def rephrase_question(
        self, question_de: str, context: str, ctx: CallContext | None = None
    ) -> str: ...

    def translate(
        self, texts: list[str], source: str, target: str, ctx: CallContext | None = None
    ) -> list[str]: ...


def build_provider(settings: Settings, gate: UsageGate | None = None) -> AIProvider:
    if settings.ai_provider == "mock":
        from app.services.ai.mock import MockAIProvider

        return MockAIProvider()
    from app.services.ai.gemini import GeminiProvider

    return GeminiProvider(settings, gate)
