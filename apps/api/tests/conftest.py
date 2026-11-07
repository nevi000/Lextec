from __future__ import annotations

import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _no_real_ai(monkeypatch):
    """Safety net: tests must never use the real Gemini key from .env or the environment."""
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    os.environ["AI_PROVIDER"] = "mock"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        ai_provider="mock",
        gemini_api_key=None,
        app_today=date(2026, 11, 7),
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        knowledge_base_dir=REPO_ROOT / "knowledge_base",
        _env_file=None,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def ctx(client):
    return client.app.state.ctx


def new_case(client, title: str = "") -> dict:
    r = client.post("/api/cases", json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


def say(client, case_id: str, text: str, answers: str | None = None) -> dict:
    body = {"content": text}
    if answers:
        body["answers_fact_id"] = answers
    r = client.post(f"/api/cases/{case_id}/messages", json=body)
    assert r.status_code == 201, r.text
    return r.json()
