from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alembic import command
from app.api.bridge_routes import mobile as bridge_mobile
from app.api.bridge_routes import worker as bridge_worker
from app.api.deps import AppContext
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db.session import make_engine, make_session_factory
from app.services.ai.base import build_provider
from app.services.ai.usage import UsageGate
from app.services.knowledge.loader import load_knowledge_base

log = logging.getLogger("lextec")
API_DIR = Path(__file__).resolve().parents[1]


def _ensure_sqlite_dir(database_url: str) -> None:
    """A fresh clone has no data/ directory (it is gitignored) - create it before connecting."""
    if database_url.startswith("sqlite") and ":memory:" not in database_url:
        path = database_url.split("///", 1)[-1]
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)


def run_migrations(database_url: str) -> None:
    _ensure_sqlite_dir(database_url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_migrate:
            run_migrations(settings.database_url)
        engine = make_engine(settings.database_url)
        kb = load_knowledge_base(settings.knowledge_base_dir)
        if not kb.valid:
            log.warning("Knowledge base has %d validation error(s).", len(kb.errors))
        factory = make_session_factory(engine)
        gate = UsageGate(factory, settings)
        app.state.ctx = AppContext(
            settings=settings,
            session_factory=factory,
            kb=kb,
            ai=build_provider(settings, gate),  # raises a clear error if Gemini is misconfigured
            gate=gate,
        )
        log.info("AI provider: %s (%s)", app.state.ctx.ai.name, app.state.ctx.ai.model)
        yield
        engine.dispose()

    app = FastAPI(
        title="LexTec Bridge API",
        version="0.1.0",
        description="Local development API. Synthetic data only. No authentication.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def _restrict_remote(request, call_next):  # noqa: ANN001
        """Devices on the network (the phone, reached through the dev proxy) may only use the bridge endpoints.

        Every hop of X-Forwarded-For counts: one non-local hop is enough to restrict the request."""
        if (
            settings.restrict_remote_access
            and _is_remote(request)
            and not _remote_allowed(request.url.path)
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "remote_forbidden",
                        "message": "Kein Zugriff von diesem Gerät.",
                    }
                },
            )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if "/voice-bridge" in request.url.path or request.url.path.startswith("/api/bridge/"):
            response.headers["Cache-Control"] = (
                "no-store"  # question/answer text and the join token are never cached
            )
        return response

    app.include_router(router)
    app.include_router(bridge_worker)
    app.include_router(bridge_mobile)
    return app


_LOCAL = {"127.0.0.1", "::1", "localhost", "testclient"}


def _is_remote(request) -> bool:  # noqa: ANN001
    hosts = [request.client.host] if request.client else []
    fwd = request.headers.get("x-forwarded-for", "")
    hosts += [h.strip() for h in fwd.split(",") if h.strip()]
    return any(h not in _LOCAL and h != "::ffff:127.0.0.1" for h in hosts)


def _remote_allowed(path: str) -> bool:
    return path.startswith("/api/bridge/") or path == "/api/health"


app = create_app()
