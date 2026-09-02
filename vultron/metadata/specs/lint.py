"""Spec registry linter.

Linter requirements: specs/spec-registry.yaml SR-04.

Usage::

    python -m vultron.metadata.specs.lint specs/
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
)
from vultron.metadata.adr.loader import load_adr_registry
from vultron.metadata.specs.schema import (
    AdrStatus,
    BehavioralSpec,
    LintWarningCode,
    RFC2119Priority,
    SpecKind,
    StatementSpec,
    TriggerType,
)

_RATIONALE_WARN_CHARS = 500
_ADR_REF_RE = re.compile(r"\bADR-(\d{4})\b")

# MS-14: prose markers that mean the design is not yet validated. An ADR
# whose body contains any of these MUST NOT declare status: accepted.
_ADR_PROVISIONAL_MARKERS = (
    "formed in sand",
    "not concrete",
    "provisional",
    "forward-looking",
    "will converge",
    "expected to converge",
    "should refine this adr",
    "status will advance",
)


def _check_adr_status(
    adr_dir: Path | None,
) -> tuple[list[str], list[str]]:
    """Validate ADR frontmatter (MS-14-001 hard, MS-14-002 advisory).

    Returns ``(hard_errors, warnings)``:

    - **Hard (MS-14-001, MS-14-004)**: every ADR frontmatter MUST satisfy the
      :class:`~vultron.metadata.adr.schema.AdrFrontmatter` schema — a valid
      ``AdrStatus`` value, and a ``superseded_by`` link when retired. This
      delegates to :func:`~vultron.metadata.adr.loader.load_adr_registry`, so
      the schema is the single source of truth (no duplicated parsing).
    - **Advisory (MS-14-002)**: an ADR whose prose carries a provisional marker
      SHOULD NOT be ``status: accepted``. This is a heuristic body scan and can
      false-positive (e.g. an ADR that *discusses* provisional-ness), so it
      surfaces ``decision-audit`` candidates rather than blocking CI; an ADR may
      opt out with ``lint_suppress: [status_prose_contradiction]``.

    Degrades to empty lists when ``adr_dir`` is missing so the check is a no-op
    in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return [], []

    errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = load_adr_registry(adr_dir.parent.parent)
    except ValueError as exc:
        # A single malformed ADR aborts registry load; surface it as the error.
        return [f"ADR frontmatter invalid (MS-14-001): {exc}"], []
    except FileNotFoundError:
        return [], []

    for rel_path, fm in registry.items():
        name = Path(rel_path).name
        if fm.status is not AdrStatus.ACCEPTED:
            continue
        if fm.lint_suppress and any(
            c.value == "status_prose_contradiction" for c in fm.lint_suppress
        ):
            continue

        body = (
            (adr_dir.parent.parent / rel_path)
            .read_text(encoding="utf-8")
            .lower()
        )
        hit = next((m for m in _ADR_PROVISIONAL_MARKERS if m in body), None)
        if hit is not None:
            warnings.append(
                f"[WARN] {name}: status is 'accepted' but prose contains "
                f"provisional marker '{hit}' (MS-14-002); if the design is "
                f"genuinely unvalidated use 'accepted-provisional' — else "
                f"this is a decision-audit candidate (see ADR-0043). "
                f"Suppress on an ADR that legitimately discusses "
                f"provisional-ness with "
                f"'lint_suppress: [status_prose_contradiction]'."
            )
    return errors, warnings


