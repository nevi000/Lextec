"""Fedlex catalog access via the official SPARQL endpoint (JOLux ontology) and version selection.

Data model (verified against the live endpoint and https://swiss.github.io/fedlex-jolux/):
* ``jolux:ConsolidationAbstract`` = the statute over time; its SR number is ``jolux:historicalLegalId``.
  ``jolux:dateEntryInForce`` / ``jolux:dateNoLongerInForce`` bound the life of the statute.
  Its Expression per language (``<abstract>/de``) carries ``jolux:title`` and ``jolux:titleShort``.
* ``jolux:Consolidation`` = one version (``jolux:isMemberOf`` the abstract) with the validity period
  ``jolux:dateApplicability`` .. ``jolux:dateEndApplicability`` (end missing = open ended; a version can
  be published before it is in force).
* Consolidation -> ``jolux:isRealizedBy`` Expression (``jolux:language``) -> ``jolux:isEmbodiedBy``
  Manifestation (``jolux:userFormat``) -> ``jolux:isExemplifiedBy`` file URL.

Note (verified): a SPARQL variable named ``?from`` makes the gateway answer 400 - avoid reserved words.
Only validated public identifiers are ever interpolated into a query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.services.sources.fedlex.http import FedlexBadResponse, FedlexHttp
from app.services.sources.fedlex.reference import SR_PATTERN

JOLUX = "http://data.legilux.public.lu/resource/ontology/jolux#"
LANG_URI = {
    "de": "http://publications.europa.eu/resource/authority/language/DEU",
    "fr": "http://publications.europa.eu/resource/authority/language/FRA",
    "it": "http://publications.europa.eu/resource/authority/language/ITA",
    "en": "http://publications.europa.eu/resource/authority/language/ENG",
    "rm": "http://publications.europa.eu/resource/authority/language/ROH",
}
XML_FORMAT = "https://fedlex.data.admin.ch/vocabulary/user-format/xml"
ELI_CC = re.compile(r"^https://fedlex\.data\.admin\.ch/eli/cc/[A-Za-z0-9_/\-]+$")
PREFIX = f"PREFIX jolux: <{JOLUX}>\n"


@dataclass(frozen=True)
class LawCandidate:
    abstract_uri: str
    entry_in_force: str | None
    no_longer_in_force: str | None
    abbreviation: str | None
    title: str | None


@dataclass(frozen=True)
class LawVersion:
    uri: str  # consolidation URI, ends with the version identifier (YYYYMMDD)
    valid_from: str
    valid_to: str | None

    @property
    def identifier(self) -> str:
        return self.uri.rsplit("/", 1)[-1]


class CatalogError(Exception):
    code = "ERROR"


class SourceNotFound(CatalogError):
    code = "NOT_FOUND"


class VersionAmbiguous(CatalogError):
    code = "VERSION_AMBIGUOUS"


class VersionNotFound(CatalogError):
    code = "VERSION_NOT_FOUND"


def _check_sr(sr: str) -> str:
    if not SR_PATTERN.match(sr):
        raise CatalogError(f"Ungültige SR-Nummer: {sr!r}")
    return sr


def _check_uri(uri: str) -> str:
    if not ELI_CC.match(uri):
        raise CatalogError(f"Ungültige Fedlex-URI: {uri!r}")
    return uri


def _lang(language: str) -> str:
    if language not in LANG_URI:
        raise CatalogError(f"Nicht unterstützte Sprache: {language!r}")
    return LANG_URI[language]


# ---- queries -------------------------------------------------------------------------------------
def find_candidates(http: FedlexHttp, sr: str, language: str) -> list[LawCandidate]:
    """All statutes that ever carried this SR number (the number is NOT unique over time)."""
    q = (
        PREFIX
        + f"""SELECT DISTINCT ?abs ?dentry ?dgone ?abbr ?title WHERE {{
  ?abs a jolux:ConsolidationAbstract ;
       jolux:historicalLegalId "{_check_sr(sr)}" ;
       jolux:dateEntryInForce ?dentry .
  FILTER(STRSTARTS(STR(?abs), "https://fedlex.data.admin.ch/eli/cc/"))
  OPTIONAL {{ ?abs jolux:dateNoLongerInForce ?dgone }}
  OPTIONAL {{ ?abs jolux:isRealizedBy ?expr .
             ?expr jolux:language <{_lang(language)}> .
             OPTIONAL {{ ?expr jolux:titleShort ?abbr }}
             OPTIONAL {{ ?expr jolux:title ?title }} }}
}} LIMIT 20"""
    )
    seen: dict[str, LawCandidate] = {}
    for r in http.sparql(q):
        seen[r["abs"]] = LawCandidate(
            r["abs"], r.get("dentry"), r.get("dgone"), r.get("abbr"), r.get("title")
        )
    return list(seen.values())


def list_versions(http: FedlexHttp, abstract_uri: str) -> list[LawVersion]:
    q = (
        PREFIX
        + f"""SELECT DISTINCT ?cons ?dstart ?dend WHERE {{
  ?cons jolux:isMemberOf <{_check_uri(abstract_uri)}> ; jolux:dateApplicability ?dstart .
  OPTIONAL {{ ?cons jolux:dateEndApplicability ?dend }}
}} ORDER BY DESC(?dstart) LIMIT 400"""
    )
    by_uri: dict[str, LawVersion] = {}
    for r in http.sparql(q):
        by_uri[r["cons"]] = LawVersion(r["cons"], r["dstart"], r.get("dend"))
    return list(by_uri.values())


def find_xml_url(http: FedlexHttp, consolidation_uri: str, language: str) -> str | None:
    """The structured Akoma Ntoso XML (LegalDocML) of one version in one language."""
    q = (
        PREFIX
        + f"""SELECT DISTINCT ?url WHERE {{
  <{_check_uri(consolidation_uri)}> jolux:isRealizedBy ?expr .
  ?expr jolux:language <{_lang(language)}> ; jolux:isEmbodiedBy ?man .
  ?man jolux:userFormat <{XML_FORMAT}> ; jolux:isExemplifiedBy ?url .
}} LIMIT 5"""
    )
    urls = sorted({r["url"] for r in http.sparql(q)})
    if len(urls) > 1:
        raise FedlexBadResponse(f"Mehrere XML-Dokumente für {consolidation_uri}: unklar.")
    return urls[0] if urls else None


# ---- selection (pure, no network) ----------------------------------------------------------------------
def select_candidate(cands: list[LawCandidate], ref: date) -> LawCandidate:
    """The statute carrying the SR number on the reference date. Never silently picks one of several."""
    iso = ref.isoformat()
    live = [
        c
        for c in cands
        if (c.entry_in_force is None or c.entry_in_force <= iso)
        and (c.no_longer_in_force is None or iso < c.no_longer_in_force)
    ]
    if not cands:
        raise SourceNotFound("Kein Gesetz mit dieser SR-Nummer bei Fedlex gefunden.")
    if not live:
        raise VersionNotFound(f"Am {iso} war unter dieser SR-Nummer kein Gesetz in Kraft.")
    if len(live) > 1:
        raise VersionAmbiguous(
            f"SR-Nummer am {iso} nicht eindeutig: {[c.abstract_uri for c in live]}"
        )
    return live[0]


def select_version(versions: list[LawVersion], ref: date) -> LawVersion:
    """The version applicable on ``ref``. Future and historical versions are never mixed up."""
    iso = ref.isoformat()
    live = [
        v for v in versions if v.valid_from <= iso and (v.valid_to is None or iso <= v.valid_to)
    ]
    if not versions:
        raise SourceNotFound("Keine Fassungen bei Fedlex gefunden.")
    if not live:
        raise VersionNotFound(f"Für den Stichtag {iso} existiert keine Fassung.")
    if len(live) > 1:
        raise VersionAmbiguous(f"Mehrere Fassungen am {iso}: {[v.identifier for v in live]}")
    return live[0]


def newer_version_exists(versions: list[LawVersion], chosen: LawVersion) -> LawVersion | None:
    """A later version (possibly not yet in force) - the caller reports it, never switches silently."""
    later = sorted(
        (v for v in versions if v.valid_from > chosen.valid_from), key=lambda v: v.valid_from
    )
    return later[0] if later else None
