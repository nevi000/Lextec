"""Pydantic models for every YAML file in the knowledge base (schema_version 1)."""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.rules.conditions import Condition

SUPPORTED_SCHEMA_VERSIONS = {1}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ISSUE_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SOURCE_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

ContentStatus = Literal["DEMO_SYNTHETIC", "DRAFT", "LEGALLY_REVIEWED"]
Priority = Literal["high", "medium", "low"]
DataType = Literal["string", "boolean", "date", "integer", "enum"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactDef(Strict):
    id: str
    label_de: str
    description: str = ""
    data_type: DataType = "string"
    enum_values: list[str] = []
    required: bool = False
    required_if: Condition | None = None
    priority: Priority = "medium"
    question_de: str
    why_needed_de: str = ""
    # --- optional richer modelling (all backward compatible) ---
    group: str = ""  # e.g. "prescreening"; used by the issue-specific briefing
    enum_labels_de: dict[str, str] = {}  # enum value -> label shown to the social worker
    extraction_hint_de: str = ""  # guidance for the AI extractor (what counts / what does not)
    source_ids: list[str] = []  # legal sources behind the relevance of this fact
    depends_on: list[str] = []  # informational: facts this one depends on (see also required_if)
    escalation_relevant: bool = False  # informational: some escalation rule reads this fact
    # shown next to a «ja» answer that leaves the details open (e.g. «reagiert: ja» but not how)
    true_value_note_de: str = ""
    # value for the expert (not legal necessity); only orders questions AFTER an escalation
    handover_priority: Literal["high", "normal"] = "normal"
    store_evidence: bool = (
        True  # false: the verbatim quote is NOT persisted (e.g. health details; no diagnoses)
    )

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError("Fakt-ID muss snake_case sein (a-z, 0-9, _).")
        return v

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.data_type == "enum" and not self.enum_values:
            raise ValueError("data_type 'enum' braucht enum_values.")
        if self.data_type != "enum" and self.enum_values:
            raise ValueError("enum_values nur bei data_type 'enum' erlaubt.")
        extra = set(self.enum_labels_de) - set(self.enum_values)
        if extra:
            raise ValueError(f"enum_labels_de enthält unbekannte Werte: {sorted(extra)}")
        if self.required and self.required_if is not None:
            raise ValueError("'required: true' und 'required_if' schliessen sich aus.")
        return self


class LegalRule(Strict):
    """A controlled, source-bound statement (HINT) or a review pointer for the expert (REVIEW_POINT).

    Every rule must cite at least one source: no statement without a source."""

    id: str
    description: str
    when: Condition
    kind: Literal["HINT", "REVIEW_POINT"] = "REVIEW_POINT"
    result_code: str
    result_de: str
    legal_source_ids: list[str]

    @field_validator("legal_source_ids")
    @classmethod
    def _needs_source(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError(
                "Jede rechtliche Aussage braucht mindestens eine Quelle (legal_source_ids)."
            )
        return v


class EscalationRule(Strict):
    id: str
    description: str
    when: Condition
    action: Literal["ESCALATE"] = "ESCALATE"
    urgency: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    reason_code: str
    reason_de: str
    professionals: list[str] = []
    # Hand over to a related issue (e.g. payment default -> Issue 3). Availability is checked at
    # decision time: only an issue that is loaded AND LEGALLY_REVIEWED counts as available.
    routes_to_issue: str | None = None
    # Case is outside the module: standard statements/legal findings of this issue are suppressed.
    suppress_standard_statements: bool = False


class Classification(Strict):
    description: str = ""
    typical_situations: list[str] = []
    related_issues: list[str] = []


class DerivedDef(Strict):
    """A value computed by the engine from KNOWN date facts. Used for INTERNAL urgency assessment
    only - never to state a deadline end date."""

    id: str
    kind: Literal["days_since_earliest", "days_until"]
    facts: list[str]
    description: str = ""

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError("Derived-ID muss snake_case sein.")
        return v


class BriefingGroup(Strict):
    id: str
    title_de: str
    fact_ids: list[str]


class ReviewPoint(Strict):
    text_de: str
    source_ids: list[str] = []


class BriefingProfile(Strict):
    """Issue-specific layout of the briefing (the generic 11 sections stay as they are)."""

    intro_de: str = ""
    groups: list[BriefingGroup] = []
    review_points: list[ReviewPoint] = []
    documents_to_request: list[str] = []
    authority_ids: list[str] = []


class IssueDefinition(Strict):
    schema_version: int = 1
    id: str
    version: str
    content_status: ContentStatus = "DRAFT"
    jurisdiction: str = "CH"
    legal_area: str
    issue: str
    title_de: str
    description: str = ""
    classification: Classification = Classification()
    facts: list[FactDef] = []
    legal_rules: list[LegalRule] = []
    escalation_rules: list[EscalationRule] = []
    legal_source_ids: list[str] = []
    default_professionals: list[str] = []
    briefing_template: str = "expert_briefing_v1"
    canton: str | None = None  # primary canton, e.g. "ZH"
    derived: list[DerivedDef] = []
    briefing_profile: BriefingProfile | None = None
    # Free-text documentation of the origin of the content (dossier, version). Not machine-used.
    provenance_de: str = ""

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not ISSUE_ID_PATTERN.match(v):
            raise ValueError("Issue-ID darf nur Buchstaben, Ziffern und _ enthalten.")
        return v


class GlobalEscalationFile(Strict):
    schema_version: int = 1
    version: str
    content_status: ContentStatus = "DRAFT"
    rules: list[EscalationRule] = []


DossierStatus = Literal["DOSSIER_CHECKED", "DOSSIER_PENDING", "REFERENCED_ONLY"]


class InterpretationReview(Strict):
    """Law-team review of how a source is USED (interpretation), independent of the wording check.
    Without an entry the interpretation counts as NOT reviewed."""

    status: Literal["NOT_REVIEWED", "REVIEWED"] = "NOT_REVIEWED"
    reviewed_by: str | None = None
    reviewed_at: str | None = None  # ISO date
    note: str | None = None

    @model_validator(mode="after")
    def _reviewed_needs_proof(self) -> Self:
        if self.status == "REVIEWED" and not (self.reviewed_by and self.reviewed_at):
            raise ValueError("status REVIEWED braucht reviewed_by und reviewed_at.")
        return self


class SourceDef(Strict):
    """A legal source.

    Two DIFFERENT statuses, never to be confused:
    * ``dossier_status``      - what the law team's dossier states (checked against their uploaded
                                 PDFs / full texts, or still pending, or only mentioned without text).
    * ``verification_status`` - live verification BY THIS SYSTEM (e.g. via Fedlex). Stays UNVERIFIED
                                 until such a mechanism really exists and ran."""

    id: str
    aliases: list[str] = []  # additional ids that resolve to this source (e.g. CH_OR_ART_266L)
    jurisdiction: str = "CH"
    provider: Literal["fedlex", "entscheidsuche", "bger", "other"] = "fedlex"
    type: Literal["statute", "case_law", "other"] = "statute"
    sr_number: str | None = None
    statute: str | None = None  # e.g. "OR", "ZPO"
    article: str | None = None
    paragraph: str | None = None  # "1", "Abs. 1", "Abs. 1-2", "Abs. 1-2 lit. c"
    letter: str | None = None  # "c" (alternative to "lit. c" inside paragraph)
    fedlex_sync: bool = True  # set false to exclude a statute source from the Fedlex sync
    interpretation_review: InterpretationReview = InterpretationReview()
    language: str = "de"
    title_de: str
    text_de: str | None = None  # wording as given in the dossier (may be abridged by the dossier)
    legal_question_de: str | None = None
    valid_as_of: str | None = None  # version date of the wording, e.g. "2026-10-01"
    origin_ref: str | None = None  # where the dossier took it from, e.g. "OR_admin.pdf S. 76"
    dossier_status: DossierStatus = "DOSSIER_PENDING"
    verification_status: Literal["VERIFIED", "UNVERIFIED", "FAILED"] = "UNVERIFIED"
    # --- case law only ---
    citation: str | None = None  # e.g. "BGE 140 III 244"
    case_number: str | None = None  # e.g. "4A_120/2014"
    decision_date: str | None = None  # ISO date
    considerations: list[str] = []  # cited Erwägungen with page, as in the dossier
    core_statement_de: str | None = None
    scope_de: str | None = None
    limits_de: str | None = None
    relevant_fact_ids: list[str] = []
    url: str | None = None  # only if provided by the dossier / verified

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SOURCE_ID_PATTERN.match(v):
            raise ValueError("Quellen-ID muss UPPER_SNAKE_CASE sein.")
        return v


class AuthorityDef(Strict):
    """A body/office the social worker can refer to. Contact data and costs are NEVER presented
    as current unless ``contact_verified`` is true (with ``verified_at``)."""

    id: str
    name_de: str
    purpose_de: str
    cost_de: str = ""  # as stated in the dossier
    scope_de: str = ""  # who/where it applies to
    source_note_de: str = ""
    url_hint: str | None = None  # as mentioned in the dossier; unverified
    contact_verified: bool = False
    verified_at: str | None = None

    @model_validator(mode="after")
    def _verified_needs_date(self) -> Self:
        if self.contact_verified and not self.verified_at:
            raise ValueError("contact_verified=true braucht verified_at (Datum der Prüfung).")
        return self


class AuthoritiesFile(Strict):
    schema_version: int = 1
    version: str
    content_status: ContentStatus = "DRAFT"
    authorities: list[AuthorityDef] = []


class RelatedIssueDef(Strict):
    id: str
    title_de: str
    issue_number: int | None = None
    status: Literal["PLANNED"] = "PLANNED"


class RelatedIssuesFile(Strict):
    """Issues that are referred to but may not be implemented yet."""

    schema_version: int = 1
    version: str
    related_issues: list[RelatedIssueDef] = []


class ForbiddenStatementDef(Strict):
    id: str
    description_de: str
    patterns: list[str]  # regular expressions (case-insensitive) that must NOT occur in output text
    reason_de: str = ""
    source_ids: list[str] = []


class StatementPolicyFile(Strict):
    schema_version: int = 1
    version: str
    content_status: ContentStatus = "DRAFT"
    safe_fallback_de: str = "Dazu kann das System keine quellengestützte Aussage machen. Bitte eine Fachperson beiziehen."
    forbidden: list[ForbiddenStatementDef] = []


class SourcesFile(Strict):
    schema_version: int = 1
    version: str
    content_status: ContentStatus = "DRAFT"
    sources: list[SourceDef] = []


class ProfessionalDef(Strict):
    id: str
    label_de: str
    description_de: str = ""


class ProfessionalsFile(Strict):
    schema_version: int = 1
    version: str
    content_status: ContentStatus = "DRAFT"
    professionals: list[ProfessionalDef] = []


class BriefingTemplateDef(Strict):
    id: str
    title_de: str
    sections: list[str]


class BriefingTemplatesFile(Strict):
    schema_version: int = 1
    version: str
    templates: list[BriefingTemplateDef] = []


class ScenarioDef(Strict):
    id: str
    title_de: str
    validation: Literal["SYNTHETIC_TECHNICAL", "LEGALLY_VALIDATED"] = "SYNTHETIC_TECHNICAL"
    has_user_input: bool = True
    issues: list[dict] = Field(default_factory=list)  # {id, confidence?}
    unsupported_issues: list[str] = []
    facts: dict[str, str | bool | int | None] = Field(default_factory=dict)
    unknown_facts: list[str] = []  # facts that were asked but are unknown (status UNKNOWN)
    today: str | None = None  # ISO date used for derived values (default: 2026-11-07)
    expected_urgency: Literal["HIGH", "MEDIUM", "LOW"] | None = None  # highest urgency expected
    expected_not_rule_ids: list[str] = []
    expected_route_issue_ids: list[str] = []
    expected_action: Literal["ASK", "PROCEED", "ESCALATE"]
    expected_rule_ids: list[str] = []
    expected_reason_codes: list[str] = []
    expected_missing_facts: list[str] = []


class ScenariosFile(Strict):
    schema_version: int = 1
    version: str
    scenarios: list[ScenarioDef] = []
