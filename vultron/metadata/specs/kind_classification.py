"""MS-12 kind-classification enforcement for the spec registry.

ADR-0038's ``SpecKind`` decision tree (MS-12-001 … MS-12-005) went unenforced
from its adoption until issue #2601, and the corpus accreted ``kind: protocol``
specs that suppressed the story-traceability gate (SR-11-003) instead of
carrying a corrected kind. Two mechanical checks close that gap:

- :func:`check_protocol_kind_code_references` — MS-12-006. A ``kind: protocol``
  spec that traces to no user story and whose ``statement`` or ``verification``
  names an unambiguous codebase construct is a hard error.
- :func:`count_missing_story_suppressions` — the live count behind MS-12-007's
  ratchet in ``test/architecture/test_spec_kind_ratchet.py``.

The module sits beside ``lint.py`` rather than inside it so the ratchet can
import the very check the linter runs — one detector, two gates — and because
``lint.py`` is already past the module-size target (CS-18).

Scope decisions, each measured against the live corpus (the derivation is in
``notes/spec-authoring-rules.md`` § "Why MS-12-006 is scoped the way it is"):

- **Only story-less specs are scanned.** A protocol spec that traces to a user
  story has demonstrated it is protocol, and its ``verification:`` names a
  ``test/`` path because MS-10-003 and MS-15-001 oblige it to. Scanning the
  whole protocol corpus flagged roughly half of it, most of them fully
  SR-11-compliant.
- **The token list is the closed set MS-12-006 names.** Bare ``module``,
  ``class`` and ``function`` read as domain English in wire requirements ("a
  machine-readable failure class") and are excluded.
- **The message names the whole MS-12-001 → MS-12-005 tree, never a
  replacement kind.** ``pytest``, ``test/`` and ``scripts/`` sit in territory
  MS-12-001 claims for ``process``, so prescribing ``project`` would misroute
  exactly the specs that describe this check.
"""

from __future__ import annotations

import re

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    LintWarningCode,
    SpecKind,
    StatementSpec,
)

#: MS-12-006's closed token set. ``.py`` must end the word so ``.pyi`` and
#: ``.pytest_cache`` do not match; a code directory must not be preceded by a
#: path or word character so ``latest/`` and ``docs/test/`` do not read as
#: ``test/``. The three library names match regardless of case — prose writes
#: ``Pydantic`` as often as ``pydantic`` — while the suffix and paths stay
#: case-sensitive, as file systems spell them.
_CODE_REFERENCE_RE = re.compile(
    r"\.py\b"
    r"|(?<![\w/.-])(?:vultron|test|scripts)/"
    r"|(?i:\b(?:pytest|pydantic|py_trees)\b)"
)

#: Characters that continue the path or dotted name a match sits in, so the
#: error names ``test/demo/`` or ``conftest.py`` rather than ``test/`` or
#: ``.py``. ``\Z`` rather than ``$``: with ``endpos`` set to the match start,
#: ``$`` would also match before a newline just ahead of it and drag the
#: previous line into the reported token.
_TOKEN_HEAD_RE = re.compile(r"[\w./-]*\Z")
_TOKEN_TAIL_RE = re.compile(r"[\w./-]*")

#: The two fields MS-12-006 scans. Behavioral ``steps``, preconditions and
#: postconditions are deliberately not included, unlike the MS-15 phantom
#: checks in ``lint.py``: an ECA step carries protocol shorthand, and the
#: requirement names ``statement`` and ``verification`` only.
_SCANNED_FIELDS = ("statement", "verification")


def code_reference_in(
    spec: StatementSpec | BehavioralSpec,
) -> tuple[str, str] | None:
    """Return ``(field, token)`` for the first MS-12-006 token in *spec*.

    ``token`` is widened to the whole path or dotted name the match belongs to.
    Returns ``None`` when neither scanned field references a codebase
    construct.
    """
    for field in _SCANNED_FIELDS:
        text: str = getattr(spec, field) or ""
        match = _CODE_REFERENCE_RE.search(text)
        if match is None:
            continue
        head = _TOKEN_HEAD_RE.search(text, 0, match.start())
        tail = _TOKEN_TAIL_RE.match(text, match.end())
        start = head.start() if head is not None else match.start()
        end = tail.end() if tail is not None else match.end()
        return field, text[start:end]
    return None


def check_protocol_kind_code_references(registry: SpecRegistry) -> list[str]:
    """Hard errors for story-less protocol specs that name code (MS-12-006).

    The population is ``kind: protocol`` with no ``stories:``. Priority is not
    a gate — MS-12-006, unlike SR-11-003, applies to every tier — so a SHOULD
    or MAY that names a ``test/`` path is reported too. Suppressible per spec
    via ``lint_suppress: [protocol_kind_with_code_reference]``.

    The message directs the author to the MS-12-001 → MS-12-005 tree in order
    rather than naming a replacement kind (see the module docstring).
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if spec.kind != SpecKind.PROTOCOL or spec.stories:
            continue
        if LintWarningCode.PROTOCOL_KIND_WITH_CODE_REFERENCE in set(
            spec.lint_suppress or []
        ):
            continue
        hit = code_reference_in(spec)
        if hit is None:
            continue
        field, token = hit
        errors.append(
            f"{spec_id}: kind=protocol with no stories: but its {field} "
            f"references the codebase construct '{token}' (MS-12-006). A "
            f"protocol requirement binds every implementation in any "
            f"language; apply the MS-12-001 → MS-12-005 decision tree in "
            f"order and take the kind of the first question that matches, "
            f"or — if the reference is genuinely incidental — suppress with "
            f"lint_suppress: [protocol_kind_with_code_reference]."
        )
    return errors


def count_missing_story_suppressions(registry: SpecRegistry) -> int:
    """Number of specs carrying ``lint_suppress: [missing_story_reference]``.

    Counts every carrier, whether or not SR-11-003 would fire on it
    (MS-12-007), so a suppression left behind on a spec that is no longer a
    ``kind: protocol`` MUST still shows up as debt rather than vanishing.
    """
    return sum(
        1
        for spec in registry.all_specs.values()
        if LintWarningCode.MISSING_STORY_REFERENCE
        in set(spec.lint_suppress or [])
    )


__all__ = [
    "check_protocol_kind_code_references",
    "code_reference_in",
    "count_missing_story_suppressions",
]
