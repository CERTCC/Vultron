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
"""``pr-body-lint``: the mechanical rules of ``pr-body-guide.md``, as a tool.

A Pull Request body is judged against
``.agents/skills/shared/pr-body-guide.md``. The rules there that need no
judgment — where the closing references sit, which sections exist, what form
the ``Docs:`` line takes — are checked here, each under a stable ID that the
guide lists (:data:`RULES`), so the guide and the tool stay one list
(PAD-20-001, PAD-20-006). ``create-pr`` runs it on the composed body before the
first push (PAD-20-002); ``pr-triage`` runs it first in its body phases and judges only
what it cannot check, such as whether the body's claims match the diff
(PAD-20-004, PAD-20-009).

Usage::

    pr-body-lint --body body.md                     # facts from the branch diff
    pr-body-lint --body body.md --stage final       # after check-docs-sync
    pr-body-lint --body - --manifest /tmp/m.txt     # body on stdin
    gh pr view 4710 --json body,baseRefName,headRefOid \
      | pr-body-lint --pr-json - --stage final      # an open PR's body

Two stages: ``pre-push`` (default) accepts the placeholders ``create-pr``
writes — ``Docs: pending check-docs-sync`` and ``<TODO>`` in ``## Spec
amended`` — and ``final`` refuses them (PD-03-013).

Like the rest of ``planning/``, the tool never calls GitHub itself: an open
PR's body, base branch and head commit arrive as the ``gh pr view`` JSON
payload on stdin (or in a file), so the rules stay testable without the
network. The changed files and the spec amendments are read from the local
checkout, which must be at the PR's head commit: GitHub's ``files`` list stops
at 100 entries, so a large PR's ``.py`` files may be missing from it.

Both stages read the branch as committed, from its merge base with the base
ref: an uncommitted or untracked file in the worktree is not part of the PR.

Exit codes: 0 = clean; 1 = findings; 2 = setup error (unreadable body,
payload or manifest, bad base ref, a checkout not at the PR's head, failed
``spec-amendments.sh`` call).

Requirements: specs/parallel-development.yaml PAD-20;
specs/project-documentation.yaml PD-03-008, PD-03-013.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from vultron.metadata.markdown_tables import fenced_lines
from vultron.metadata.specs.backstop import (
    BackstopError,
    git_toplevel,
    merge_base,
    run_git,
)


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
        "opened M`.",
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
        "(`updated …`, `no docs impact — …`, `deferred to #N`).",
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

#: A reference GitHub closes on merge: a keyword, an optional colon, then
#: ``#N``, ``owner/repo#N`` or an issue URL.
_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+"
    r"(?:[\w.-]+/[\w.-]+#\d+|#\d+"
    r"|https://github\.com/[\w.-]+/[\w.-]+/issues/\d+)",
    re.I,
)
_CLOSES_BULLET_RE = re.compile(r"^- (?:Closes|Fixes|Resolves) #\d+$")
#: An inline code span; GitHub reads no closing keyword inside one.
_CODE_SPAN_RE = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_SECTION_LEVEL = 2
_BLOCK_LEVEL = 3
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_ISSUES_RE = re.compile(r"^Issues: closed \d+, opened \d+\b")
_RANGE_RE = re.compile(r"\b[A-Z]+-\d\d(?:-\d{3})?\.\.")
_ATTRIBUTION_RE = re.compile(r"Generated with \[[^\]]+\]\([^)]+\)")
_DOCS_FINAL_RE = re.compile(
    r"^Docs: (?:updated \S.*|no docs impact — \S.*|deferred to #\d+)$"
)


@dataclass(frozen=True)
class BodyFacts:
    """What the branch says about the PR, beyond the body text.

    Attributes:
        pr_type: Which template applies.
        py_changed: The diff changes at least one ``.py`` file.
        amended_ids: IDs ``spec-amendments.sh`` lists for the diff.
        stage: Whether the placeholders ``create-pr`` writes are accepted.
        manifest: The resolved Spec manifest text, when one was given.
        closes_work_item: The PR closes a ``Task``, ``Feature`` or ``Bug``,
            which needs a ``Docs:`` line whatever the template (PD-03-013).
    """

    pr_type: PrType
    py_changed: bool
    amended_ids: tuple[str, ...] = ()
    stage: Stage = Stage.PRE_PUSH
    manifest: str | None = None
    closes_work_item: bool = False

    @property
    def needs_docs_line(self) -> bool:
        """Whether PRB-08 applies: an implementation or work-item PR."""
        return self.pr_type is PrType.IMPLEMENTATION or self.closes_work_item


@dataclass(frozen=True)
class Finding:
    """One rule violation."""

    rule_id: str
    message: str

    def render(self) -> str:
        """``PRB-NN name: message``."""
        return (
            f"{self.rule_id} {RULES_BY_ID[self.rule_id].name}: {self.message}"
        )


@dataclass
class _Body:
    """The body split into lines and ``##`` sections.

    HTML comments are blanked (line count kept), and a line inside a fenced
    code block is never read as a heading or a closing reference: a manifest
    pasted in a ```` ```text ```` fence still belongs to its section.
    """

    text: str
    lines: list[str] = field(init=False)
    fenced: list[bool] = field(init=False)
    sections: dict[str, list[str]] = field(init=False)
    section_fenced: dict[str, list[bool]] = field(init=False)

    def __post_init__(self) -> None:
        bare = _COMMENT_RE.sub(
            lambda m: "\n" * m.group(0).count("\n"), self.text
        )
        self.lines = bare.splitlines()
        inside = fenced_lines(bare)
        self.fenced = [n in inside for n in range(1, len(self.lines) + 1)]
        self.sections = {}
        self.section_fenced = {}
        current: str | None = None
        for line, fenced in zip(self.lines, self.fenced, strict=True):
            heading = None if fenced else _HEADING_RE.match(line)
            if heading and len(heading.group(1)) == _SECTION_LEVEL:
                name: str = heading.group(2)
                current = name
                self.sections.setdefault(name, [])
                self.section_fenced.setdefault(name, [])
                continue
            if current is not None:
                self.sections[current].append(line)
                self.section_fenced[current].append(fenced)

    def section(self, name: str) -> list[str] | None:
        """The lines under ``## <name>`` up to the next ``##``, or ``None``."""
        return self.sections.get(name)


def _check_closing(body: _Body) -> Iterator[Finding]:
    """PRB-01 and PRB-02."""
    in_opening = True
    for number, (line, fenced) in enumerate(
        zip(body.lines, body.fenced, strict=True), start=1
    ):
        stripped = line.strip()
        if not stripped:
            continue
        if fenced:
            in_opening = False
            continue
        refs = _CLOSING_RE.findall(_CODE_SPAN_RE.sub("", stripped))
        if in_opening and refs:
            if len(refs) > 1 or not _CLOSES_BULLET_RE.match(stripped):
                yield Finding(
                    "PRB-02",
                    f"line {number} is not a single `- Closes #N` bullet: "
                    f"{stripped!r}",
                )
            continue
        in_opening = False
        if refs:
            yield Finding(
                "PRB-01",
                f"line {number} carries a closing reference after the opening "
                f"block ({', '.join(refs)}); move it to the top as its own "
                f"`- Closes #N` line, or reword it so GitHub does not close "
                f"the issue",
            )


