#!/usr/bin/env python3
"""Rewrite the standing "Theme fit report" Issue with a fresh ``theme-fit`` run.

The report Issue is found by its ``theme-fit-report`` label through the
list-issues endpoint, not the search index, whose lag once let a workflow
file a second tracker (#5105).
The oldest open one is rewritten; with none open, the oldest closed one is
reopened and rewritten; only with none at all is one created (PAD-14-005).
The run applies no labels to any other Issue and fixes nothing: it publishes
what ``theme-fit`` found (``notes/epic-themes.md`` § "The Structural Check").

A finding is the report's content, not a broken run: ``theme-fit`` exit 1
(findings) publishes like exit 0. Any other exit (the catalog or ``gh``
failed) fails the run, so ``notify-failure`` files a CI failure (CISEC-05).

The body keeps the Issue's existing ``Theme:`` lines, so a person who
re-themed it keeps their theme, and starts a new Issue on
:data:`DEFAULT_THEME`. ``ensure-issue-triage.sh`` then sets the theme label;
no parent is set (PAD-02-027), so the Issue is listed as untriaged until a
person routes it.

The decisions (``pick_report_issue``, ``compose_body``, ``report_usable``)
are pure functions so the test suite can pin them without the GitHub API.
Everything else is thin ``gh`` plumbing.

Usage: publish_theme_fit_report.py [--dry-run] [--repo OWNER/NAME]
       [--run-url URL]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

LABEL = "theme-fit-report"
TITLE = "Theme fit report"
DEFAULT_THEME = "theme:dev-workflow"
DEFAULT_OUTCOME = "keeps the theme-fit report current for routing and calving."
GITHUB_BODY_LIMIT = 65536
"""The most characters GitHub accepts in an Issue body."""
USABLE_EXITS = frozenset({0, 1})
"""``theme-fit`` exits: 0 no findings, 1 findings; 2 is a failed run."""
TRIAGE_HELPER = Path(__file__).resolve().parent / "ensure-issue-triage.sh"


def report_usable(returncode: int) -> bool:
    """True when a ``theme-fit`` exit status carries a report to publish."""
    return returncode in USABLE_EXITS


def pick_report_issue(
    items: Iterable[Mapping[str, object]],
) -> tuple[int, str] | None:
    """The ``(number, state)`` of the report Issue to rewrite, or ``None``.

    *items* are list-issues REST records for the report label, any state.
    Pull requests are skipped. The oldest open Issue wins; with none open,
    the oldest closed one, which the caller reopens. ``None`` means none
    exists and one must be created.
    """
    issues = sorted(
        (
            (int(str(i["number"])), str(i["state"]))
            for i in items
            if "pull_request" not in i
        ),
    )
    for wanted in ("open", "closed"):
        for number, state in issues:
            if state == wanted:
                return number, state
    return None


def theme_lines(body: str) -> list[str]:
    """The ``Theme:`` lines of *body*, in order."""
    return [
        line for line in body.splitlines() if line.split()[:1] == ["Theme:"]
    ]


def body_prefix(current_body: str | None, run_url: str | None) -> str:
    """Everything above the report: ``Theme:`` lines and the rewrite note."""
    themes = theme_lines(current_body or "") or [
        f"Theme: {DEFAULT_THEME} — {DEFAULT_OUTCOME}"
    ]
    run = f" Last rewritten by [this run]({run_url})." if run_url else ""
    note = (
        "The daily Theme Fit Report workflow rewrites this Issue from "
        "`uv run theme-fit`; an edit to anything but its `Theme:` lines "
        "is lost."
        f"{run} It is the `calve-epics` work list."
    )
    return "\n".join([*themes, "", note, "", ""])


def compose_body(prefix: str, report: str) -> str:
    """The whole Issue body: *prefix*, then the ``theme-fit`` *report*."""
    body = prefix + report
    if len(body) > GITHUB_BODY_LIMIT:
        raise ValueError(
            f"the report body is {len(body)} characters; "
            f"GitHub takes {GITHUB_BODY_LIMIT}"
        )
    return body


def _gh(*args: str) -> str:
    """``gh``'s stdout; on failure its stderr goes to the log, then it raises."""
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["gh", *args],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr or "")
        raise


def run_theme_fit(repo: str, max_chars: int) -> str:
    """The Markdown report, cut to *max_chars*; raises when the run failed."""
    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [  # noqa: S607
            "theme-fit",
            "--repo",
            repo,
            "--no-schedule",
            "--max-chars",
            str(max_chars),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if not report_usable(done.returncode):
        sys.stderr.write(done.stderr)
        raise RuntimeError(f"theme-fit exited {done.returncode}")
    return done.stdout


def report_candidates(repo: str) -> list[dict[str, object]]:
    """Every Issue with the report label, any state (list endpoint)."""
    pages = json.loads(
        _gh(
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repo}/issues?labels={LABEL}&state=all"
            "&sort=created&direction=asc&per_page=100",
        )
    )
    return [item for page in pages for item in page]


def _body_of(repo: str, number: int) -> str:
    issue = json.loads(_gh("api", f"repos/{repo}/issues/{number}"))
    body = issue.get("body")
    return body if isinstance(body, str) else ""


def _triage(repo: str, number: int) -> None:
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [  # noqa: S607
            "bash",
            str(TRIAGE_HELPER),
            repo,
            str(number),
            DEFAULT_THEME,
            DEFAULT_OUTCOME,
        ],
        check=True,
    )


def publish(repo: str, dry_run: bool, run_url: str | None) -> None:
    """Rewrite the report Issue, reopening or creating it as needed."""
    picked = pick_report_issue(report_candidates(repo))
    current = None if picked is None else _body_of(repo, picked[0])
    prefix = body_prefix(current, run_url)
    body = compose_body(
        prefix, run_theme_fit(repo, GITHUB_BODY_LIMIT - len(prefix))
    )
    if dry_run:
        target = "a new Issue" if picked is None else f"#{picked[0]}"
        print(f"Would write {len(body)} characters to {target}:\n")
        print(body, end="")
        return
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(body)
        body_file = fh.name
    try:
        if picked is None:
            _gh(
                "label",
                "create",
                LABEL,
                "--repo",
                repo,
                "--force",
                "--description",
                "Bot-managed: the standing theme-fit report",
                "--color",
                "5319E7",
            )
            url = _gh(
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                TITLE,
                "--body-file",
                body_file,
                "--label",
                LABEL,
            ).strip()
            number = int(url.rsplit("/", 1)[-1])
            print(f"Created #{number}")
        else:
            number, state = picked
            if state == "closed":
                _gh("issue", "reopen", str(number), "--repo", repo)
                print(f"Reopened #{number}")
            _gh(
                "issue",
                "edit",
                str(number),
                "--repo",
                repo,
                "--body-file",
                body_file,
            )
            print(f"Rewrote #{number}")
    finally:
        os.unlink(body_file)
    _triage(repo, number)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--run-url", default=os.environ.get("RUN_URL"))
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    publish(args.repo, args.dry_run, args.run_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
