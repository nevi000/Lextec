"""Schema of knowledge_base/report/report_profile.yaml (which key data the report's first page shows)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PersonField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str


class ProfileRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    fact_id: str | None = None  # None = not captured by LexTec Bridge: shown as "nicht erfasst"


class ProfileSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    rows: list[ProfileRow]


class ReportProfileFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    version: str
    content_status: str | None = None
    person_fields: list[PersonField] = []
    issue_sections: dict[str, list[ProfileSection]] = {}