def _check_sections(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-03, PRB-04 and PRB-07."""
    for name in ("Summary", "Changes"):
        if body.section(name) is None:
            yield Finding("PRB-03", f"no `## {name}` section")
    summary = body.section("Summary")
    if facts.pr_type is PrType.IMPLEMENTATION and summary is not None:
        last = next((ln.strip() for ln in reversed(summary) if ln.strip()), "")
        if not _ISSUES_RE.match(last):
            yield Finding(
                "PRB-04",
                "the last line of `## Summary` is not `Issues: closed N, "
                "opened M`",
            )
    if facts.py_changed and body.section("Verification") is None:
        yield Finding(
            "PRB-07",
            "the diff changes `.py` files but there is no "
            "`## Verification` section",
        )


def _check_specs(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-05 and PRB-06."""
    if facts.pr_type is not PrType.IMPLEMENTATION:
        return
    specs = body.section("Specs")
    if specs is None:
        yield Finding("PRB-05", "no `## Specs` section")
        return
    stripped = [ln.strip().lstrip("-*+ ").replace("*", "") for ln in specs]
    for label in MANIFEST_LINES:
        if not any(ln.startswith(label) for ln in stripped):
            yield Finding(
                "PRB-05",
                f"`## Specs` has no `{label}` line; paste the Spec manifest "
                f"deepen-context returned, not a list of IDs",
            )
    for line in specs:
        if _RANGE_RE.search(line):
            yield Finding(
                "PRB-05",
                f"`## Specs` writes an ID range ({line.strip()!r}); list every "
                f"ID in full",
            )
    if facts.manifest is not None:
        present = {ln.strip() for ln in specs}
        for line in facts.manifest.splitlines():
            if line.strip() and line.strip() not in present:
                yield Finding(
                    "PRB-06",
                    f"the resolved manifest line {line.strip()!r} is not in "
                    f"`## Specs` verbatim; copy the manifest file, do not "
                    f"retype it",
                )


def _check_docs(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-08."""
    if not facts.needs_docs_line:
        return
    docs = [
        ln.strip()
        for ln, fenced in zip(body.lines, body.fenced, strict=True)
        if not fenced and ln.strip().startswith("Docs:")
    ]
    if not docs:
        yield Finding(
            "PRB-08",
            f"no `Docs:` line; create-pr writes `{DOCS_PLACEHOLDER}` and "
            f"check-docs-sync replaces it",
        )
        return
    if facts.stage is not Stage.FINAL:
        return
    for line in docs:
        if line == DOCS_PLACEHOLDER:
            yield Finding(
                "PRB-08",
                "the `Docs:` line is still the placeholder; replace it with "
                "the line check-docs-sync reported (PD-03-013)",
            )
        elif not _DOCS_FINAL_RE.match(line):
            yield Finding(
                "PRB-08",
                f"{line!r} is not a final `Docs:` form: `updated <page>, ...`, "
                f"`no docs impact — <reason>`, or `deferred to #N`",
            )


def _check_amended(body: _Body, facts: BodyFacts) -> Iterator[Finding]:
    """PRB-09."""
    if not facts.amended_ids:
        return
    section = body.section("Spec amended")
    if section is None:
        yield Finding(
            "PRB-09",
            f"spec-amendments.sh lists {', '.join(facts.amended_ids)} but "
            f"there is no `## Spec amended` section",
        )
        return
    fenced = body.section_fenced["Spec amended"]
    blocks = {
        m.group(2).strip()
        for ln, in_fence in zip(section, fenced, strict=True)
        if not in_fence
        and (m := _HEADING_RE.match(ln))
        and len(m.group(1)) == _BLOCK_LEVEL
    }
    for spec_id in facts.amended_ids:
        if spec_id not in blocks:
            yield Finding(
                "PRB-09", f"`## Spec amended` has no `### {spec_id}` block"
            )
    if facts.stage is Stage.FINAL and any("<TODO" in ln for ln in section):
        yield Finding(
            "PRB-09",
            "`## Spec amended` still holds a `<TODO>` field; fill it from "
            "the specs/ diff",
        )


def _check_attribution(body: _Body) -> Iterator[Finding]:
    """PRB-10."""
    filled = [(n, ln) for n, ln in enumerate(body.lines, 1) if ln.strip()]
    marked = [n for n, ln in filled if _ATTRIBUTION_RE.search(ln)]
    if marked and marked[-1] != filled[-1][0]:
        yield Finding(
            "PRB-10",
            f"the attribution line (line {marked[-1]}) is not the last line "
            f"of the body",
        )


def _check_length(text: str) -> Iterator[Finding]:
    """PRB-11."""
    if len(text) > BODY_LIMIT:
        yield Finding(
            "PRB-11",
            f"the body is {len(text):,} characters, over GitHub's "
            f"{BODY_LIMIT:,}-character limit; shorten it (a long "
            f"`## Spec amended` statement can show its changed span)",
        )


def lint_body(text: str, facts: BodyFacts) -> list[Finding]:
    """Every finding for the body *text*, in rule order."""
    body = _Body(text)
    findings = [
        *_check_closing(body),
        *_check_sections(body, facts),
        *_check_specs(body, facts),
        *_check_docs(body, facts),
        *_check_amended(body, facts),
        *_check_attribution(body),
        *_check_length(text),
    ]
    order = {rule.rule_id: i for i, rule in enumerate(RULES)}
    return sorted(findings, key=lambda f: order[f.rule_id])


# --- fact gathering ---------------------------------------------------------

Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


class SetupError(Exception):
    """The body, the manifest, the diff or a helper could not be read."""


def _run(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - fixed argv
        list(argv), cwd=cwd, capture_output=True, text=True, check=False
    )


def amended_ids(
    root: Path, base: str, head: str = "HEAD", run: Runner = _run
) -> tuple[str, ...]:
    """IDs ``spec-amendments.sh`` lists for *base*...*head*.

    Raises:
        SetupError: the script exits 2 (bad ref, unreadable spec file).
    """
    script = root / ".agents" / "skills" / "shared" / "spec-amendments.sh"
    proc = run(["bash", str(script), base, head], root)
    if proc.returncode not in (0, 1):
        raise SetupError(
            f"spec-amendments.sh {base} {head} exited {proc.returncode}: "
            f"{proc.stderr.strip()}"
        )
    return tuple(
        line.split("\t", 1)[0] for line in proc.stdout.splitlines() if line
    )


def _branch_files(root: Path, base: str) -> list[str]:
    """Paths the branch's commits change since its merge base with *base*.

    Committed work only, as ``spec-amendments.sh`` reads it: a scratch file
    left in the worktree is not part of the PR.
    """
    try:
        git = run_git(root)
        start = merge_base(git, base)
        listing = git(["diff", "--name-only", "--no-renames", start, "HEAD"])
    except BackstopError as exc:
        raise SetupError(str(exc)) from exc
    return sorted(set(listing.splitlines()))


def _head_sha(root: Path) -> str:
    try:
        return run_git(root)(["rev-parse", "HEAD"]).strip()
    except BackstopError as exc:
        raise SetupError(str(exc)) from exc


_PAYLOAD_FIELDS = "body,baseRefName,headRefOid"


def _pr_payload(path: str) -> dict[str, object]:
    """The ``gh pr view --json body,baseRefName,headRefOid`` payload."""
    try:
        view = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise SetupError(f"--pr-json {path}: not JSON: {exc}") from exc
    if (
        not isinstance(view, dict)
        or not isinstance(view.get("body"), str)
        or not isinstance(view.get("headRefOid"), str)
    ):
        raise SetupError(
            f"--pr-json {path}: expected the object `gh pr view --json "
            f"{_PAYLOAD_FIELDS}` prints"
        )
    return view


def _read(path: str) -> str:
    try:
        return sys.stdin.read() if path == "-" else Path(path).read_text()
    except OSError as exc:
        raise SetupError(f"cannot read {path}: {exc}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-body-lint",
        description="Check a PR body against the mechanical rules of "
        "pr-body-guide.md.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--body", help="Body file, or - for stdin")
    source.add_argument(
        "--pr-json",
        help=f"The `gh pr view --json {_PAYLOAD_FIELDS}` payload of an open "
        "PR, or - for stdin; the changed files and spec amendments are read "
        "from the local checkout, which must be at the PR's head commit",
    )
    parser.add_argument(
        "--base",
        help="Diff base (default origin/main, or origin/<base branch> with "
        "--pr-json)",
    )
    parser.add_argument(
        "--type",
        choices=[t.value for t in PrType],
        help="Body template; default: implementation when .py changed",
    )
    parser.add_argument(
        "--stage",
        choices=[s.value for s in Stage],
        default=Stage.PRE_PUSH.value,
        help="pre-push accepts create-pr's placeholders; final refuses them",
    )
    parser.add_argument(
        "--manifest", help="The resolved Spec manifest file (PRB-06)"
    )
    parser.add_argument(
        "--closes-work-item",
        action="store_true",
        help="The PR closes a Task, Feature or Bug: require a Docs: line "
        "even on a docs PR (PD-03-013)",
    )
    parser.add_argument(
        "--list-rules", action="store_true", help="Print the rules and exit"
    )
    return parser


def _gather(
    args: argparse.Namespace, root: Path, run: Runner
) -> tuple[str, BodyFacts]:
    base = args.base or "origin/main"
    if args.pr_json is not None:
        view = _pr_payload(args.pr_json)
        text = str(view["body"])
        if args.base is None and view.get("baseRefName"):
            base = f"origin/{view['baseRefName']}"
        head = _head_sha(root)
        if view["headRefOid"] != head:
            raise SetupError(
                f"--pr-json: the checkout is at {head[:12]}, not the PR's "
                f"head {str(view['headRefOid'])[:12]}; check out the PR "
                f"branch at its pushed commit"
            )
    else:
        text = _read(args.body)
    files = _branch_files(root, base)
    py_changed = any(f.endswith(".py") for f in files)
    if args.type:
        pr_type = PrType(args.type)
    else:
        pr_type = PrType.IMPLEMENTATION if py_changed else PrType.DOCS
    facts = BodyFacts(
        pr_type=pr_type,
        py_changed=py_changed,
        amended_ids=amended_ids(root, base, run=run),
        stage=Stage(args.stage),
        manifest=_read(args.manifest) if args.manifest else None,
        closes_work_item=args.closes_work_item,
    )
    return text, facts


def main(argv: Sequence[str] | None = None, run: Runner = _run) -> int:
    """CLI entry point; returns the exit code (see the module docstring)."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list_rules:
        for rule in RULES:
            print(f"{rule.rule_id} {rule.name}: {rule.summary}")
        return 0
    if args.body is None and args.pr_json is None:
        parser.error("one of --body or --pr-json is required")
    try:
        root = git_toplevel(Path.cwd())
        text, facts = _gather(args, root, run)
    except (SetupError, BackstopError) as exc:
        print(f"pr-body-lint: {exc}", file=sys.stderr)
        return 2
    findings = lint_body(text, facts)
    for finding in findings:
        print(finding.render())
    print(
        f"pr-body-lint: {len(findings)} finding(s) "
        f"({facts.pr_type.value} PR, {facts.stage.value} stage)",
        file=sys.stderr,
    )
    return 1 if findings else 0


def cli() -> None:
    """Console-script wrapper: ``sys.exit(main())``."""
    sys.exit(main())


__all__ = [
    "DOCS_PLACEHOLDER",
    "MANIFEST_LINES",
    "RULES",
    "RULES_BY_ID",
    "BodyFacts",
    "Finding",
    "PrType",
    "Rule",
    "SetupError",
    "Stage",
    "amended_ids",
    "cli",
    "lint_body",
    "main",
]
