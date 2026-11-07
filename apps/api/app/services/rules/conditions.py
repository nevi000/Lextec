"""Deterministic rule-condition language (no eval, no code execution).

Syntax (YAML):

    when:
      all:                                   # also: any, not
        - { ref: fact.some_fact, op: equals, value: true }
        - { ref: ctx.active_issue_count, op: greater_than, value: 1 }

Three-valued semantics (True / False / None = "unknown"):

* Comparison operators (equals, not_equals, in, greater_than, less_than) on a fact that is not
  KNOWN (missing / ambiguous / contradictory / not applicable) evaluate to ``None`` (unknown).
* ``exists`` / ``is_known`` -> True iff the fact is KNOWN. ``is_missing`` -> True iff the fact is
  not KNOWN (not asked yet, ambiguous, contradictory or asked-but-unknown). ``is_unknown`` -> True
  iff the fact was ASKED and the person does not know (status UNKNOWN). These are always definite.
* ``derived.<id>`` values are computed by the engine from facts (see knowledge schema ``derived``);
  a derived value that cannot be computed is unknown (None).
* ``not`` of unknown stays unknown. ``all``: False if any child is False, else unknown if any
  child is unknown, else True. ``any``: True if any child is True, else unknown if any child is
  unknown, else False.
* A rule *fires* only if its condition evaluates to exactly ``True``. Unknown never fires.
  Consequently an unknown value can never silently trigger or suppress an escalation: missing
  facts are handled by the Missing Information Engine (-> ASK), not by guessing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Op = Literal[
    "equals",
    "not_equals",
    "in",
    "exists",
    "is_missing",
    "is_known",
    "greater_than",
    "less_than",
    "is_unknown",
]

VALUE_OPS = {"equals", "not_equals", "greater_than", "less_than"}
NO_VALUE_OPS = {"exists", "is_missing", "is_known", "is_unknown"}

CONTEXT_KEYS = frozenset(
    {
        "has_user_input",
        "active_issue_count",
        "unsupported_issue_count",
        "min_classification_confidence",
        "contradictory_fact_count",
        "missing_required_count",
    }
)

REF_PATTERN = re.compile(r"^(fact|ctx|issue|derived)\.([A-Za-z][A-Za-z0-9_]*)$")


class Condition(BaseModel):
    """One node of a condition tree: either a composite (all/any/not) or a leaf (ref/op)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all: list[Condition] | None = None
    any: list[Condition] | None = None
    not_: Condition | None = Field(default=None, alias="not")
    ref: str | None = None
    op: Op | None = None
    value: Any = None

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        forms = [
            self.all is not None,
            self.any is not None,
            self.not_ is not None,
            self.ref is not None or self.op is not None,
        ]
        if sum(forms) != 1:
            raise ValueError(
                "Eine Bedingung muss genau eine Form haben: all, any, not oder (ref + op)."
            )
        if self.all is not None and not self.all:
            raise ValueError("'all' darf nicht leer sein.")
        if self.any is not None and not self.any:
            raise ValueError("'any' darf nicht leer sein.")
        if self.ref is not None or self.op is not None:
            if self.ref is None or self.op is None:
                raise ValueError("Ein Blatt braucht sowohl 'ref' als auch 'op'.")
            if not REF_PATTERN.match(self.ref):
                raise ValueError(
                    f"Ungültige ref '{self.ref}'. Erlaubt: fact.<id>, ctx.<name>, issue.<id>, derived.<id>."
                )
            kind, name = self.ref.split(".", 1)
            if kind == "ctx" and name not in CONTEXT_KEYS:
                raise ValueError(
                    f"Unbekannter Kontext '{name}'. Erlaubt: {', '.join(sorted(CONTEXT_KEYS))}."
                )
            if self.op in NO_VALUE_OPS and self.value is not None:
                raise ValueError(f"Operator '{self.op}' erlaubt keinen 'value'.")
            if self.op in VALUE_OPS and self.value is None:
                raise ValueError(f"Operator '{self.op}' braucht einen 'value'.")
            if self.op == "in" and not (isinstance(self.value, list) and self.value):
                raise ValueError("Operator 'in' braucht eine nicht-leere Liste als 'value'.")
            if self.op == "is_unknown" and kind != "fact":
                raise ValueError("Operator 'is_unknown' ist nur auf fact.<id> erlaubt.")
            if kind == "issue" and self.op not in {"equals", "not_equals", "is_known", "exists"}:
                raise ValueError("Auf issue.<id> sind nur equals/not_equals/exists erlaubt.")
        return self

    # --- introspection -----------------------------------------------------------------
    def refs(self) -> list[str]:
        out: list[str] = []
        for child in (self.all or []) + (self.any or []):
            out.extend(child.refs())
        if self.not_ is not None:
            out.extend(self.not_.refs())
        if self.ref:
            out.append(self.ref)
        return out


