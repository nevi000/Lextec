"""Targeted live integration test against the REAL Fedlex endpoint (a handful of requests).

Runs in a throw-away database so it never touches the real cache. A success here means a real retrieval; it is
never confused with fixture-based unit tests.
"""

from __future__ import annotations

import copy
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import make_engine, make_session_factory
from app.models.tables import SourceSnapshot
from app.services.knowledge.loader import KnowledgeBase
from app.services.knowledge.schema import SourceDef
from app.services.sources.fedlex.http import FedlexHttp
from app.services.sources.fedlex.provider import CachedFedlexProvider
from app.services.sources.fedlex.service import FedlexService

# (test id, KB source to compare with, structured reference under test)
CASES = [
    ("A", "CH_OR_266L", dict(sr_number="220", statute="OR", article="266l", paragraph=None)),
    ("B", "CH_OR_273_1", dict(sr_number="220", statute="OR", article="273", paragraph="Abs. 1")),
    (
        "C",
        "CH_ZPO_113",
        dict(sr_number="272", statute="ZPO", article="113", paragraph="Abs. 2 lit. c"),
    ),
]


def run_live_test(settings: Settings, kb: KnowledgeBase, _real_sf: sessionmaker[Session]) -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        engine = make_engine(f"sqlite:///{(Path(tmp) / 'livetest.db').as_posix()}")
        Base.metadata.create_all(engine)
        sf = make_session_factory(engine)

        test_kb = copy.copy(kb)
        test_kb.sources = dict(kb.sources)
        test_kb.source_aliases = {}
        for tid, kb_id, ref in CASES:
            base = kb.sources[kb_id]
            # compare the test reference against the dossier wording of the matching KB source
            test_kb.sources[f"LIVE_{tid}"] = SourceDef(
                id=f"LIVE_{tid}",
                provider="fedlex",
                type="statute",
                title_de=base.title_de,
                text_de=base.text_de,
                valid_as_of=base.valid_as_of,
                **ref,
            )
        test_kb.sources["LIVE_NEG"] = SourceDef(
            id="LIVE_NEG",
            provider="fedlex",
            type="statute",
            sr_number="220",
            statute="OR",
            article="266zz",
            title_de="Nicht existierender Artikel (Negativprobe)",
        )

        http = FedlexHttp(settings)
        svc = FedlexService(sf, settings, test_kb, http)
        ref = settings.app_today or date.today()
        print(
            f"Live test against {settings.fedlex_sparql_url} (reference date {ref}, language {settings.fedlex_language})\n"
        )
        rep = svc.sync([f"LIVE_{t}" for t, _, _ in CASES] + ["LIVE_NEG"], ref, force=True)
        provider = CachedFedlexProvider(sf, settings, test_kb, ref)
        ok = True
        for tid, _kb_id, ref_spec in CASES:
            info = provider.info(f"LIVE_{tid}")
            res = next(r for r in rep.results if r.source_id == f"LIVE_{tid}")
            print(f"== Test {tid}: {info.article_label or ref_spec['article']}  [{res.status}]")
            if res.status != "RETRIEVED":
                print(f"   FAILED: {res.message}\n")
                ok = False
                continue
            with sf() as s:
                stored = s.query(SourceSnapshot).filter_by(source_id=f"LIVE_{tid}").count()
            checks = {
                "law found": bool(info.law_abbreviation),
                "language de": info.language == "de",
                "article label matches": (info.article_label or "").startswith(
                    f"Art. {ref_spec['article']}"
                ),
                "official text present": bool(info.official_text),
                "official document URL (fedlex.data.admin.ch)": (
                    info.official_document_url or ""
                ).startswith("https://fedlex.data.admin.ch/filestore/"),
                "version + validity": bool(info.version_identifier and info.valid_from),
                "stored locally": stored == 1,
                "wording vs. knowledge base": info.wording_status == "MATCHED",
            }
            for k, v in checks.items():
                print(f"   [{'ok' if v else 'FAIL'}] {k}")
                ok &= v
            print(f"   law:      {info.law_abbreviation} - {(info.law_title or '')[:70]}")
            print(
                f"   version:  {info.version_identifier} valid {info.valid_from} .. {info.valid_to or 'open'}"
            )
            print(f"   eli:      {info.official_eli_uri}")
            print(f"   document: {info.official_document_url}")
            print(
                f"   article:  {info.official_article_url}  (viewer deep link, anchor not auto-verified)"
            )
            print(f"   official text: {info.official_text}")
            print(f"   hash: {info.content_hash}\n")
        neg = next(r for r in rep.results if r.source_id == "LIVE_NEG")
        neg_ok = neg.status == "NOT_FOUND"
        print(
            f"== Negative test (Art. 266zz OR): {neg.status} -> {'ok, nothing invented' if neg_ok else 'UNEXPECTED'}"
        )
        ok &= neg_ok
        print(
            f"\nReal network requests: {rep.requests} | result: {'ALL CHECKS PASSED' if ok else 'PROBLEMS FOUND'}"
        )
        http.close()
        engine.dispose()
        return 0 if ok else 1