#: MS-15: a backticked token in a spec statement that looks like a
#: repo-relative file path (has a directory separator and a known extension).
_SPEC_PATH_RE = re.compile(
    r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.(?:py|ya?ml|md|json|toml))`"
)

#: MS-15: a backticked token that looks like a repo-relative directory path
#: (two or more path segments with a trailing slash).  Single-segment forms
#: (e.g. ``devlogs/``) are excluded because they are frequently conceptual or
#: context-specific (CI runner refs, runtime output dirs) and carry high
#: false-positive risk.
_SPEC_DIR_RE = re.compile(r"`((?:[A-Za-z0-9_.][A-Za-z0-9_.-]*/){2,})`")

#: Placeholder tokens that name a *shape* of path rather than a real one
#: (e.g. `test_XXX_invariants.py`, `plan/history/YYMM/README.md`,
#: `docs/adr/ADR-XXXX-foo.md`). Uppercase by convention, so a collision with a
#: real path segment is implausible. Bracketed forms (`{YYMM}`, `<repo>`) need
#: no entry here — :data:`_SPEC_PATH_RE` cannot match them in the first place.
_PATH_PLACEHOLDER_RE = re.compile(r"XXX|YYMM|NNNN")

#: Placeholder *basenames* used in spec prose to illustrate a new file being
#: created. Matched whole-segment, not as substrings: `notes/new-spec.md` is
#: exempt but `notes/new-spec-workflow.md` is a real path and is checked.
_PLACEHOLDER_BASENAMES = frozenset({"new-topic.md", "new-spec.md"})

#: Top-level repository directories that a spec statement may reference
#: repo-relatively. Enumerated explicitly rather than read from the working
#: tree so the check behaves identically in a developer checkout (where
#: gitignored directories such as ``devlogs/`` and ``site/`` exist) and in a
#: fresh CI clone (where they do not). Add a directory here when the repo grows
#: one that specs cite.
_REPO_TOP_LEVEL_DIRS = frozenset(
    {
        ".agents",
        ".claude",
        ".devcontainer",
        ".github",
        "archived_notes",
        "doc",
        "docker",
        "docs",
        "integration_tests",
        "notes",
        "ontology",
        "overrides",
        "plan",
        "prompts",
        "scripts",
        "specs",
        "test",
        "vultron",
    }
)

#: Regex for bare spec ID tokens (e.g. ``HTTP-03-005``, ``CBT-05-007``) in
#: Python source files.  Matched with ``\b`` word boundaries so that version
#: strings like ``1.2.3`` or ``ADR-0001`` are not mistaken for spec IDs.
#: The pattern is intentionally specific to Vultron spec ID conventions
#: (2–8 uppercase letters, two-digit group, three-digit index) and does not
#: match ISO standard numbers, semantic version strings, or similar patterns
#: seen in the vultron/ and test/ trees.
_SPEC_ID_RE = re.compile(r"\b([A-Z]{2,8}-\d{2}-\d{3})\b")

#: MS-15: a backticked ``SCREAMING_SNAKE_CASE`` token in spec prose, read as a
#: reference to a module-level code symbol (e.g. ``SEMANTIC_REGISTRY``,
#: ``CORE_VOCABULARY``). At least one underscore is required, which excludes the
#: three shapes that would otherwise dominate the matches and are not symbols:
#: RFC 2119 keywords (``MUST``), protocol shorthands (``RS``, ``EP``), and
#: single-word state or role names (``SIGNATORY``, ``VFD``). A dotted member
#: reference (`` `MessageSemantics.UNKNOWN` ``) does not match either, since
#: the opening backtick must be followed immediately by the token.
_SPEC_SYMBOL_RE = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`")

#: Uppercase word tokens in Python source. Used to build the symbol corpus
#: that :func:`_check_phantom_symbols` resolves spec references against. A
#: textual scan rather than an AST walk on purpose: a spec may legitimately
#: name a symbol that appears only in a docstring, a comment, or a string
#: literal, and none of those are bindings an AST pass would report.
_SOURCE_SYMBOL_RE = re.compile(r"\b[A-Z][A-Z0-9_]*\b")

#: Directories (relative to repo root) whose Python files legitimately cite
#: synthetic fixture IDs and are therefore excluded from the phantom-ID scan.
#: Use a trailing ``/`` to match the directory exactly and avoid silently
#: exempting a sibling directory that shares the same prefix.
_PHANTOM_ID_ALLOWLIST_DIRS = frozenset(["test/metadata/specs"])

#: Files and directories excluded from the symbol corpus that
#: :func:`_check_phantom_symbols` resolves against. Each entry matches either an
#: exact file or a directory prefix. Both hold symbol names that are *examples*
#: rather than code the specs describe: this module quotes retired names while
#: documenting the check that exists to reject them — including
#: ``SEMANTICS_ACTIVITY_PATTERNS`` itself, which would otherwise resolve as live
#: and blind the guard to the case it was built for — and the linter's own tests
#: invent names for fixtures.
#:
#: Scoped to ``lint.py`` rather than the whole ``vultron/metadata/specs/``
#: package on purpose: ``schema.py`` defines symbols the specs legitimately
#: cite (``RFC2119Priority`` members such as ``SHOULD_NOT``), so excluding the
#: package would reject real references. Separate from
#: :data:`_PHANTOM_ID_ALLOWLIST_DIRS` for the same reason in reverse — a stale
#: spec ID cited by the linter is a real defect and must stay scanned.
_SYMBOL_CORPUS_EXCLUDED_PATHS = frozenset(
    ["vultron/metadata/specs/lint.py", "test/metadata/specs"]
)

