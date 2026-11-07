"""Test fixtures for the Fedlex cache: trimmed copies of REAL snapshots, always stored with origin FIXTURE.

A fixture is never reported as an official retrieval or as "verified"; the UI labels it as test data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.tables import SourceSnapshot
from app.services.knowledge.loader import KnowledgeBase

FIXTURE_FILE = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "fedlex" / "snapshots.json"
)
COLUMNS = (
    "source_id",
    "sr_number",
    "language",
    "law_abbreviation",
    "law_title",
    "article",
    "paragraph",
    "letter",
    "article_label",
    "requested_reference_date",
    "version_identifier",
    "valid_from",
    "valid_to",
    "abstract_uri",
    "eli_uri",
    "document_url",
    "article_url",
    "article_eid",
    "heading",
    "text",
    "structure",
    "content_hash",
    "document_hash",
)


def export_fixtures(
    sf: sessionmaker[Session], source_ids: list[str], path: Path = FIXTURE_FILE
) -> int:
    """Developer helper: copy real snapshots from the cache into the fixture file."""
    with sf() as s:
        rows = [
            r
            for r in s.scalars(select(SourceSnapshot).where(SourceSnapshot.origin == "FEDLEX"))
            if r.source_id in source_ids
        ]
    data = [{c: getattr(r, c) for c in COLUMNS} for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return len(data)


def seed_fixtures(
    sf: sessionmaker[Session], kb: KnowledgeBase | None = None, path: Path = FIXTURE_FILE
) -> int:
    """Load fixtures idempotently (origin FIXTURE). Only ids that exist in the knowledge base (if given)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    with sf() as s:
        for d in data:
            if kb is not None and d["source_id"] not in kb.sources:
                continue
            exists = s.scalar(
                select(SourceSnapshot.id).where(
                    SourceSnapshot.source_id == d["source_id"],
                    SourceSnapshot.version_identifier == d["version_identifier"],
                    SourceSnapshot.language == d["language"],
                    SourceSnapshot.content_hash == d["content_hash"],
                )
            )
            if exists:
                continue
            now = datetime.now(UTC)
            s.add(SourceSnapshot(origin="FIXTURE", retrieved_at=now, last_checked_at=now, **d))
            n += 1
        s.commit()
    return n
