"""Developer CLI.

python -m app.cli migrate           apply Alembic migrations
python -m app.cli seed-demo         create synthetic demo cases (always uses the MOCK AI)
python -m app.cli export-schemas    write JSON Schemas for the YAML files to ./schemas
python -m app.cli validate-kb       alias of `python -m app.services.knowledge.cli`
    python -m app.cli live-test --confirm   ONE real Gemini call (isolated, limited, no retry)
    python -m app.cli fedlex <sync|verify|status|map-inputs|live-test|seed-fixtures>   see fedlex/cli.py
"""

from __future__ import annotations

import json
import sys

from app.core.config import REPO_ROOT, get_settings
from app.db.session import make_engine, make_session_factory
from app.domain.enums import MessageKind
from app.main import run_migrations
from app.services.ai.mock import MockAIProvider
from app.services.cases.service import CaseService
from app.services.knowledge.loader import load_knowledge_base
from app.services.knowledge.schema import (
    AuthoritiesFile,
    BriefingTemplatesFile,
    GlobalEscalationFile,
    IssueDefinition,
    ProfessionalsFile,
    RelatedIssuesFile,
    ScenariosFile,
    SourcesFile,
    StatementPolicyFile,
)

FIXTURES = REPO_ROOT / "demo_fixtures" / "demo_cases.json"
SCHEMAS = {
    "issue_definition.schema.json": IssueDefinition,
    "global_escalation.schema.json": GlobalEscalationFile,
    "sources.schema.json": SourcesFile,
    "professionals.schema.json": ProfessionalsFile,
    "briefing_templates.schema.json": BriefingTemplatesFile,
    "scenarios.schema.json": ScenariosFile,
    "authorities.schema.json": AuthoritiesFile,
    "related_issues.schema.json": RelatedIssuesFile,
    "statement_policy.schema.json": StatementPolicyFile,
}


def cmd_migrate() -> int:
    run_migrations(get_settings().database_url)
    print("Datenbank ist auf dem neuesten Stand.")
    return 0


def cmd_seed_demo() -> int:
    settings = get_settings()
    run_migrations(settings.database_url)
    kb = load_knowledge_base(settings.knowledge_base_dir)
    factory = make_session_factory(make_engine(settings.database_url))
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    created = 0
    with factory() as session:
        svc = CaseService(session, kb, MockAIProvider())
        for spec in cases:
            case = svc.create_case(spec.get("title", ""))
            for m in spec["messages"]:
                kind = "ANSWER" if m.get("answers_fact_id") else "DESCRIPTION"
                svc.add_message(case.id, m["content"], MessageKind(kind), m.get("answers_fact_id"))
                state = svc.analyze_pending(case.id)
                if state.status != "OK":
                    print(f"  Analyse fehlgeschlagen: {state.error_message}")
            session.refresh(case)
            print(f"  {case.display_id}: {case.title} -> {case.current_action}")
            created += 1
    print(f"{created} synthetische Demo-Fälle angelegt (Mock-KI, keine externen Aufrufe).")
    return 0