#: Directories skipped when resolving a package-relative path suffix — build
#: artifacts and virtualenvs would otherwise satisfy a reference that no
#: tracked file does.
_IGNORED_TREE_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "devlogs",
        "node_modules",
        "site",
        "vultron.egg-info",
    }
)


def _check_phantom_paths(registry: SpecRegistry, repo_root: Path) -> list[str]:
    """Hard error when a spec field names a file or directory that does not exist (MS-15-001).

    A normative statement or verification criterion that points at a
    non-existent path is a stale-premise landmine: an agent reads the MUST,
    cannot find the infrastructure, and either invents something inconsistent
    or silently ignores the requirement.
    DEMOMA-19-008 (issue #2004) named a ``test/ci/invariants/conftest.py`` that
    had never existed on any branch.

    Scanned fields: ``statement``, ``verification``, ``BehavioralSpec`` step
    ``action``, precondition ``description``, and postcondition ``description``.
    ``rationale`` narrates history by design
    ("X has been converted to Y", "if X stays in Z...") and legitimately
    references paths that no longer exist.

    File references (backticked path with extension and ``/`` separator) use
    :data:`_SPEC_PATH_RE`.  Directory references (two or more path segments
    with a trailing ``/``) use :data:`_SPEC_DIR_RE`.  Single-segment directory
    forms (e.g. ``devlogs/``) are excluded from the directory check because
    they are frequently conceptual or CI-context references with high
    false-positive risk.

    A match whose first segment is a known top-level directory
    (:data:`_REPO_TOP_LEVEL_DIRS`) is resolved repo-relatively. Any other match
    is a package-relative illustration such as ``vocab/activities/embargo.py``
    and is resolved as a path *suffix* anywhere in the tree. Suffix resolution
    is deliberate rather than a blanket exemption: it is what catches a
    mistyped leading segment (``tests/ci/...`` for ``test/ci/...``), which is
    the most common shape of a stale reference.

    Exemptions:

    - Placeholder forms (:data:`_PATH_PLACEHOLDER_RE`,
      :data:`_PLACEHOLDER_BASENAMES`) that describe a path shape rather than a
      specific file.
    - Per-spec opt-out via ``lint_suppress: [phantom_path_ref]``, for a
      spec-first requirement that deliberately names a file yet to be created.

    Absolute paths and paths containing a ``..`` segment are rejected outright
    rather than exempted: neither is a valid repo-relative reference, and
    ``..`` would otherwise resolve outside the repository.
    """
    resolver = _PathResolver(repo_root)

    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if LintWarningCode.PHANTOM_PATH_REF in set(spec.lint_suppress or []):
            continue
        for field_label, text in _scanned_texts(spec):
            for match in _SPEC_PATH_RE.findall(text):
                problem = resolver.problem_with(match)
                if problem is not None:
                    errors.append(
                        f"{spec_id}: {field_label} references {problem}"
                    )
            for match in _SPEC_DIR_RE.findall(text):
                problem = resolver.problem_with_dir(match)
                if problem is not None:
                    errors.append(
                        f"{spec_id}: {field_label} references {problem}"
                    )

    return errors


def _scanned_texts(
    spec: BehavioralSpec | StatementSpec,
) -> list[tuple[str, str]]:
    """Return ``(field_label, text)`` pairs for all fields scanned by MS-15-001.

    ``rationale`` is deliberately excluded — it narrates history and may
    legitimately cite paths that no longer exist.
    """
    texts: list[tuple[str, str]] = [
        ("statement", spec.statement or ""),
        ("verification", spec.verification or ""),
    ]
    if isinstance(spec, BehavioralSpec):
        for step in spec.steps or []:
            texts.append(("behavioral step", step.action))
        for pre in spec.preconditions or []:
            texts.append(("precondition", pre.description))
        for post in spec.postconditions or []:
            texts.append(("postcondition", post.description))
    return texts


