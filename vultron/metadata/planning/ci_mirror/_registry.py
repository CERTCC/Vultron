#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""What the local CI mirror runs, and every CI step it leaves out and why.

Every step a ``pull_request`` run can execute is either mirrored by a
:class:`MirrorCheck` or matched by an :data:`EXCLUSIONS` key with a reason;
``test/ci/test_prepush_ci_mirror_parity.py`` fails on a step that is neither,
on a key that names no step, and on a step both mirror and exclusion claim.

A check with no ``command`` runs the CI step's own ``run:`` script, so the
local command cannot drift from CI's. A check with a ``command`` says in
``note`` why it differs. A check with ``paths`` runs on a narrower diff than
its workflow's filter and says why in ``narrowed``.

The :data:`GUARD_TESTS` are pytest files that CI runs inside the full suite
and the local targeted set reaches too late or not at all. Most are the
limit-enforcing ones the #5580 audit found failing CI after a push the local
gate let through: each sits outside the targeted set of some diff that breaks
it, or runs on a docs-typed PR, which runs no pytest at all. The rest read
only files that name no Python symbol, such as a workflow, so no diff over
them selects the test that checks them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.planning.ci_mirror._workflows import StepKey

#: ``{placeholder}`` values a check's ``command`` and ``env`` may name:
#: ``base`` (the base branch name), ``base_ref`` (``origin/<base>``),
#: ``merge_base`` (its SHA) and ``pr`` (the PR number, when known).
Placeholders = Mapping[str, str]


@dataclass(frozen=True)
class CheckContext:
    """What a check's command may depend on."""

    placeholders: Placeholders
    changed: tuple[str, ...]
    root: Path

    def present(self) -> list[str]:
        """The changed paths that still exist: a deletion has nothing to lint."""
        return [p for p in self.changed if (self.root / p).is_file()]


#: Builds a check's argv from the diff; ``None`` means the diff gives the
#: check nothing to read, so it does not run.
CommandBuilder = Callable[[CheckContext], Sequence[str] | None]


@dataclass(frozen=True)
class MirrorCheck:
    """One local command standing for one CI step (or for a guard set)."""

    id: str
    step: StepKey | None
    command: Sequence[str] | CommandBuilder | None = None
    note: str = ""
    paths: tuple[str, ...] | None = None
    narrowed: str = ""
    env: Mapping[str, str] = field(default_factory=dict)
    group: str | None = None
    tool: str | None = None
    needs_pr: bool = False
    #: Runs after every other check, by itself: it writes into the tree others read.
    alone: bool = False
    #: Starts many processes or uses much memory, so it takes one of the host's
    #: heavy-check slots, shared with this mirror's other heavy checks (#5947).
    heavy: bool = False
    #: Step env values naming a GitHub expression that run without it locally,
    #: each with why; parity refuses an expression neither here nor in ``env``.
    drops_env: Mapping[str, str] = field(default_factory=dict)


_PY = "python-app.yml"
_SPEC = "spec-check.yml"
_DOCS = "docs-build-check.yml::docs-build-check::"
_SITE = _DOCS + "Check site publication > "
_UI = "ui.yml::ui::"

#: Inputs of the site build and of every check that reads the built site.
#: Narrower than docs-build-check.yml's filter, which adds ``vultron/**`` and
#: ``specs/**``: a local ``mkdocs build --strict`` takes about six minutes, and
#: every site-publication failure the #5580 audit found changed a page.
SITE_PATHS = (
    "docs/**",
    "overrides/**",
    "references.bib",
    "mkdocs.yml",
    # Root pages that docs/ pages pull in with include-markdown.
    "CONTRIBUTING.md",
    "ContributionInstructions.md",
    "LICENSE.md",
    "Acknowledgements.md",
    "uv.lock",
    "vultron/metadata/docs/**",
    ".github/actions/build-site/**",
    ".github/actions/check-site-publication/**",
    ".github/workflows/docs-build-check.yml",
)
_SITE_NARROWED = (
    "the site build takes about six minutes locally; it runs when a page or "
    "a site input changes, which every site-publication failure in the #5580 "
    "audit did"
)

#: Tests the targeted set reaches too late or not at all: the limit-enforcing
#: ones the #5580 audit traced CI failures to, plus any whose only inputs are
#: files no changed Python symbol selects — a workflow or config file.
GUARD_TESTS = (
    "test/architecture/test_line_length_ratchet.py",
    "test/architecture/test_spec_statement_guard.py",
    "test/architecture/test_spec_kind_ratchet.py",
    "test/architecture/test_vocab_examples_current.py",
    # Reads `.github/workflows/`, so a workflow-only diff names no Python
    # symbol and the targeted set selects nothing that checks it (PAD-18-023).
    "test/ci/test_python_app_test_parts.py",
    "test/core/behaviors/test_btnd07_structure.py",
    "test/metadata/test_agents_md_size_ratchet.py",
    "test/metadata/test_adr_back_edges.py",
    # Reads the skills' Markdown, which no CI pytest path filter lists, so a
    # skill-only PR that drops a gate's ceiling or heavy-check slot reaches
    # CI's suite only on a later PR (#5947).
    "test/metadata/test_gate_ceiling.py",
    "test/metadata/test_no_decision_record_part_citations.py",
    "test/metadata/test_msm_occasions.py",
    "test/metadata/docs/test_page_frontmatter.py",
    "test/metadata/docs/test_level_order.py",
)

