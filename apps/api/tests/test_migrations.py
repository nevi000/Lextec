from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import make_engine
from app.main import run_migrations

EXPECTED = {
    "cases",
    "case_messages",
    "case_issues",
    "case_facts",
    "decisions",
    "briefings",
    "handoffs",
    "alembic_version",
}


def test_alembic_upgrade_creates_all_tables_with_fk_enforcement(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    run_migrations(url)
    engine = make_engine(url)
    assert EXPECTED <= set(inspect(engine).get_table_names())
    with engine.connect() as c:
        assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    run_migrations(url)  # idempotent


def test_migration_creates_missing_parent_directory(tmp_path):
    """Regression: a fresh clone has no data/ directory."""
    url = f"sqlite:///{(tmp_path / 'does' / 'not' / 'exist' / 'm.db').as_posix()}"
    run_migrations(url)
    assert "cases" in set(inspect(make_engine(url)).get_table_names())
