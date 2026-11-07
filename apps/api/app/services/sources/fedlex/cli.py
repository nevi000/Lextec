"""`python -m app.cli fedlex <command>` - deterministic Fedlex tooling (no LLM, no API key).

fedlex sync   [--issue ID | --all-referenced | --source ID ...] [--date YYYY-MM-DD] [--as-of-dossier]
              [--force] [--offline]
fedlex verify [--issue ID | --all-referenced]        offline: re-compare wording with the stored snapshots
fedlex status [--issue ID]                           what is stored, how old, which statuses
fedlex map-inputs [--check]                          map the law team's YAML references to source ids
fedlex live-test                                     3 real articles (OR 266l, OR 273 Abs. 1, ZPO 113 Abs. 2 lit. c)
fedlex seed-fixtures                                 load TEST fixtures (labelled FIXTURE, never "verified")
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.session import make_engine, make_session_factory
from app.main import run_migrations
from app.models.tables import SourceSnapshot
from app.services.knowledge.loader import load_knowledge_base
from app.services.sources.fedlex.provider import CachedFedlexProvider
from app.services.sources.fedlex.service import FedlexService, SyncReport, is_fedlex_statute


def _setup(settings: Settings | None = None):
    settings = settings or get_settings()
    run_migrations(settings.database_url)
    kb = load_knowledge_base(settings.knowledge_base_dir)
    sf = make_session_factory(make_engine(settings.database_url))
    return settings, kb, sf


def print_report(title: str, rep: SyncReport) -> None:
    n = len(rep.results)
    print(f"\n{title}\n")
    print(f"Referenced sources:        {n}")
    print(f"  Retrieved from Fedlex:   {rep.count('RETRIEVED')}")
    print(f"  Served from cache:       {rep.count('CACHED')}")
    print(f"  Skipped (not Fedlex law):{rep.count('SKIPPED')}")
    print(f"  Failed / not available:  {len(rep.failed)}")
    print(f"Network requests:          {rep.requests}{'  (offline mode)' if rep.offline else ''}")
    print(f"Reference date:            {rep.reference_date}\n")
    for r in rep.results:
        if r.status == "SKIPPED":
            continue
        ver = f" v{r.version_identifier}" if r.version_identifier else ""
        wording = f" | wording: {r.wording_status}" if r.wording_status else ""
        newer = f" | newer version exists: {r.newer_version}" if r.newer_version else ""
        print(f"  [{r.status:<18}] {r.source_id:<18} {r.label}{ver}{wording}{newer}")
        if r.status not in ("RETRIEVED", "CACHED"):
            print(f"        -> {r.message}")
    print(
        "\nSource retrieval and wording comparison completed. Legal INTERPRETATION is verified separately."
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="app.cli fedlex", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("sync", "verify", "status"):
        p = sub.add_parser(name)
        p.add_argument("--issue")
        p.add_argument("--all-referenced", action="store_true")
        p.add_argument("--source", action="append", default=[])
        if name == "sync":
            p.add_argument("--date", help="reference date (default: APP_TODAY or today)")
            p.add_argument(
                "--as-of-dossier", action="store_true", help="use each source's valid_as_of date"
            )
            p.add_argument("--force", action="store_true")
            p.add_argument("--offline", action="store_true")
    mp = sub.add_parser("map-inputs")
    mp.add_argument("--check", action="store_true", help="also check existence at Fedlex (network)")
    sub.add_parser("live-test")
    sub.add_parser("seed-fixtures")
    args = ap.parse_args(argv)

    settings, kb, sf = _setup()
    svc = FedlexService(sf, settings, kb)

    def ids() -> list[str]:
        if args.source:
            return args.source
        if args.issue:
            return svc.collect_issue_sources(args.issue)
        return svc.all_referenced_sources()

    if args.cmd == "sync":
        ref = date.fromisoformat(args.date) if args.date else (settings.app_today or date.today())
        title = f"Issue: {args.issue}" if args.issue else "All referenced statutes"
        rep = svc.sync(
            ids(), ref, force=args.force, offline=args.offline, as_of_dossier=args.as_of_dossier
        )
        print_report(title, rep)
        return 1 if rep.failed else 0

    if args.cmd == "verify":
        results = svc.reverify(ids())
        rep = SyncReport(date.today().isoformat(), results, 0, True)
        print_report("Offline wording verification against stored snapshots", rep)
        return 0

    if args.cmd == "status":
        provider = CachedFedlexProvider(sf, settings, kb)
        print(
            f"{'source':<20}{'retrieval':<20}{'wording':<20}{'origin':<9}{'version':<10}{'age(d)':<7}label"
        )
        for sid in ids():
            src = kb.sources.get(sid)
            if src is None or not is_fedlex_statute(src):
                continue
            i = provider.info(sid)
            print(
                f"{sid:<20}{i.retrieval_status:<20}{i.wording_status:<20}{i.origin:<9}"
                f"{(i.version_identifier or '-'):<10}{str(i.cache_age_days if i.cache_age_days is not None else '-'):<7}"
                f"{i.article_label or ''}"
            )
        with sf() as s:
            n = len(list(s.scalars(select(SourceSnapshot.id))))
        print(f"\n{n} snapshot(s) stored (older versions are kept).")
        return 0

    if args.cmd == "map-inputs":
        from app.services.sources.fedlex.inputs import run_map_inputs

        return run_map_inputs(settings, kb, sf, check=args.check)

    if args.cmd == "live-test":
        from app.services.sources.fedlex.livetest import run_live_test

        return run_live_test(settings, kb, sf)

    if args.cmd == "seed-fixtures":
        from app.services.sources.fedlex.fixtures import seed_fixtures

        print(
            f"{seed_fixtures(sf, kb)} fixture snapshot(s) loaded (origin FIXTURE; not a Fedlex retrieval)."
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