class _PathResolver:
    """Classifies a single backticked path match for :func:`_check_phantom_paths`.

    Holds the lazily-built tree-path index so it is walked at most once per
    lint run rather than once per match.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._tree_paths: set[str] | None = None
        self._tree_dirs: set[str] | None = None

    def problem_with(self, match: str) -> str | None:
        """Return an error fragment for ``match``, or ``None`` if it resolves."""
        segments = match.split("/")

        if match.startswith("/") or ".." in segments:
            return (
                f"'{match}', which is not a valid repo-relative path "
                f"(MS-15-001). Absolute paths and '..' segments are not "
                f"permitted."
            )

        if _PATH_PLACEHOLDER_RE.search(match):
            return None
        if segments[-1] in _PLACEHOLDER_BASENAMES:
            return None

        if segments[0] in _REPO_TOP_LEVEL_DIRS:
            if (self._repo_root / match).exists():
                return None
            hint = "Point at the real path"
        else:
            if self._resolves_as_suffix(match):
                return None
            hint = (
                "Point at the real path (this is not a repo-relative path, "
                "and no file in the tree ends with it)"
            )

        return (
            f"'{match}' which does not exist (MS-15-001). {hint}, or — if the "
            f"file is intentionally yet to be created — suppress with "
            f"lint_suppress: [phantom_path_ref]."
        )

    def problem_with_dir(self, match: str) -> str | None:
        """Return an error fragment for directory ``match``, or ``None`` if it resolves.

        ``match`` is expected to have a trailing ``/`` as captured by
        :data:`_SPEC_DIR_RE`.
        """
        path = match.rstrip("/")
        segments = path.split("/")

        if ".." in segments:
            return (
                f"'{match}', which is not a valid repo-relative path "
                f"(MS-15-001). '..' segments are not permitted."
            )

        if _PATH_PLACEHOLDER_RE.search(match):
            return None

        if segments[0] in _REPO_TOP_LEVEL_DIRS:
            if (self._repo_root / path).is_dir():
                return None
            hint = "Point at the real path"
        else:
            if self._resolves_as_dir_suffix(path):
                return None
            hint = (
                "Point at the real path (this is not a repo-relative "
                "directory, and no directory in the tree ends with it)"
            )

        return (
            f"'{match}' which does not exist (MS-15-001). {hint}, or — if "
            f"the directory is intentionally yet to be created — suppress "
            f"with lint_suppress: [phantom_path_ref]."
        )

    def _resolves_as_suffix(self, match: str) -> bool:
        """True when some file in the tree has ``match`` as a path suffix."""
        if self._tree_paths is None:
            self._tree_paths = _collect_tree_paths(self._repo_root)
        suffix = "/" + match
        return match in self._tree_paths or any(
            p.endswith(suffix) for p in self._tree_paths
        )

    def _resolves_as_dir_suffix(self, path: str) -> bool:
        """True when some directory in the tree has ``path`` as a path suffix."""
        if self._tree_dirs is None:
            self._tree_dirs = _collect_tree_dirs(self._repo_root)
        suffix = "/" + path
        return path in self._tree_dirs or any(
            d.endswith(suffix) for d in self._tree_dirs
        )


def _collect_tree_paths(repo_root: Path) -> set[str]:
    """Return every file path in the repo, repo-relative, as a POSIX string.

    Specs illustrate package-relative paths (``vocab/activities/embargo.py`` for
    ``vultron/wire/as2/vocab/activities/embargo.py``), so a match that is not
    rooted at a top-level directory is resolved against this set as a path
    suffix rather than exempted outright.

    :data:`_IGNORED_TREE_DIRS` is pruned during the walk, not filtered
    afterwards — descending into ``.venv/`` would dominate the runtime and let a
    vendored file satisfy a reference that no repo file does. Built lazily and
    at most once per lint run.
    """
    paths: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_TREE_DIRS]
        rel_dir = Path(dirpath).relative_to(repo_root)
        prefix = "" if rel_dir == Path(".") else rel_dir.as_posix() + "/"
        for name in filenames:
            paths.add(prefix + name)
    return paths


def _collect_tree_dirs(repo_root: Path) -> set[str]:
    """Return every directory path in the repo, repo-relative, as a POSIX string.

    Same walk rules as :func:`_collect_tree_paths` — :data:`_IGNORED_TREE_DIRS`
    is pruned during the walk so build artifacts and virtualenvs do not satisfy
    a reference that no tracked directory does.  Built lazily and at most once
    per lint run.
    """
    dirs: set[str] = set()
    for dirpath, dirnames, _ in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_TREE_DIRS]
        rel_dir = Path(dirpath).relative_to(repo_root)
        if rel_dir != Path("."):
            dirs.add(rel_dir.as_posix())
    return dirs


def _check_prefix_consistency(registry: SpecRegistry) -> list[str]:
    """Verify each group ID prefix matches its containing file prefix
    (SR-01-007)."""
    errors: list[str] = []
    for spec_file in registry.files:
        file_prefix = spec_file.id
        for group in spec_file.groups:
            group_prefix = group.id.split("-")[0]
            if group_prefix != file_prefix:
                errors.append(
                    f"Group '{group.id}' prefix '{group_prefix}' does not "
                    f"match file prefix '{file_prefix}'"
                )
    return errors


def _check_spec_id_prefix_consistency(registry: SpecRegistry) -> list[str]:
    """Verify each spec ID prefix matches the group it lives in (MS-04-004).

    A spec with ID ``HP-07-002`` MUST reside in group ``HP-07``.
    """
    errors: list[str] = []
    for spec_file in registry.files:
        for group in spec_file.groups:
            expected_prefix = group.id + "-"
            for spec in group.specs:
                if not spec.id.startswith(expected_prefix):
                    errors.append(
                        f"Spec '{spec.id}' does not belong in group "
                        f"'{group.id}' (expected prefix '{expected_prefix}')"
                    )
    return errors


def _adr_exists(adr_dir: Path, adr_number: str) -> bool:
    """Return True if an ADR file for ``adr_number`` exists in ``adr_dir``.

    ADR files follow the naming convention ``NNNN-<slug>.md``, so
    ``ADR-0009`` resolves to any file matching ``0009-*.md``.
    """
    return any(adr_dir.glob(f"{adr_number}-*.md"))


def _check_adr_references(
    registry: SpecRegistry, adr_dir: Path | None
) -> tuple[list[str], list[str]]:
    """Validate spec → ADR references (MS-11-004, SR-03-004).

    Returns ``(hard_errors, warnings)``:

    - **Hard**: a structured ``adr:`` field target with no matching ADR file
      (in ``adr_dir`` or ``adr_dir/archived``). The structured field is part of
      the traceability edges graph, so a dangling target silently breaks
      "dependents of ADR-NNNN" queries.
    - **Advisory**: a free-text ``rationale`` citation of an ADR that does not
      exist (legacy prose form; suppressible via ``lint_suppress``).

    Returns two empty lists when ``adr_dir`` is None or does not exist so the
    check degrades gracefully in environments without a docs/ tree.
    """
    if adr_dir is None or not adr_dir.is_dir():
        return [], []

    warnings: list[str] = []
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        # Structured adr: references are validated as HARD errors — the field is
        # part of the traceability graph, so a dangling target breaks
        # "dependents of ADR-NNNN" queries (MS-11-004, SR-03-004). Also search
        # both docs/adr/ and docs/adr/archived/ so pointing at a retired ADR is
        # still valid.
        for adr_id in spec.adr or []:
            adr_number = adr_id.split("-", 1)[1]
            if not _adr_exists(adr_dir, adr_number) and not _adr_exists(
                adr_dir / "archived", adr_number
            ):
                errors.append(
                    f"{spec_id}: adr reference '{adr_id}' has no matching "
                    f"ADR file in '{adr_dir}' or '{adr_dir / 'archived'}'"
                )

        # Free-text rationale ADR citations remain advisory (legacy prose form).
        suppressed = set(spec.lint_suppress or [])
        if LintWarningCode.DANGLING_ADR_REF in suppressed:
            continue
        seen = set(_ADR_REF_RE.findall(spec.rationale or ""))
        for adr_number in seen:
            if not _adr_exists(adr_dir, adr_number) and not _adr_exists(
                adr_dir / "archived", adr_number
            ):
                warnings.append(
                    f"[WARN] {spec_id}: rationale references "
                    f"ADR-{adr_number} but no matching file found in "
                    f"'{adr_dir}' "
                    f"(suppress with lint_suppress: [dangling_adr_ref])"
                )
    return errors, warnings


def _check_missing_kind(registry: SpecRegistry) -> list[str]:
    """Return hard errors for any spec item missing a ``kind:`` field (SR-09-003).

    Pydantic already rejects ``kind: null`` at load time via the required
    ``SpecKind`` field type, so this check is belt-and-suspenders for future
    schema relaxations or registry manipulation outside the Pydantic validator.
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if spec.kind is None:
            errors.append(
                f"{spec_id}: missing required 'kind' field on spec item"
            )
    return errors


