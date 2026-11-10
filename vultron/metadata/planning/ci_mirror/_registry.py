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

Every check left here answers in seconds to a couple of minutes. The five
expensive ones — pyright, the spec-corpus suite, the guard-test set, the site
build and the checks that read the built site — are CI's, and each is in
:data:`EXCLUSIONS` under the job that owns it (PAD-18-023). They cost most of
the mirror's former median 824 seconds on every push, and the required
``CI gate`` judges the jobs that run them, so dropping them locally leaves no
check unenforced (PAD-18-031).
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
    #: No check declares it today: PAD-18-023 made every expensive one CI's.
    #: It stays for a CI step cheap enough to mirror and heavy enough to queue.
    heavy: bool = False
    #: Step env values naming a GitHub expression that run without it locally,
    #: each with why; parity refuses an expression neither here nor in ``env``.
    drops_env: Mapping[str, str] = field(default_factory=dict)


_PY = "python-app.yml"
_SPEC = "spec-check.yml"
_DOCS = "docs-build-check.yml::docs-build-check::"
_SITE = _DOCS + "Check site publication > "
_UI = "ui.yml::ui::"

#: The ``Check site publication`` steps that read the built site, by their
#: step label. Named here rather than inline in :data:`EXCLUSIONS` so a test
#: can pin every one of them against this list: pinning a representative left
#: four of the five covered by nothing (PAD-18-023).
SITE_READERS = (
    "Check withheld artifacts are unpublished",
    "Check published URLs still resolve",
    "Check internal references resolve",
    "Check reading-path boxes",
    "Check every built page is recorded",
)

#: The step-key prefix :data:`SITE_READERS` labels hang off, so a test can
#: rebuild the exclusion keys without restating the workflow and job.
SITE_READER_PREFIX = _SITE

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
        "package-build",
        f"{_PY}::build::Build package",
        paths=("pyproject.toml", "uv.lock", "MANIFEST.in"),
        narrowed=(
            "a package build takes about 30 s and reads only the build "
            "configuration; a source change cannot fail it"
        ),
        # `uv build` unpacks the sdist into the repository root while it runs,
        # which a concurrent tree walk collects. The walk that used to catch
        # it was the AGENTS.md ratchet, inside the guard-test check PAD-18-023
        # retired; the mirror still runs two — `markdownlint` over `**/*.md`
        # when a lint config changed, and `docs-path-ratchet`.
        alone=True,
    ),
    MirrorCheck("spec-lint", f"{_SPEC}::spec-lint::Run spec-lint"),
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
    "demo-verdict.yml": (
        "CI's demo-verdict job owns the base-versus-head comparison: it "
        "records the whole scenario tree twice, about 366 s a pass, and it "
        "reads the pull request's merge base and its labels, neither of which "
        "a pre-push run has. The required CI gate judges it, so nothing is "
        "merged past it unseen (PAD-18-023, PAD-18-031)"
    ),
    "ci-gate.yml": (
        "waits on GitHub for the other checks on the PR's head commit and "
        "judges them; locally there are no checks to wait for"
    ),
    "pr-size-label.yml": (
        "labels the PR from GitHub's diff statistics; nothing to fail locally"
    ),
    f"{_PY}::test::Run this part of the pytest suite": (
        "CI's test job owns the suite, one part per matrix leg, and the "
        "required CI gate judges it; no gate before a push runs it "
        "(PAD-18-008). Each push runs the branch diff's targeted set instead "
        "(PAD-18-001, PAD-18-002)"
    ),
    # PAD-18-023: the five checks that cost most of the mirror's former
    # median 824 s. Each names the CI job that owns it; the required
    # `CI gate` judges that job, so none is merged past unseen (PAD-18-031).
    f"{_PY}::lint-pyright::Type-check with pyright": (
        "CI's lint-pyright job owns pyright: it took a median of two minutes "
        "in each local linter step and enough memory to starve a parallel "
        "test run, against 81-149 s there (PAD-18-023, PAD-18-027)"
    ),
    f"{_SPEC}::spec-tests::Run spec_corpus pytest suite": (
        "CI's spec-tests job owns the spec-corpus suite: 230 s locally "
        "against about 1.8 min there (PAD-18-023)"
    ),
    "guard-tests.yml::guard-tests::Run the guard tests": (
        "CI's guard-tests job owns the guard set, on every pull request and "
        "so on the Markdown, specs/, AGENTS.md and notes/ inputs "
        "python-app.yml's path filters miss: 94 s locally (PAD-18-023)"
    ),
    _DOCS + "Build Site > Build Site": (
        "CI's docs-build-check job owns the site build: about six minutes "
        "locally against 2.7 min there. The build-docs skill still runs it "
        "when a docs/ page changes (PAD-18-023)"
    ),
    **{
        _SITE + label: (
            "CI's docs-build-check job owns it: it reads the built site, "
            "which the mirror no longer builds (PAD-18-023)"
        )
        for label in SITE_READERS
    },
    "verification-debt-owners.yml::open-owners": (
        "the job runs only off pull_request (its if: excludes the event)"
    ),
}