_MARKDOWN_CONFIGS = (".markdownlint-cli2.yaml", ".markdownlint-cli2.jsonc")


def markdownlint_command(context: CheckContext) -> list[str] | None:
    """markdownlint over the branch's Markdown, or the tree on a config change.

    CI lints ``**/*.md``. ``main`` passes that, so the branch's own files are
    what can fail, unless a lint config changed, which can fail any file.
    Each root and nested config file counts.
    """
    base = ["markdownlint-cli2", "--config", ".markdownlint-cli2.yaml"]
    if any(p.endswith(_MARKDOWN_CONFIGS) for p in context.changed):
        return [*base, "**/*.md"]
    files = [p for p in context.present() if p.endswith(".md")]
    return [*base, *files] if files else None


#: The memo wrapper of :func:`_memoized`, relative to the repository root.
RUN_IF_CHANGED = ".agents/skills/shared/run-if-changed.sh"


def _memoized(tool: str, *inputs: str) -> tuple[str, ...]:
    return (
        "bash",
        RUN_IF_CHANGED,
        tool,
        *inputs,
        "--",
        "uv",
        "run",
        tool,
    )


_MEMOIZED_NOTE = (
    "run through run-if-changed.sh, which skips the tool when its inputs are "
    "unchanged since its last pass (ADR-0094)"
)

