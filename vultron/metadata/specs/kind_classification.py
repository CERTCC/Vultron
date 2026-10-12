"""MS-12 kind-classification enforcement for the spec registry.

ADR-0038's ``SpecKind`` decision tree (then MS-12-001 … MS-12-005) went
unenforced from its adoption until issue #2601, and the corpus accreted ``kind: protocol``
specs that suppressed the story-traceability gate (SR-11-003) instead of
carrying a corrected kind. ADR-0133 then settled what the tree asks: who must
obey a rule decides its kind, and naming code never does (MS-12-002). These
mechanical checks back it:

- :func:`check_protocol_kind_code_references` — MS-12-006. A ``kind: protocol``
  spec that traces to no user story and whose ``statement`` names an
  unambiguous codebase construct is a hard error.
- :func:`check_foundation_standard_tags` — MS-12-009. A ``kind: foundation``
  spec names the standard it inherits from with one of
  :data:`~vultron.metadata.specs.schema.FOUNDATION_STANDARD_TAGS`.
- :func:`suppression_carriers` — the specs carrying a ``lint_suppress`` code.
  :func:`missing_story_suppression_carriers` is the per-item extractor behind
  the MS-12-007 PR-only growth guard, and the MS-12-008 assertion in
  ``test/architecture/test_spec_kind_ratchet.py`` holds the
  ``protocol_kind_with_code_reference`` carriers at none.
  :func:`suppression_status_lines` prints the live totals from ``spec-lint``,
  so they are visible without being committed.

The module sits beside ``lint.py`` rather than inside it so the guards can
import the very check the linter runs — one detector, two gates — and because
``lint.py`` is already past the module-size target (CS-18).

Scope decisions, each measured against the live corpus (the derivation is in
``notes/spec-authoring-rules.md`` § "Why MS-12-006 is scoped the way it is"):

- **Only the ``statement`` is scanned.** ``protocol`` means RFC content
  (MS-12-003), and whether a rule is RFC content is a property of the rule. A
  ``verification:`` clause names the test that checks the rule, and names a
  ``test/`` path because MS-10-003 and MS-15-001 oblige it to; scanning it
  relabeled some ninety wire and state-machine obligations to ``project``
  (#3943).
- **Only story-less specs are scanned.** A protocol spec that traces to a user
  story has demonstrated it is protocol. Scanning the whole protocol corpus
  flagged roughly half of it, most of them fully SR-11-compliant.
- **The token list is the closed set MS-12-006 names.** Bare ``module``,
  ``class`` and ``function`` read as domain English in wire requirements ("a
  machine-readable failure class") and are excluded.
- **The message says reword or split, never relabel.** A code token in a
  protocol statement does not make the rule ``project`` (MS-12-002): either
  the statement spells a protocol rule in this codebase's terms and is
  reworded, or it mixes a protocol rule with how this codebase meets it and
  is split (MS-12-010).
"""

from __future__ import annotations

import re
from pathlib import Path

from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import (
    FOUNDATION_STANDARD_TAGS,
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

#: The one field MS-12-006 scans. ``verification`` is excluded because it
#: names the test that checks a rule, which MS-10-003 and MS-15-001 oblige it
#: to do, and says nothing about whether the rule is protocol content (#3943).
#: Behavioral ``steps``, preconditions and postconditions are excluded too,
#: unlike the MS-15 phantom checks in ``lint.py``: an ECA step carries protocol
#: shorthand, and the requirement names ``statement`` only.
_SCANNED_FIELDS = ("statement",)


def code_reference_in(
    spec: StatementSpec | BehavioralSpec,
) -> tuple[str, str] | None:
    """Return ``(field, token)`` for the first MS-12-006 token in *spec*.

    ``token`` is widened to the whole path or dotted name the match belongs to.
    Returns ``None`` when no scanned field references a codebase construct.
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

    The message advises rewording the statement implementation-neutrally or
    splitting the spec (MS-12-010), never relabeling it (see the module
    docstring).
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
            f"references the codebase construct '{token}' (MS-12-006). "
            f"Naming code does not decide a spec's kind (MS-12-002). Reword "
            f"the statement so any implementation could obey it, or split the "
            f"spec (MS-12-010): this ID keeps the rule other participants can "
            f"observe, and how this codebase meets it moves to a new project "
            f"ID that links back. If the reference is genuinely incidental, "
            f"suppress with lint_suppress: [protocol_kind_with_code_reference]."
        )
    return errors


def check_foundation_standard_tags(registry: SpecRegistry) -> list[str]:
    """Hard errors for ``foundation`` specs that name no standard (MS-12-009).

    A ``foundation`` rule is inherited from a standard beneath Vultron, and its
    effective tags (its own, or its file's when it has none of its own) MUST
    name which one with at least one of :data:`FOUNDATION_STANDARD_TAGS`. Not suppressible: the tag is what
    lets a reader trace the rule to the standard that owns it.
    """
    wanted = ", ".join(sorted(tag.value for tag in FOUNDATION_STANDARD_TAGS))
    return [
        f"{spec_id}: kind=foundation but no tag names the standard it is "
        f"inherited from (MS-12-009); add one of: {wanted}"
        for spec_id, spec in registry.all_specs.items()
        if spec.kind == SpecKind.FOUNDATION
        and not FOUNDATION_STANDARD_TAGS.intersection(
            registry.get_effective_tags(spec_id)
        )
    ]


def suppression_carriers(
    registry: SpecRegistry, code: LintWarningCode
) -> frozenset[str]:
    """IDs of the specs whose ``lint_suppress:`` carries *code*.

    Every carrier counts, whether or not the suppressed check would fire on
    it, so a suppression left behind on a spec that no longer needs it still
    shows up as debt rather than vanishing (MS-12-007, MS-12-008).
    """
    return frozenset(
        spec_id
        for spec_id, spec in registry.all_specs.items()
        if code in set(spec.lint_suppress or [])
    )


def missing_story_suppression_carriers(repo_root: Path) -> frozenset[str]:
    """Carriers of ``missing_story_reference`` in ``specs/`` under *repo_root*.

    The per-item extractor behind the MS-12-007 growth guard
    (:func:`vultron.metadata.specs.growth_guard.added_since_base`).
    """
    return suppression_carriers(
        load_registry(repo_root / "specs"),
        LintWarningCode.MISSING_STORY_REFERENCE,
    )


#: The suppression codes whose carrier totals ``spec-lint`` reports.
_REPORTED_SUPPRESSIONS = (
    LintWarningCode.MISSING_STORY_REFERENCE,
    LintWarningCode.PROTOCOL_KIND_WITH_CODE_REFERENCE,
)


def suppression_status_lines(registry: SpecRegistry) -> list[str]:
    """One ``[INFO]`` line per MS-12 suppression code with its live total."""
    return [
        f"[INFO] lint_suppress {code.value}: "
        f"{len(suppression_carriers(registry, code))} spec(s) carry it"
        for code in _REPORTED_SUPPRESSIONS
    ]


__all__ = [
    "check_foundation_standard_tags",
    "check_protocol_kind_code_references",
    "code_reference_in",
    "missing_story_suppression_carriers",
    "suppression_carriers",
    "suppression_status_lines",
]