Condition.model_rebuild()


@dataclass(frozen=True)
class EvalContext:
    """Values visible to the condition evaluator."""

    facts: Mapping[str, Any]  # only KNOWN facts, fact_id -> typed value
    ctx: Mapping[str, Any]
    active_issues: frozenset[str]
    unknown: frozenset[str] = frozenset()  # facts that were ASKED but the person does not know
    derived: Mapping[str, Any] = field(
        default_factory=dict
    )  # KB-declared derived values (e.g. days)


def _compare(op: str, left: Any, right: Any) -> bool | None:
    if isinstance(left, str) and isinstance(right, str):
        left, right = left.casefold(), right.casefold()
    if op == "equals":
        return left == right
    if op == "not_equals":
        return left != right
    # ordering
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    numeric = (int, float)
    if isinstance(left, numeric) and isinstance(right, numeric):
        pass
    elif isinstance(left, str) and isinstance(right, str):
        pass  # ISO dates compare correctly as strings
    else:
        return None
    return left > right if op == "greater_than" else left < right


def evaluate(cond: Condition, env: EvalContext) -> bool | None:
    if cond.all is not None:
        results = [evaluate(c, env) for c in cond.all]
        if any(r is False for r in results):
            return False
        return None if any(r is None for r in results) else True
    if cond.any is not None:
        results = [evaluate(c, env) for c in cond.any]
        if any(r is True for r in results):
            return True
        return None if any(r is None for r in results) else False
    if cond.not_ is not None:
        inner = evaluate(cond.not_, env)
        return None if inner is None else (not inner)

    assert cond.ref is not None and cond.op is not None
    kind, name = cond.ref.split(".", 1)

    if kind == "issue":
        active = name in env.active_issues
        if cond.op in {"exists", "is_known"}:
            return active
        return _compare(cond.op, active, cond.value)

    if kind == "ctx":
        actual = env.ctx.get(name)
        if actual is None:
            return None
        if cond.op in {"exists", "is_known"}:
            return True
        if cond.op == "is_missing":
            return False
        if cond.op == "in":
            return actual in cond.value
        return _compare(cond.op, actual, cond.value)

    if kind == "derived":
        actual = env.derived.get(name)
        if cond.op in {"exists", "is_known"}:
            return actual is not None
        if cond.op == "is_missing":
            return actual is None
        if actual is None:
            return None
        if cond.op == "in":
            return actual in cond.value
        return _compare(cond.op, actual, cond.value)

    # kind == "fact"
    if cond.op == "is_unknown":
        return name in env.unknown
    known = name in env.facts
    if cond.op in {"exists", "is_known"}:
        return known
    if cond.op == "is_missing":
        return not known
    if not known:
        return None
    actual = env.facts[name]
    if cond.op == "in":
        return any(_compare("equals", actual, v) for v in cond.value)
    return _compare(cond.op, actual, cond.value)


def fires(cond: Condition | None, env: EvalContext) -> bool:
    """A rule fires only when its condition is definitely True."""
    if cond is None:
        return False
    return evaluate(cond, env) is True
