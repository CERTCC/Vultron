"""Sweep-time report of ``plan`` notes whose tracked issues are all closed.

Report requirements: specs/notes-frontmatter.yaml NF-09.

The report only flags: a flagged note is a sweep agenda item, never an
automatic archive (NF-09-002).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from vultron.metadata.base import issue_number
from vultron.metadata.notes.loader import load_notes_registry
from vultron.metadata.notes.schema import NoteKind, NotesFrontmatter

REPO = "CERTCC/Vultron"
ISSUE_LIMIT = "10000"


class IssueState(StrEnum):
    """GitHub issue states as reported by ``gh``."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class TracksFinding:
    """One ``plan`` note the report flags, and why."""

    path: str
    reason: str


def plan_findings(
    registry: Mapping[str, NotesFrontmatter],
    states: Mapping[int, IssueState],
) -> list[TracksFinding]:
    """Flag ``plan`` notes that are retirement candidates or mis-tracked.

    A note is flagged when every issue it tracks is closed (NF-09-001), or
    when it tracks a number that is not a known issue — a pull request or a
    typo would otherwise keep the note alive forever.
    """
    findings: list[TracksFinding] = []
    for path, note in sorted(registry.items()):
        if note.kind != NoteKind.PLAN or not note.tracks:
            continue
        unknown = [t for t in note.tracks if issue_number(t) not in states]
        if unknown:
            findings.append(
                TracksFinding(path, f"tracks unknown issue(s) {unknown}")
            )
            continue
        if all(
            states[issue_number(t)] == IssueState.CLOSED for t in note.tracks
        ):
            findings.append(
                TracksFinding(
                    path,
                    "every tracked issue is closed "
                    f"({', '.join(note.tracks)}); review for archive "
                    "or promotion",
                )
            )
    return findings


def fetch_issue_states(repo: str = REPO) -> dict[int, IssueState]:
    """Return the state of every issue in *repo* via one ``gh`` call.

    Raises:
        RuntimeError: If ``gh`` cannot be run, exits non-zero, or returns
            output that is not a list of issue states.
    """
    try:
        result = _run_gh_issue_list(repo)
    except OSError as exc:
        raise RuntimeError(f"gh issue list could not run: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"gh issue list failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    try:
        return {
            int(item["number"]): IssueState(item["state"])
            for item in json.loads(result.stdout)
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            f"gh issue list returned unexpected output: {exc}"
        ) from exc


def _run_gh_issue_list(repo: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            ISSUE_LIMIT,
            "--json",
            "number,state",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI: ``notes-tracks`` — list plan notes due for sweep review."""
    parser = argparse.ArgumentParser(
        prog="notes-tracks",
        description=(
            "List plan notes whose tracked issues are all closed (NF-09). "
            "Advisory: always exits 0 unless the issue lookup fails."
        ),
    )
    parser.parse_args(argv)
    try:
        states = fetch_issue_states()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    findings = plan_findings(load_notes_registry(), states)
    for finding in findings:
        print(f"{finding.path}: {finding.reason}")
    if not findings:
        print("No plan notes due for review.")
