"""The PR body rule table and the path sets the docs rules judge (PAD-20)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Stage(StrEnum):
    """When the body is linted: before the first push, or once it is final."""

    PRE_PUSH = "pre-push"
    FINAL = "final"


class PrType(StrEnum):
    """The two body templates of ``pr-body-guide.md``."""

    IMPLEMENTATION = "implementation"
    DOCS = "docs"


@dataclass(frozen=True)
class Rule:
    """One mechanical rule: its stable ID, short name, and what it checks."""

    rule_id: str
    name: str
    summary: str


#: Every rule, in the order the guide lists them. IDs are stable: retire one
#: by leaving a gap, never by renumbering.
RULES: tuple[Rule, ...] = (
    Rule(
        "PRB-01",
        "closes-first",
        "Closing references (`Closes`/`Fixes`/`Resolves #N`) appear only in "
        "the opening block, before any other line of the body.",
    ),
    Rule(
        "PRB-02",
        "closes-one-per-line",
        "Each closing reference is its own `- Closes #N` bullet line.",
    ),
    Rule(
        "PRB-03",
        "required-sections",
        "`## Summary` and `## Changes` are present.",
    ),
    Rule(
        "PRB-04",
        "issues-line",
        "An implementation PR's `## Summary` ends with `Issues: closed N, "
        "opened M`, or with that line followed by the `Questions:` line.",
    ),
    Rule(
        "PRB-05",
        "specs-manifest",
        "An implementation PR has `## Specs` holding a Spec manifest: the "
        "`Loaded (floor)`, `Loaded (cross-cutting)`, `Loaded (selected)` and "
        "`Considered, skipped` lines, with no `..` ID ranges.",
    ),
    Rule(
        "PRB-06",
        "manifest-verbatim",
        "With `--manifest`, every line of the manifest `spec-backstop` "
        "resolved appears in `## Specs` unchanged.",
    ),
    Rule(
        "PRB-07",
        "verification-section",
        "`## Verification` is present when the diff changes a `.py` file.",
    ),
    Rule(
        "PRB-08",
        "docs-line",
        "An implementation PR, or one closing a Task, Feature or Bug, has a "
        "line beginning `Docs:`; at the final "
        "stage it is not the placeholder and takes a final form "
        "(`updated …`, `no docs impact — …`, `no maintainer docs impact — …`, "
        "`deferred to #N`).",
    ),
    Rule(
        "PRB-09",
        "spec-amended",
        "When `spec-amendments.sh` lists IDs, `## Spec amended` has a "
        "`### <ID>` block for each; at the final stage no `<TODO>` is left.",
    ),
    Rule(
        "PRB-10",
        "attribution-last",
        "An attribution line (`Generated with [...]`) is the body's last "
        "non-blank line.",
    ),
    Rule(
        "PRB-11",
        "body-length",
        "The body is at most GitHub's 65,536-character limit, at every stage.",
    ),
    Rule(
        "PRB-12",
        "maintainer-docs-followup",
        "When the diff changes a workflow or tooling file and no "
        "maintainer-facing doc, a `Docs:` line exists; at the final stage it "
        "names the follow-up issue (`deferred to #N`) or says why no "
        "maintainer doc needs the change (`no maintainer docs impact — …`).",
    ),
    Rule(
        "PRB-13",
        "questions-line",
        "An implementation PR's `## Summary` ends with `Questions: asked N, "
        "filed M`, directly after the `Issues:` line.",
    ),
    Rule(
        "PRB-14",
        "part-of-unlinked",
        "A `Part of #N` line names an issue the PR does not close: the head "
        "branch is not #N's claim branch `<prefix>/<N>-<slug>`, and the open "
        "PR's `closingIssuesReferences` does not hold N.",
    ),
)


RULES_BY_ID: dict[str, Rule] = {rule.rule_id: rule for rule in RULES}


DOCS_PLACEHOLDER = "Docs: pending check-docs-sync"


#: GitHub refuses a pull request body longer than this many characters.
BODY_LIMIT = 65_536


MANIFEST_LINES: tuple[str, ...] = (
    "Loaded (floor):",
    "Loaded (cross-cutting):",
    "Loaded (selected):",
    "Considered, skipped:",
)


#: Path prefixes of workflow and tooling files: CI workflows and their
#: scripts, the skills agents run, the project's metadata tools, and the
#: development container and images (PRB-12).
TOOLING_PREFIXES: tuple[str, ...] = (
    ".github/workflows/",
    ".github/scripts/",
    ".github/actions/",
    ".agents/skills/",
    "vultron/metadata/",
    "scripts/",
    ".devcontainer/",
    "docker/",
    ".githooks/",
)


#: Single tooling files at the repository root (PRB-12).
TOOLING_FILES: frozenset[str] = frozenset(
    {".pre-commit-config.yaml", "mdlint.sh", "Makefile", "start-dev.sh"}
)


#: Path prefixes of maintainer-facing documentation: the maintainer and agent
#: docs trees, design notes, and contributor instructions (PRB-12). Any
#: ``AGENTS.md`` and any Markdown file under ``.agents/skills/`` count too.
MAINTAINER_DOC_PREFIXES: tuple[str, ...] = (
    "docs/developer/",
    "docs/agents/",
    "notes/",
    ".github/instructions/",
)


MAINTAINER_DOC_FILES: frozenset[str] = frozenset(
    {
        "CONTRIBUTING.md",
        "README-DEV.md",
        ".devcontainer/README.md",
        ".github/copilot-instructions.md",
    }
)


def is_maintainer_doc(path: str) -> bool:
    """Whether *path* is maintainer-facing documentation (PD-03-006)."""
    return (
        path in MAINTAINER_DOC_FILES
        or path.startswith(MAINTAINER_DOC_PREFIXES)
        or Path(path).name == "AGENTS.md"
        or (path.startswith(".agents/skills/") and path.endswith(".md"))
    )


def undocumented_tooling(files: Sequence[str]) -> tuple[str, ...]:
    """The workflow or tooling files in *files*, when *files* has no doc.

    Empty when the diff changes no workflow or tooling file, or changes at
    least one maintainer-facing doc (PD-03-006): only a tooling change with
    no maintainer doc beside it needs a ``Docs:`` line to account for the
    gap (PD-03-014).
    """
    if any(is_maintainer_doc(f) for f in files):
        return ()
    return tuple(
        sorted(
            f
            for f in files
            if f in TOOLING_FILES or f.startswith(TOOLING_PREFIXES)
        )
    )