MIRROR_CHECKS: tuple[MirrorCheck, ...] = (
    MirrorCheck("ruff-check", f"{_PY}::lint-ruff::Lint with ruff"),
    MirrorCheck(
        "ruff-format", f"{_PY}::lint-ruff::Check formatting with ruff"
    ),
    MirrorCheck(
        "mypy",
        f"{_PY}::lint-mypy::Type-check with mypy",
        command=_memoized("mypy", "vultron/", "test/", ".mypy.ini", "uv.lock"),
        note=_MEMOIZED_NOTE,
    ),
    MirrorCheck(
        "pyright",
        f"{_PY}::lint-pyright::Type-check with pyright",
        command=_memoized(
            "pyright", "vultron/", "test/", "pyrightconfig.json", "uv.lock"
        ),
        note=_MEMOIZED_NOTE,
        heavy=True,
    ),
    MirrorCheck(
        "package-build",
        f"{_PY}::build::Build package",
        paths=("pyproject.toml", "uv.lock", "MANIFEST.in"),
        narrowed=(
            "a package build takes about 30 s and reads only the build "
            "configuration; a source change cannot fail it"
        ),
        # `uv build` unpacks the sdist into the repository root while it
        # runs, which a concurrent tree walk (the AGENTS.md ratchet) collects.
        alone=True,
    ),
    MirrorCheck(
        "guard-tests",
        None,
        command=(
            *("uv", "run", "pytest", "-m", "", "-n", "auto", "--tb=short"),
            *GUARD_TESTS,
        ),
        heavy=True,
        note=(
            "CI runs these inside the full suite, which the mirror leaves to "
            "create-pr and CI; the #5580 audit traced CI failures to each"
        ),
    ),
    MirrorCheck("spec-lint", f"{_SPEC}::spec-lint::Run spec-lint"),
    MirrorCheck(
        "spec-corpus",
        f"{_SPEC}::spec-tests::Run spec_corpus pytest suite",
        command=(
            *("uv", "run", "pytest", "-m", "spec_corpus", "-n", "auto"),
            "--tb=short",
        ),
        note="adds -n auto; the serial run is several times slower locally",
        heavy=True,
    ),
    MirrorCheck(
        "story-page-shape",
        f"{_SPEC}::spec-tests::Run user-story page shape test",
    ),
    MirrorCheck(
        "docs-path-ratchet",
        f"{_SPEC}::docs-path-ratchet::Run codebase docs path ratchet",
    ),
    MirrorCheck(
        "adr-lifecycle",
        "adr-lifecycle.yml::adr-lifecycle-check::"
        "Check the ADRs this pull request changes",
        env={"BASE_REF": "{base}"},
    ),
    MirrorCheck(
        "markdownlint",
        "lint_md_all.yml::lint::DavidAnson/markdownlint-cli2-action",
        command=markdownlint_command,
        note=(
            "the branch's Markdown files, or the whole tree when a lint "
            "config changed; CI's whole-tree glob costs about 40 s"
        ),
        tool="markdownlint-cli2",
    ),
    MirrorCheck(
        "actionlint",
        "actions-lint.yml::actionlint::Run actionlint",
        tool="actionlint",
    ),
    MirrorCheck(
        "demo-matrix",
        "actions-lint.yml::actionlint::Validate demo scenario matrix",
        tool="jq",
    ),
    MirrorCheck(
        "closing-pr-owners",
        "verification-debt-owners.yml::closing-pr::"
        "Check the owner issues this PR closes",
        env={"PR_NUMBER": "{pr}"},
        drops_env={"GH_TOKEN": "the local gh CLI reads its own login"},
        needs_pr=True,
    ),
    *(
        MirrorCheck(check_id, _DOCS + label)
        for check_id, label in (
            ("adr-index", "ADR index in sync, and no ADR in the nav"),
            ("docs-frontmatter", "Page frontmatter (DF-11-001)"),
            (
                "docs-normative-banner",
                "Normative banner on exactly its pages (DF-12-006)",
            ),
            (
                "docs-nav-subjects",
                "No nav section mixes protocol and implementation pages "
                "(DF-11-020)",
            ),
            (
                "docs-level-order",
                "No page depends on a page above its level (DF-11-002)",
            ),
            (
                "docs-site",
                "Landing pages, reading-path boxes and coverage matrix in "
                "sync (DF-11-005)",
            ),
            (
                "docs-threads",
                "Reading-path threads list only reader-facing pages "
                "(DF-11-016)",
            ),
            (
                "docs-thread-order",
                "No thread page depends on a later member's term (DF-11-024)",
            ),
            ("msm-occasions", "Occasion table and message fragments in sync"),
            (
                "demo-scenarios",
                "Demo scenario artifacts in sync (DEMOCI-11-005)",
            ),
            (
                "wire-context",
                "JSON-LD context in sync with the wire vocabulary (VM-10-001)",
            ),
        )
    ),
    *(
        MirrorCheck(
            check_id,
            label,
            paths=SITE_PATHS,
            narrowed=_SITE_NARROWED,
            group="site",
            heavy=check_id == "site-build",
        )
        for check_id, label in (
            ("site-build", _DOCS + "Build Site > Build Site"),
            (
                "docs-withheld",
                _SITE + "Check withheld artifacts are unpublished",
            ),
            ("docs-legacy-urls", _SITE + "Check published URLs still resolve"),
            ("docs-links", _SITE + "Check internal references resolve"),
            ("docs-path-boxes", _SITE + "Check reading-path boxes"),
            ("docs-recorded", _SITE + "Check every built page is recorded"),
        )
    ),
    MirrorCheck(
        "ui-install", _UI + "Install dependencies", group="ui", tool="npm"
    ),
    MirrorCheck("ui-lint", _UI + "Lint", group="ui", tool="npm"),
    MirrorCheck("ui-build", _UI + "Build", group="ui", tool="npm"),
)

#: CI steps the mirror does not run. A key is a whole workflow
#: (``<file>``), a job (``<file>::<job>``), a step (its full key), or every
#: step calling an action (``uses:<action>``).
EXCLUSIONS: Mapping[str, str] = {
    "uses:actions/checkout": "the mirror runs in the checkout it gates",
    "uses:./.github/actions/setup-python-uv": (
        "the worktree's own uv environment is the toolchain"
    ),
    "uses:actions/setup-node": "the local npm is the toolchain",
    "uses:./.github/actions/debounce-main-push": "acts only on a push to main",
    "uses:./.github/actions/notify-failure": (
        "files or closes CI-failure issues for main (CISEC-05); not a check"
    ),
    "uses:actions/upload-artifact": "moves artifacts between jobs; not a check",
    "actions-lint.yml::actionlint::Install actionlint": (
        "downloads the binary; the mirror needs actionlint on PATH instead"
    ),
    "demo-integration.yml": (
        "container demos need Docker and take many minutes; they stay CI's"
    ),
    "ci-gate.yml": (
        "waits on GitHub for the other checks on the PR's head commit and "
        "judges them; locally there are no checks to wait for"
    ),
    "pr-size-label.yml": (
        "labels the PR from GitHub's diff statistics; nothing to fail locally"
    ),
    f"{_PY}::test::Run this part of the pytest suite": (
        "the full suite runs once before the first push in create-pr "
        "(PAD-18-001); later pushes run the targeted set (PAD-18-002) and "
        "guard-tests, and CI runs the rest, one part per matrix leg"
    ),
    "verification-debt-owners.yml::open-owners": (
        "the job runs only off pull_request (its if: excludes the event)"
    ),
}