def cmd_export_schemas() -> int:
    out = REPO_ROOT / "schemas"
    out.mkdir(exist_ok=True)
    for name, model in SCHEMAS.items():
        (out / name).write_text(
            json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  schemas/{name}")
    return 0


LIVE_TEXT = (
    "Ich betreue eine Klientin in Zürich. Sie hat von ihrem Vermieter die Kündigung für ihre Wohnung "
    "erhalten und weiss nicht, ob sie ausziehen muss. Die Klientin ist alleinige Mieterin einer normalen "
    "Wohnung in der Stadt Zürich, der Vertrag ist unbefristet. Die Kündigung hat sie am 4. November 2026 mit "
    "normaler Post erhalten, nur ein gewöhnlicher Brief ohne amtliches Kündigungsformular. Die Kündigung soll "
    "per 31. Januar 2027 gelten."
)


def cmd_live_test(args: list[str]) -> int:
    """Exactly ONE real Gemini request through the normal cost gate. Never loops, never retries."""
    from uuid import uuid4

    from app.services.ai.base import CallContext
    from app.services.ai.gemini import GeminiProvider
    from app.services.ai.schemas import (
        ExtractionInput,
        FactCatalogEntry,
        InputMessage,
        IssueCatalogEntry,
    )
    from app.services.ai.usage import UsageGate, estimate_tokens
    from app.services.ai.validation import validate_extraction

    if "--confirm" not in args:
        print(
            "Dies löst EINEN echten, kostenpflichtigen Gemini-Aufruf aus. Mit --confirm bestätigen."
        )
        return 2
    settings = get_settings()
    if settings.ai_provider != "gemini" or settings.gemini_api_key is None:
        print(
            "AI_PROVIDER=gemini und GEMINI_API_KEY sind nötig (aus .env). Abbruch, nichts gesendet."
        )
        return 2
    run_migrations(settings.database_url)
    settings = settings.model_copy(update={"ai_max_retries": 0})  # one call, no retry
    kb = load_knowledge_base(settings.knowledge_base_dir)
    factory = make_session_factory(make_engine(settings.database_url))
    gate = UsageGate(factory, settings)
    before = gate.summary()
    print(
        f"Modell: {settings.gemini_model} | heute bisher: {before['calls_today']} Aufrufe | "
        f"Limits: {before['daily_request_limit']}/Tag, ${before['daily_budget_usd']}/Tag"
    )

    mid = str(uuid4())
    seen: dict[str, FactCatalogEntry] = {}
    for d in kb.issues.values():
        for f in d.facts:
            seen.setdefault(
                f.id,
                FactCatalogEntry(
                    id=f.id,
                    label_de=f.label_de,
                    data_type=f.data_type,
                    enum_values=f.enum_values,
                    enum_labels_de=f.enum_labels_de,
                    hint_de=f.extraction_hint_de,
                    question_de=f.question_de,
                ),
            )
    data = ExtractionInput(
        new_messages=[InputMessage(id=mid, kind="DESCRIPTION", content=LIVE_TEXT)],
        issue_catalog=[
            IssueCatalogEntry(
                id=d.id,
                title_de=d.title_de,
                description=d.classification.description or d.description,
                typical_situations=d.classification.typical_situations,
            )
            for d in kb.issues.values()
        ],
        fact_catalog=list(seen.values()),
        today="2026-11-07",
    )
    prov = GeminiProvider(settings, gate)
    print(
        f"Geschätzte Eingabe-Tokens (lokal, konservativ): ~{estimate_tokens(data.model_dump_json())}"
    )
    try:
        raw = prov.extract(data, CallContext(None, "live_test"))
    except Exception as exc:  # report, never retry
        print(f"FEHLER ({type(exc).__name__}): {getattr(exc, 'message', exc)}")
        after = gate.summary()
        print(f"Aufrufe heute: {after['calls_today']} (davor {before['calls_today']})")
        return 1
    v = validate_extraction(raw, kb, {mid: LIVE_TEXT})
    print("\nErkannte Rechtsgebiete:", [(i.issue_id, i.confidence) for i in v.issues])
    print("Nicht abgedeckt:", [u.description for u in v.unsupported])
    print("Fakten (nach Validierung):")
    for ef, typed in v.facts:
        state = "unklar" if ef.ambiguous else ("unbekannt" if ef.unknown else repr(typed))
        print(f"  {ef.fact_id:32} = {state:24} Beleg: {ef.evidence_quote!r}")
    print("Warnungen der Validierung:", v.warnings or "keine")
    print("Zusammenfassung:", raw.summary_de)
    last = gate.recent(1)[0]
    after = gate.summary()
    print(
        f"\nTokens: Eingabe {last.input_tokens}, Ausgabe {last.output_tokens}, Denken {last.thinking_tokens}, "
        f"gesamt {last.total_tokens}"
    )
    print(
        f"Geschätzte Kosten dieses Aufrufs: ${last.cost_usd:.6f}"
        if last.cost_usd is not None
        else "Kosten unbekannt"
    )
    print(
        f"Aufrufe heute: {after['calls_today']} | geschätzte Tageskosten: ${after['estimated_cost_today_usd']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else ""
    if cmd == "migrate":
        return cmd_migrate()
    if cmd == "seed-demo":
        return cmd_seed_demo()
    if cmd == "export-schemas":
        return cmd_export_schemas()
    if cmd == "fedlex":
        from app.services.sources.fedlex.cli import main as fedlex_main

        return fedlex_main(args[1:])
    if cmd == "live-test":
        return cmd_live_test(args[1:])
    if cmd == "validate-kb":
        from app.services.knowledge.cli import main as kb_main

        return kb_main(args[1:])
    print(__doc__)
    return 2 if cmd else 0


if __name__ == "__main__":
    raise SystemExit(main())