def _check_scenario_start_groups(registry: SpecRegistry) -> list[str]:
    """Hard error when a scenario_start group has no BehavioralSpec with steps.

    Enforces MS-13-004: mixed groups are permitted, but at least one item must
    be a BehavioralSpec with a non-empty steps list.
    """
    errors: list[str] = []
    for spec_file in registry.files:
        for group in spec_file.groups:
            if (
                group.trigger is None
                or group.trigger.type != TriggerType.SCENARIO_START
            ):
                continue
            has_eca = any(
                isinstance(spec, BehavioralSpec) and bool(spec.steps)
                for spec in group.specs
            )
            if not has_eca:
                errors.append(
                    f"Group '{group.id}' has trigger type scenario_start but "
                    f"contains no BehavioralSpec item with steps (MS-13-004)"
                )
    return errors


def _check_missing_story_references(registry: SpecRegistry) -> list[str]:
    """Hard error when a ``kind: protocol`` MUST spec has no ``stories:`` (SR-11-003).

    Protocol MUST specs define wire-level compliance invariants.  A MUST with no
    user-story back-reference breaks the bidirectional traceability graph and is
    treated as a hard gate (exit 1).  Suppressible via
    ``lint_suppress: [missing_story_reference]`` for specs that are genuinely
    not traceable to any story.
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if spec.kind != SpecKind.PROTOCOL:
            continue
        if spec.priority != RFC2119Priority.MUST:
            continue
        if spec.stories:
            continue
        suppressed = set(spec.lint_suppress or [])
        if LintWarningCode.MISSING_STORY_REFERENCE in suppressed:
            continue
        errors.append(
            f"{spec_id}: kind=protocol, priority=MUST but has no stories: "
            f"field (SR-11-003); add user-story back-references, or suppress "
            f"with lint_suppress: [missing_story_reference]"
        )
    return errors


def _check_per_spec_advisory_warnings(registry: SpecRegistry) -> list[str]:
    """Collect per-spec advisory warnings (SR-04-002).

    Covers: testable_without_steps, rationale_too_long, missing_tags,
    must_without_verification, and missing_story_reference (SHOULD/MAY).
    All are suppressible via ``lint_suppress``.
    """
    warnings: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        suppressed = set(spec.lint_suppress or [])

        is_behavioral = isinstance(spec, BehavioralSpec) and bool(spec.steps)

        if (
            not spec.testable
            and not is_behavioral
            and LintWarningCode.TESTABLE_WITHOUT_STEPS not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: testable=false but no behavioral steps "
                f"(suppress with lint_suppress: [testable_without_steps])"
            )

        if (
            spec.rationale
            and len(spec.rationale) > _RATIONALE_WARN_CHARS
            and LintWarningCode.RATIONALE_TOO_LONG not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: rationale exceeds "
                f"{_RATIONALE_WARN_CHARS} characters"
            )

        tags = registry.get_effective_tags(spec_id)
        if not tags and LintWarningCode.MISSING_TAGS not in suppressed:
            warnings.append(f"[WARN] {spec_id}: no tags defined")

        if (
            spec.priority == RFC2119Priority.MUST
            and not spec.verification
            and LintWarningCode.MUST_WITHOUT_VERIFICATION not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: priority is MUST but has no "
                f"verification: field (MS-05-003); add a verification: "
                f"criterion, or suppress with "
                f"lint_suppress: [must_without_verification]"
            )

        if (
            spec.kind == SpecKind.PROTOCOL
            and spec.priority in (RFC2119Priority.SHOULD, RFC2119Priority.MAY)
            and not spec.stories
            and LintWarningCode.MISSING_STORY_REFERENCE not in suppressed
        ):
            warnings.append(
                f"[WARN] {spec_id}: kind=protocol, priority={spec.priority} "
                f"but has no stories: field (SR-11-004); consider adding "
                f"user-story back-references, or suppress with "
                f"lint_suppress: [missing_story_reference]"
            )

    return warnings


class _SourceScan:
    """One pass over the ``vultron/`` and ``test/`` Python trees.

    Two checks need the full text of every tracked Python file:
    :func:`_check_phantom_spec_id_citations` reads spec IDs *out* of the source,
    and :func:`_check_phantom_symbols` resolves spec references *into* it.
    Walking the tree once and sharing the result keeps the linter's I/O flat as
    the second check is added — ``spec-lint`` runs on every commit and its
    pytest wrapper sits close to a 5 s budget.

    The two exclusion sets differ on purpose — see
    :data:`_PHANTOM_ID_ALLOWLIST_DIRS` and
    :data:`_SYMBOL_CORPUS_EXCLUDED_PATHS`.

    Attributes:
        spec_id_citations: ``(relative_path, spec_id)`` for every distinct spec
            ID token cited by a file, excluding
            :data:`_PHANTOM_ID_ALLOWLIST_DIRS`.
        symbols: Every uppercase word token seen anywhere in the scanned
            source, excluding :data:`_SYMBOL_CORPUS_EXCLUDED_PATHS`.
    """

    def __init__(self, repo_root: Path) -> None:
        self.spec_id_citations: list[tuple[str, str]] = []
        self.symbols: set[str] = set()

        for scan_root in (repo_root / "vultron", repo_root / "test"):
            if not scan_root.is_dir():
                continue
            for py_file in sorted(scan_root.rglob("*.py")):
                try:
                    rel = py_file.relative_to(repo_root)
                except ValueError:
                    continue
                rel_str = str(rel).replace("\\", "/")
                text = py_file.read_text(encoding="utf-8", errors="replace")

                if not any(
                    rel_str == p or rel_str.startswith(p + "/")
                    for p in _SYMBOL_CORPUS_EXCLUDED_PATHS
                ):
                    self.symbols.update(_SOURCE_SYMBOL_RE.findall(text))

                if any(
                    rel_str.startswith(d + "/")
                    for d in _PHANTOM_ID_ALLOWLIST_DIRS
                ):
                    continue
                seen_in_file: set[str] = set()
                for match in _SPEC_ID_RE.finditer(text):
                    sid = match.group(1)
                    if sid not in seen_in_file:
                        seen_in_file.add(sid)
                        self.spec_id_citations.append((rel_str, sid))


def _check_phantom_spec_id_citations(
    registry: SpecRegistry, scan: _SourceScan
) -> list[str]:
    """Hard error when Python source cites a spec ID that does not exist (SR-04-008).

    Reads the spec ID tokens (pattern ``[A-Z]{2,8}-\\d{2}-\\d{3}``) that
    *scan* collected from ``vultron/`` and ``test/`` and rejects any that are
    not present in the registry.  Files under ``test/metadata/specs/`` are
    excluded by the scan because they legitimately cite synthetic fixture IDs.
    """
    known_ids = set(registry.all_specs.keys())
    return [
        f"{rel_str}: cites unknown spec ID {sid}"
        for rel_str, sid in scan.spec_id_citations
        if sid not in known_ids
    ]


def _check_phantom_symbols(
    registry: SpecRegistry, scan: _SourceScan
) -> list[str]:
    """Hard error when a spec field names a code symbol that does not exist (MS-15-004).

    The mirror image of :func:`_check_phantom_paths`, for the reference shape
    that check cannot see. ``_check_phantom_paths`` only inspects backticked
    tokens containing a directory separator, so a bare symbol name such as
    `` `SEMANTICS_ACTIVITY_PATTERNS` `` passed silently — and did, across 33
    occurrences and 8 MUST-level statements, for the whole interval between the
    symbol's removal and issue #3022.

    A statement that asserts a MUST about a symbol nobody can find is worse
    than an absent requirement: an agent reads it, cannot locate the referent,
    and either invents a replacement or quietly drops the obligation. Making
    the divergence *detectable* rather than merely absent is the principle
    ADR-0083 applies to message shapes; this applies it to symbol names.

    Scanned fields are :func:`_scanned_texts` — the same set
    ``_check_phantom_paths`` uses. ``rationale`` is again excluded: it narrates
    history by design and legitimately names symbols that have been removed.

    Resolution is deliberately loose — a token counts as live if it appears
    *anywhere* in the ``vultron/`` or ``test/`` Python text, including comments
    and docstrings. The check is aimed at names with no trace left in the
    codebase, not at proving a binding exists at the cited location, so it
    prefers a false negative over blocking a commit on a legitimate reference.
    The one exception to that preference is the whole-token corpus: a cited
    ``FOO`` whose only occurrence in source is as a fragment of a longer
    identifier (``FOO_V2``) does *not* resolve, because :data:`_SOURCE_SYMBOL_RE`
    captures whole ``\\b``-delimited runs. That is a deliberate true positive —
    ``FOO`` and ``FOO_V2`` are distinct symbols — not an oversight; suppress with
    ``lint_suppress`` if a spec genuinely means the longer name.

    Exemption: per-spec opt-out via ``lint_suppress: [phantom_symbol_ref]``,
    for a statement that deliberately names a retired symbol in order to
    record its removal, or names a convention token that was never code.
    """
    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if LintWarningCode.PHANTOM_SYMBOL_REF in set(spec.lint_suppress or []):
            continue
        seen: set[str] = set()
        for field_label, text in _scanned_texts(spec):
            for match in _SPEC_SYMBOL_RE.findall(text):
                if match in scan.symbols or match in seen:
                    continue
                seen.add(match)
                errors.append(
                    f"{spec_id}: {field_label} references symbol "
                    f"'{match}' which does not appear anywhere in vultron/ or "
                    f"test/ (MS-15-004). Point at the live symbol, or — if the "
                    f"reference is deliberately historical — suppress with "
                    f"lint_suppress: [phantom_symbol_ref]."
                )
    return errors


def lint(
    spec_dir: Path,
    adr_dir: Path | None = None,
    registry: SpecRegistry | None = None,
) -> int:
    """Validate the spec registry in ``spec_dir``.

    Hard errors cause exit code 1.  Advisory warnings are printed but do not
    affect the exit code (SR-04-001, SR-04-002).

    Args:
        spec_dir: Directory containing ``*.yaml`` spec files.
        adr_dir: Directory containing ADR markdown files.  When ``None``
            (the default), falls back to ``spec_dir.parent / "docs" / "adr"``
            so that ``uv run spec-lint`` from the repository root picks up
            ``docs/adr/`` automatically.  To skip the ADR-reference check,
            pass a path that does not exist on disk.
        registry: Pre-loaded :class:`SpecRegistry` instance.  When provided,
            the ``load_registry(spec_dir)`` call is skipped, avoiding
            redundant I/O in callers that already hold a loaded registry.

    Returns:
        ``0`` if no hard errors, ``1`` if any hard errors found.
    """
    if adr_dir is None:
        adr_dir = spec_dir.parent / "docs" / "adr"

    hard_errors: list[str] = []
    warnings: list[str] = []

    if registry is None:
        try:
            registry = load_registry(spec_dir)
        except (ValidationError, ValueError) as exc:
            print(f"[FATAL] Registry load failed:\n{exc}", file=sys.stderr)
            return 1

    hard_errors.extend(registry.validate_cross_references())
    hard_errors.extend(_check_prefix_consistency(registry))
    hard_errors.extend(_check_spec_id_prefix_consistency(registry))
    hard_errors.extend(_check_scenario_start_groups(registry))
    hard_errors.extend(_check_phantom_paths(registry, spec_dir.parent))
    source_scan = _SourceScan(spec_dir.parent)
    hard_errors.extend(_check_phantom_spec_id_citations(registry, source_scan))
    hard_errors.extend(_check_phantom_symbols(registry, source_scan))
    hard_errors.extend(_check_missing_story_references(registry))

    warnings.extend(_check_per_spec_advisory_warnings(registry))

    adr_ref_errors, adr_ref_warnings = _check_adr_references(registry, adr_dir)
    hard_errors.extend(adr_ref_errors)
    warnings.extend(adr_ref_warnings)
    hard_errors.extend(_check_missing_kind(registry))
    adr_status_errors, adr_status_warnings = _check_adr_status(adr_dir)
    hard_errors.extend(adr_status_errors)
    warnings.extend(adr_status_warnings)

    for w in warnings:
        print(w)
    for e in hard_errors:
        print(f"[ERROR] {e}", file=sys.stderr)

    return 0 if not hard_errors else 1


def main() -> None:
    """CLI entry point: ``uv run spec-lint`` or
    ``python -m vultron.metadata.specs.lint [spec_dir]`` (SR-04-003).

    ``spec_dir`` defaults to ``specs/`` relative to the current working
    directory so that ``uv run spec-lint`` from the repository root
    behaves identically to the pre-commit hook.
    """
    spec_dir = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path("specs")
    if not spec_dir.is_dir():
        print(
            f"[FATAL] spec_dir '{spec_dir}' not found or not a directory",
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(lint(spec_dir))


if __name__ == "__main__":
    main()
