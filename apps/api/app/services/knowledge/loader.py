"""Loads and cross-validates the YAML knowledge base. Never raises on content errors."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from app.services.knowledge.schema import (
    SUPPORTED_SCHEMA_VERSIONS,
    AuthoritiesFile,
    BriefingTemplatesFile,
    EscalationRule,
    GlobalEscalationFile,
    IssueDefinition,
    ProfessionalsFile,
    RelatedIssuesFile,
    ScenariosFile,
    SourcesFile,
    StatementPolicyFile,
)
from app.services.referrals.network import ReferralNetwork
from app.services.report.profile import ReportProfileFile
from app.services.rules.conditions import Condition
from app.services.safety.config import SafetySignalsFile


@dataclass
class FileReport:
    path: str  # relative to knowledge base root
    kind: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    version: str | None = None
    content_status: str | None = None
    rule_count: int = 0


@dataclass
class KnowledgeBase:
    root: Path
    issues: dict[str, IssueDefinition] = field(default_factory=dict)
    global_rules: list[EscalationRule] = field(default_factory=list)
    global_rules_loaded: bool = False
    sources: dict[str, Any] = field(default_factory=dict)
    professionals: dict[str, Any] = field(default_factory=dict)
    templates: dict[str, Any] = field(default_factory=dict)
    scenarios: list[Any] = field(default_factory=list)
    authorities: dict[str, Any] = field(default_factory=dict)
    related_issues: dict[str, Any] = field(default_factory=dict)
    forbidden: list[tuple[Any, list[re.Pattern]]] = field(default_factory=list)
    safe_fallback_de: str = "Dazu kann das System keine quellengestützte Aussage machen."
    source_aliases: dict[str, str] = field(default_factory=dict)  # alias id -> canonical id
    files: list[FileReport] = field(default_factory=list)
    cross_errors: list[str] = field(default_factory=list)
    safety_config: Any = None  # knowledge_base/safety/safety_signals.yaml
    referral_network: Any = None  # knowledge_base/referrals/referral_network.yaml
    report_profile: Any = None  # knowledge_base/report/report_profile.yaml
    version: str = "kb-empty"

    def resolve_source_id(self, source_id: str) -> str | None:
        """Canonical id for an id or an alias (None if unknown)."""
        if source_id in self.sources:
            return source_id
        return self.source_aliases.get(source_id)

    @property
    def errors(self) -> list[str]:
        out = [f"{f.path}: {e}" for f in self.files for e in f.errors]
        return out + self.cross_errors

    @property
    def valid(self) -> bool:
        return not self.errors


def _fmt_validation(exc: ValidationError) -> list[str]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"]) or "(root)"
        out.append(f"{loc}: {e['msg']}")
    return out


def _load_yaml(path: Path) -> tuple[Any, str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, f"Ungültiges YAML: {exc}"
    except OSError as exc:
        return None, f"Datei nicht lesbar: {exc}"
    if not isinstance(data, dict):
        return None, "Oberste Ebene muss ein YAML-Mapping sein."
    return data, None


def _parse(kb: KnowledgeBase, path: Path, kind: str, model: type[BaseModel]) -> BaseModel | None:
    rel = path.relative_to(kb.root).as_posix()
    report = FileReport(path=rel, kind=kind, ok=False)
    kb.files.append(report)
    data, err = _load_yaml(path)
    if err:
        report.errors.append(err)
        return None
    sv = data.get("schema_version", 1)
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        report.errors.append(
            f"schema_version {sv!r} nicht unterstützt (erlaubt: {sorted(SUPPORTED_SCHEMA_VERSIONS)})."
        )
        return None
    try:
        obj = model.model_validate(data)
    except ValidationError as exc:
        report.errors.extend(_fmt_validation(exc))
        return None
    report.ok = True
    report.version = str(getattr(obj, "version", "") or "") or None
    report.content_status = getattr(obj, "content_status", None)
    return obj


def _check_dupes(kb: KnowledgeBase, label: str, ids: list[tuple[str, str]]) -> None:
    seen: dict[str, str] = {}
    for ident, where in ids:
        if ident in seen:
            kb.cross_errors.append(
                f"Doppelte {label}-ID '{ident}' in {where} (bereits in {seen[ident]})."
            )
        else:
            seen[ident] = where


def _check_condition_refs(
    kb: KnowledgeBase,
    cond: Condition | None,
    fact_ids: set[str] | None,
    where: str,
    derived_ids: set[str] | None = None,
) -> None:
    if cond is None:
        return
    for ref in cond.refs():
        kind, name = ref.split(".", 1)
        if kind == "derived":
            if derived_ids is None or name not in derived_ids:
                kb.cross_errors.append(f"{where}: unbekannter abgeleiteter Wert '{name}' ({ref}).")
        elif kind == "fact":
            if fact_ids is None:
                kb.cross_errors.append(
                    f"{where}: globale Regeln dürfen keine fact.* referenzieren ({ref})."
                )
            elif name not in fact_ids:
                kb.cross_errors.append(f"{where}: unbekannter Fakt '{name}' in Bedingung ({ref}).")
        elif kind == "issue" and name not in kb.issues:
            kb.cross_errors.append(f"{where}: unbekannte Issue-ID '{name}' in Bedingung ({ref}).")


def canonical_alias(src) -> str | None:
    """CH_OR_ART_266L / CH_OR_ART_273_1 / CH_ZPO_ART_113_2_C ... derived from structured fields."""
    if src.type != "statute" or not (src.statute and src.article):
        return None
    parts = [
        "CH" if src.jurisdiction == "CH" else src.jurisdiction.upper(),
        src.statute.upper(),
        "ART",
        src.article.upper(),
    ]
    para = (src.paragraph or "").lower().replace("abs.", "").replace("abs", "")
    para = para.split("lit")[0].replace("–", "-").replace("—", "-").strip()
    if para:
        parts += [p for p in re.split(r"[-\s]+", para) if p]
    lit = (
        src.letter
        or (
            src.paragraph.lower().split("lit.")[-1].strip()
            if src.paragraph and "lit." in src.paragraph.lower()
            else ""
        )
    ).strip(". ")
    if lit:
        parts.append(lit.upper())
    return "_".join(parts)


def _register_aliases(kb: KnowledgeBase) -> None:
    kb.source_aliases.clear()
    taken: dict[str, str] = {}
    for src in kb.sources.values():
        wanted = list(src.aliases)
        auto = canonical_alias(src)
        if auto and auto != src.id:
            wanted.append(auto)
        # article-only alias (CH_OR_ART_266L) only if the article has exactly ONE source in the KB
        if src.type == "statute" and src.statute and src.article:
            same = [
                o
                for o in kb.sources.values()
                if o.type == "statute" and o.statute == src.statute and o.article == src.article
            ]
            if len(same) == 1:
                wanted.append(f"CH_{src.statute.upper()}_ART_{src.article.upper()}")
        for a in dict.fromkeys(wanted):
            if a in kb.sources:
                kb.cross_errors.append(
                    f"Alias '{a}' von Quelle {src.id} ist bereits eine Quellen-ID."
                )
            elif a in taken and taken[a] != src.id:
                # an automatic alias may legitimately collide (e.g. two sources for the same article range)
                if a in src.aliases or a in kb.sources[taken[a]].aliases:
                    kb.cross_errors.append(f"Alias '{a}' ist mehrdeutig ({taken[a]} / {src.id}).")
                kb.source_aliases.pop(a, None)
            else:
                taken[a] = src.id
                kb.source_aliases[a] = src.id


def _cross_validate(kb: KnowledgeBase) -> None:
    _register_aliases(kb)
    id_list: list[tuple[str, str]] = []
    rule_ids: list[tuple[str, str]] = []
    for issue in kb.issues.values():
        where = f"legal_issues/{issue.id}"
        id_list.append((issue.id, where))
        fact_ids = [f.id for f in issue.facts]
        _check_dupes(kb, f"Fakt in {issue.id}", [(f, where) for f in fact_ids])
        fset = set(fact_ids)
        dset = {d.id for d in issue.derived}
        for d in issue.derived:
            for fid in d.facts:
                if fid not in fset:
                    kb.cross_errors.append(f"{where}.derived.{d.id}: unbekannter Fakt '{fid}'.")
        for f in issue.facts:
            _check_condition_refs(
                kb, f.required_if, fset, f"{where}.facts.{f.id}.required_if", dset
            )
            for sid in f.source_ids:
                if kb.resolve_source_id(sid) is None:
                    kb.cross_errors.append(f"{where}.facts.{f.id}: unbekannte Quelle '{sid}'.")
            for dep in f.depends_on:
                if dep not in fset:
                    kb.cross_errors.append(
                        f"{where}.facts.{f.id}.depends_on: unbekannter Fakt '{dep}'."
                    )
        for r in issue.legal_rules:
            rule_ids.append((r.id, where))
            _check_condition_refs(kb, r.when, fset, f"{where}.legal_rules.{r.id}", dset)
            for s in r.legal_source_ids:
                if kb.resolve_source_id(s) is None:
                    kb.cross_errors.append(f"{where}.legal_rules.{r.id}: unbekannte Quelle '{s}'.")
        for r in issue.escalation_rules:
            rule_ids.append((r.id, where))
            _check_condition_refs(kb, r.when, fset, f"{where}.escalation_rules.{r.id}", dset)
            if (
                r.routes_to_issue
                and r.routes_to_issue not in kb.issues
                and r.routes_to_issue not in kb.related_issues
            ):
                kb.cross_errors.append(
                    f"{where}.escalation_rules.{r.id}: routes_to_issue '{r.routes_to_issue}' ist weder "
                    "ein geladenes Issue noch in routing/related_issues.yaml aufgeführt."
                )
            for p in r.professionals:
                if p not in kb.professionals:
                    kb.cross_errors.append(
                        f"{where}.escalation_rules.{r.id}: unbekannte Fachperson '{p}'."
                    )
        for s in issue.legal_source_ids:
            if kb.resolve_source_id(s) is None:
                kb.cross_errors.append(f"{where}: unbekannte Quelle '{s}'.")
        prof = issue.briefing_profile
        if prof:
            for g in prof.groups:
                for fid in g.fact_ids:
                    if fid not in fset:
                        kb.cross_errors.append(
                            f"{where}.briefing_profile.groups.{g.id}: unbekannter Fakt '{fid}'."
                        )
            for rp in prof.review_points:
                for sid in rp.source_ids:
                    if kb.resolve_source_id(sid) is None:
                        kb.cross_errors.append(
                            f"{where}.briefing_profile.review_points: unbekannte Quelle '{sid}'."
                        )
            for aid in prof.authority_ids:
                if aid not in kb.authorities:
                    kb.cross_errors.append(
                        f"{where}.briefing_profile.authority_ids: unbekannte Stelle '{aid}'."
                    )
        for p in issue.default_professionals:
            if p not in kb.professionals:
                kb.cross_errors.append(f"{where}: unbekannte Fachperson '{p}'.")
        if issue.briefing_template not in kb.templates:
            kb.cross_errors.append(
                f"{where}: Briefing-Vorlage '{issue.briefing_template}' nicht gefunden."
            )
        for rel in issue.classification.related_issues:
            if rel not in kb.issues:
                kb.cross_errors.append(
                    f"{where}: related_issues verweist auf unbekannte ID '{rel}'."
                )
    for r in kb.global_rules:
        rule_ids.append((r.id, "routing/global_escalation"))
        _check_condition_refs(kb, r.when, None, f"routing/global_escalation.rules.{r.id}")
        for p in r.professionals:
            if p not in kb.professionals:
                kb.cross_errors.append(
                    f"global_escalation.rules.{r.id}: unbekannte Fachperson '{p}'."
                )
    _check_dupes(kb, "Regel", rule_ids)
    # Shared fact ids across issues must agree on the data type.
    types: dict[str, tuple[str, str]] = {}
    for issue in kb.issues.values():
        for f in issue.facts:
            if f.id in types and types[f.id][0] != f.data_type:
                kb.cross_errors.append(
                    f"Fakt '{f.id}' hat in {issue.id} Typ '{f.data_type}', "
                    f"in {types[f.id][1]} Typ '{types[f.id][0]}'."
                )
            types.setdefault(f.id, (f.data_type, issue.id))
    _check_text_policy(kb)
    for sc in kb.scenarios:
        for i in sc.issues:
            if i.get("id") not in kb.issues:
                kb.cross_errors.append(
                    f"tests/scenarios {sc.id}: unbekannte Issue-ID '{i.get('id')}'."
                )


def _validate_safety_and_referrals(kb: KnowledgeBase) -> None:
    """Safety patterns must compile; every organisation / category reference must exist (no dangling contacts)."""
    cfg, net = kb.safety_config, kb.referral_network
    if cfg is not None:
        groups = {
            "modifiers": [x for lst in vars(cfg.modifiers).values() for x in lst],
        }
        for c in cfg.categories:
            groups[c.id] = [*c.acute, *c.mention]
        for where, patterns in groups.items():
            for pat in patterns:
                try:
                    re.compile(pat)
                except re.error as exc:
                    kb.cross_errors.append(
                        f"safety_signals.{where}: ungültiger regulärer Ausdruck {pat!r}: {exc}"
                    )
    if net is None:
        if cfg is not None:
            kb.cross_errors.append(
                "safety_signals.yaml ohne referral_network.yaml: Konsequenzen der Kategorien fehlen."
            )
        return
    orgs = {o.id for o in net.professionals}
    roles = set(net.role_resolution)

    def need(ref: str, where: str) -> None:
        if ref not in orgs and ref not in roles:
            kb.cross_errors.append(
                f"referral_network: {where} verweist auf unbekannte Stelle/Rolle '{ref}'."
            )

    for role, table in net.role_resolution.items():
        for key, org_id in table.items():
            if org_id is not None and org_id not in orgs:
                kb.cross_errors.append(
                    f"referral_network.role_resolution.{role}.{key}: unbekannte Stelle '{org_id}'."
                )
    for r in net.safety_routing:
        for ref in [*r.show_to_user, *r.referrals, *r.follow_up_referrals]:
            need(ref, f"safety_routing.{r.category}")
    for rule in net.issue_rules:
        for ref in [*rule.referrals.primary, *rule.referrals.secondary]:
            need(ref, f"issue_rules.{rule.issue_id}")
    if cfg is not None:
        routed = {r.category for r in net.safety_routing}
        for c in cfg.categories:
            if c.id not in routed:
                kb.cross_errors.append(
                    f"safety_signals: Kategorie '{c.id}' fehlt in referral_network.safety_routing."
                )
        known = {c.id for c in cfg.categories}
        for r in net.safety_routing:
            if r.category not in known:
                kb.cross_errors.append(
                    f"safety_routing: Kategorie '{r.category}' hat keine Erkennungsmuster in safety_signals.yaml."
                )


def _validate_report_profile(kb: KnowledgeBase) -> None:
    prof = kb.report_profile
    if prof is None:
        return
    for issue_id, sections in prof.issue_sections.items():
        issue = kb.issues.get(issue_id)
        if issue is None:
            kb.cross_errors.append(f"report_profile: unbekanntes Issue '{issue_id}'.")
            continue
        fact_ids = {f.id for f in issue.facts}
        for sec in sections:
            for row in sec.rows:
                if row.fact_id and row.fact_id not in fact_ids:
                    kb.cross_errors.append(
                        f"report_profile.{issue_id}.{sec.title}: unbekannter Fakt '{row.fact_id}'."
                    )


def _kb_texts(kb: KnowledgeBase):
    """Yield (location, text) for every user-visible text in the knowledge base."""
    for issue in kb.issues.values():
        w = f"legal_issues/{issue.id}"
        for f in issue.facts:
            yield f"{w}.facts.{f.id}.question_de", f.question_de
            yield f"{w}.facts.{f.id}.why_needed_de", f.why_needed_de
        for lr in issue.legal_rules:
            yield f"{w}.legal_rules.{lr.id}.result_de", lr.result_de
        for er in issue.escalation_rules:
            yield f"{w}.escalation_rules.{er.id}.reason_de", er.reason_de
        if issue.briefing_profile:
            for rp in issue.briefing_profile.review_points:
                yield f"{w}.briefing_profile.review_points", rp.text_de
    for er in kb.global_rules:
        yield f"routing/global_escalation.{er.id}.reason_de", er.reason_de


def _check_text_policy(kb: KnowledgeBase) -> None:
    """No knowledge-base text may contain a forbidden statement (Issue 1 dossier, section 6)."""
    for loc, text in _kb_texts(kb):
        for rule, pats in kb.forbidden:
            if any(p.search(text) for p in pats):
                kb.cross_errors.append(
                    f"{loc}: verbotene Aussage ({rule.id}: {rule.description_de}) im Text: {text[:80]!r}"
                )


def _version_hash(root: Path, paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return f"kb-{h.hexdigest()[:10]}"


def load_knowledge_base(root: Path) -> KnowledgeBase:
    root = Path(root)
    kb = KnowledgeBase(root=root)
    if not root.is_dir():
        kb.cross_errors.append(f"Wissensbasis-Verzeichnis nicht gefunden: {root}")
        return kb

    yaml_paths = sorted(p for p in root.rglob("*.yaml") if p.is_file())

    def under(sub: str) -> list[Path]:
        return [p for p in yaml_paths if p.relative_to(root).parts[0] == sub]

    for p in under("referrals"):
        if p.name == "referral_network.yaml":
            obj = _parse(kb, p, "referral_network", ReferralNetwork)
            if obj:
                kb.referral_network = obj
                kb.files[-1].rule_count = len(obj.professionals)  # type: ignore[attr-defined]
            continue
        if p.name == "authorities.yaml":
            obj = _parse(kb, p, "authorities", AuthoritiesFile)
            if obj:
                kb.authorities.update({x.id: x for x in obj.authorities})  # type: ignore[attr-defined]
                kb.files[-1].rule_count = len(obj.authorities)  # type: ignore[attr-defined]
            continue
        obj = _parse(kb, p, "professionals", ProfessionalsFile)
        if obj:
            kb.professionals.update({x.id: x for x in obj.professionals})  # type: ignore[attr-defined]
    for p in under("safety"):
        obj = _parse(kb, p, "safety_signals", SafetySignalsFile)
        if obj:
            kb.safety_config = obj
            kb.files[-1].rule_count = len(obj.categories)  # type: ignore[attr-defined]
    for p in under("report"):
        obj = _parse(kb, p, "report_profile", ReportProfileFile)
        if obj:
            kb.report_profile = obj
            kb.files[-1].rule_count = len(obj.issue_sections)  # type: ignore[attr-defined]
    for p in under("policies"):
        obj = _parse(kb, p, "statement_policy", StatementPolicyFile)
        if obj:
            kb.safe_fallback_de = obj.safe_fallback_de  # type: ignore[attr-defined]
            for rule in obj.forbidden:  # type: ignore[attr-defined]
                try:
                    kb.forbidden.append(
                        (rule, [re.compile(x, re.IGNORECASE) for x in rule.patterns])
                    )
                except re.error as exc:
                    kb.files[-1].ok = False
                    kb.files[-1].errors.append(
                        f"forbidden.{rule.id}: ungültiger regulärer Ausdruck: {exc}"
                    )
            kb.files[-1].rule_count = len(obj.forbidden)  # type: ignore[attr-defined]
    for p in under("routing"):
        if p.name == "related_issues.yaml":
            obj = _parse(kb, p, "related_issues", RelatedIssuesFile)
            if obj:
                kb.related_issues.update({x.id: x for x in obj.related_issues})  # type: ignore[attr-defined]
                kb.files[-1].rule_count = len(obj.related_issues)  # type: ignore[attr-defined]
    for p in under("legal_sources"):
        obj = _parse(kb, p, "sources", SourcesFile)
        if obj:
            kb.sources.update({x.id: x for x in obj.sources})  # type: ignore[attr-defined]
    for p in under("briefings"):
        obj = _parse(kb, p, "briefing_templates", BriefingTemplatesFile)
        if obj:
            kb.templates.update({x.id: x for x in obj.templates})  # type: ignore[attr-defined]
    for p in under("legal_issues"):
        obj = _parse(kb, p, "legal_issue", IssueDefinition)
        if obj:
            issue: IssueDefinition = obj  # type: ignore[assignment]
            if issue.id in kb.issues:
                kb.cross_errors.append(f"Doppelte Issue-ID '{issue.id}' ({p.name}).")
                continue
            kb.issues[issue.id] = issue
            rep = kb.files[-1]
            rep.rule_count = len(issue.legal_rules) + len(issue.escalation_rules)
    for p in under("routing"):
        if p.name == "related_issues.yaml":
            continue
        obj = _parse(kb, p, "global_escalation", GlobalEscalationFile)
        if obj:
            kb.global_rules.extend(obj.rules)  # type: ignore[attr-defined]
            kb.global_rules_loaded = True
            kb.files[-1].rule_count = len(obj.rules)  # type: ignore[attr-defined]
    for p in under("tests"):
        obj = _parse(kb, p, "scenarios", ScenariosFile)
        if obj:
            kb.scenarios.extend(obj.scenarios)  # type: ignore[attr-defined]
            kb.files[-1].rule_count = len(obj.scenarios)  # type: ignore[attr-defined]

    _cross_validate(kb)
    _validate_safety_and_referrals(kb)
    _validate_report_profile(kb)
    kb.version = _version_hash(root, yaml_paths)
    return kb
