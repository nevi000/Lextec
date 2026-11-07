from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.services.ai.base import AIProvider
from app.services.ai.usage import UsageGate
from app.services.cases.service import CaseService
from app.services.knowledge.loader import KnowledgeBase
from app.services.sources.fedlex.provider import CachedFedlexProvider


@dataclass
class AppContext:
    settings: Settings
    session_factory: sessionmaker[Session]
    kb: KnowledgeBase
    ai: AIProvider
    gate: UsageGate | None = None


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_session(ctx: AppContext = Depends(get_ctx)) -> Iterator[Session]:
    session = ctx.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_service(
    ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)
) -> CaseService:
    return CaseService(
        session,
        ctx.kb,
        ctx.ai,
        rephrase_questions=ctx.settings.ai_rephrase_questions,
        today=ctx.settings.app_today,
        max_attempts=ctx.settings.ai_max_analysis_attempts_per_message,
        source_provider=CachedFedlexProvider(ctx.session_factory, ctx.settings, ctx.kb),
    )
