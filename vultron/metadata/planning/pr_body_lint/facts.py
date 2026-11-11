"""Gather a PR's body and branch facts from git and ``gh pr view``."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.planning.pr_body_lint.rules import (
    PrType,
    Stage,
    undocumented_tooling,
)
from vultron.metadata.specs.backstop import (
    BackstopError,
    merge_base,
    run_git,
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
        undocumented_tooling: The workflow or tooling files the diff changes
            when it changes no maintainer-facing doc (PD-03-014); see
            :func:`undocumented_tooling`.
        head_branch: The PR's head branch, or ``None`` on a detached
            checkout; PRB-14 refuses a `Part of #N` body on #N's claim branch.
        closing_refs: The issue numbers GitHub will close when the open PR
            merges (its ``closingIssuesReferences``); empty before the PR
            exists. A linked claim branch puts its issue here with no closing
            keyword in the body (PAD-04-008).
    """

    pr_type: PrType
    py_changed: bool
    amended_ids: tuple[str, ...] = ()
    stage: Stage = Stage.PRE_PUSH
    manifest: str | None = None
    closes_work_item: bool = False
    undocumented_tooling: tuple[str, ...] = ()
    head_branch: str | None = None
    closing_refs: tuple[int, ...] = ()

    @property
    def needs_docs_line(self) -> bool:
        """Whether PRB-08 applies: an implementation or work-item PR."""
        return self.pr_type is PrType.IMPLEMENTATION or self.closes_work_item


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


def _current_branch(root: Path) -> str | None:
    """The checked-out branch, or ``None`` on a detached ``HEAD``."""
    try:
        name = run_git(root)(["branch", "--show-current"]).strip()
    except BackstopError as exc:
        raise SetupError(str(exc)) from exc
    return name or None


_PAYLOAD_FIELDS = (
    "body,baseRefName,headRefName,headRefOid,closingIssuesReferences"
)


def _closing_refs(view: dict[str, object]) -> tuple[int, ...] | None:
    """The issue numbers in ``closingIssuesReferences``, or ``None`` if bad."""
    refs = view.get("closingIssuesReferences")
    if not isinstance(refs, list):
        return None
    numbers: list[int] = []
    for ref in refs:
        number = ref.get("number") if isinstance(ref, dict) else None
        if not isinstance(number, int) or isinstance(number, bool):
            return None
        numbers.append(number)
    return tuple(numbers)


def _pr_payload(path: str) -> dict[str, object]:
    """The ``gh pr view --json`` payload of :data:`_PAYLOAD_FIELDS`.

    ``closingIssuesReferences`` is required: without it PRB-14 could not see
    the closing reference a linked claim branch adds, and would pass silently.
    """
    try:
        view = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise SetupError(f"--pr-json {path}: not JSON: {exc}") from exc
    if (
        not isinstance(view, dict)
        or not isinstance(view.get("body"), str)
        or not isinstance(view.get("headRefOid"), str)
        or not isinstance(view.get("headRefName"), str)
        or _closing_refs(view) is None
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


def _gather(
    args: argparse.Namespace, root: Path, run: Runner
) -> tuple[str, BodyFacts]:
    base = args.base or "origin/main"
    closing_refs: tuple[int, ...] = ()
    if args.pr_json is not None:
        view = _pr_payload(args.pr_json)
        text = str(view["body"])
        head_branch: str | None = str(view["headRefName"]) or None
        closing_refs = _closing_refs(view) or ()
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
        head_branch = _current_branch(root)
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
        undocumented_tooling=undocumented_tooling(files),
        head_branch=head_branch,
        closing_refs=closing_refs,
    )
    return text, facts
