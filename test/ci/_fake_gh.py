"""A stand-in ``gh`` CLI for running bot issue-filing shell scripts in tests.

The scripts under ``.github/scripts/`` and the ``run:`` steps that call them
(``notify-failure``, ``demo-recordings.yml``) talk to GitHub only through
``gh``. :func:`install_fake_gh` puts a fake one first on ``PATH`` that logs
every call and answers each with canned data:

- the list-issues REST call gets the JSON page ``FAKE_ISSUES_PAGE``, filtered
  through the caller's real ``--jq`` expression, while a search-backed
  ``gh issue list`` answers with nothing, as the lagging search index did when
  it let the ADR Status Drift workflow file a second tracker (#5105). With
  ``FAKE_API_FAIL`` set, the list-issues call fails as an API error would;
- the triage helper's GraphQL issue query gets ``FAKE_ISSUE_JSON`` and its Epic
  lookup ``FAKE_EPIC_JSON``, each wrapped as a real response and run through
  the caller's real ``--jq`` expression. With ``FAKE_EPIC_FAIL`` set, the Epic
  lookup fails;
- a body written with ``gh issue edit --body-file <file>`` is saved to
  ``FAKE_BODY_OUT``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_FAKE_GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
jq_expr="" body_file="" prev=""
for arg in "$@"; do
  [ "$prev" = "--jq" ] && jq_expr="$arg"
  [ "$prev" = "--body-file" ] && body_file="$arg"
  prev="$arg"
done
# Answer a GraphQL issue query with {"data":{"repository":{"issue": $1}}},
# run through the caller's real --jq expression.
answer_issue() {
  printf '{"data":{"repository":{"issue":%s}}}' "$1" | jq -r "$jq_expr"
}
case "$1 $2" in
  "api graphql")
    case "$*" in
      *issueTypes*) printf 'Bug\tBUG_TYPE_ID\nTask\tTASK_TYPE_ID\n' ;;
      *addSubIssue*) echo "Set parent" ;;
      *subIssues*)
        if [ -n "${FAKE_EPIC_FAIL:-}" ]; then
          echo "HTTP 502: Bad Gateway" >&2
          exit 1
        fi
        answer_issue "$FAKE_EPIC_JSON" ;;
      *"labels(first"*) answer_issue "$FAKE_ISSUE_JSON" ;;
      *) echo "Set issue type" ;;
    esac ;;
  "api "*)
    for arg in "$@"; do
      case "$arg" in
        repos/*/issues\?*)
          if [ -n "${FAKE_API_FAIL:-}" ]; then
            echo "HTTP 502: Bad Gateway" >&2
            exit 1
          fi
          printf '%s' "$FAKE_ISSUES_PAGE" | jq -r "$jq_expr" ;;
      esac
    done ;;
  "issue view") printf 'ISSUE_NODE_ID\nBug\n' ;;
  "issue edit")
    if [ -n "$body_file" ]; then cp "$body_file" "$FAKE_BODY_OUT"; fi ;;
  "issue create") echo "https://github.com/OWNER/REPO/issues/999" ;;
esac
"""

UNTRIAGED_ISSUE: dict[str, object] = {
    "id": "ISSUE_NODE_ID",
    "body": "Original body.",
    "parent": None,
    "labels": {"nodes": [{"name": "ci:main-failure"}]},
}
"""A filed issue with no theme label, no ``Theme:`` line and no parent."""


def open_epic(theme: str, *, sub_issues: int = 38) -> dict[str, object]:
    """An open Epic carrying *theme*, as the Epic lookup sees it."""
    return {
        "id": "EPIC_NODE_ID",
        "state": "OPEN",
        "issueType": {"name": "Epic"},
        "subIssues": {"totalCount": sub_issues},
        "labels": {"nodes": [{"name": theme}]},
    }


@dataclass(frozen=True)
class FakeGh:
    """An installed fake ``gh``: the environment to run under, and its record."""

    env: dict[str, str]
    log: Path
    body_out: Path

    def calls(self) -> list[str]:
        """Every ``gh`` call made, one line of arguments each."""
        return self.log.read_text().splitlines()

    def written_body(self) -> str | None:
        """The body last written with ``--body-file``, if any."""
        if not self.body_out.exists():
            return None
        return self.body_out.read_text()


def install_fake_gh(
    tmp_path: Path,
    *,
    issues_page: list[dict[str, object]] | None = None,
    issue: dict[str, object] | None = None,
    epic: dict[str, object] | None = None,
    api_fails: bool = False,
    epic_lookup_fails: bool = False,
) -> FakeGh:
    """Write the fake ``gh`` under *tmp_path* and return how to run with it."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(_FAKE_GH)
    fake_gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.touch()
    body_out = tmp_path / "body.md"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH_LOG": str(log),
        "FAKE_ISSUES_PAGE": json.dumps(issues_page or []),
        "FAKE_ISSUE_JSON": json.dumps(
            UNTRIAGED_ISSUE if issue is None else issue
        ),
        "FAKE_EPIC_JSON": json.dumps(epic or open_epic("theme:test-and-ci")),
        "FAKE_BODY_OUT": str(body_out),
        "GH_TOKEN": "fake-token",
        # One attempt: a failure under test should not wait out retry.sh.
        "GH_RETRY_ATTEMPTS": "1",
    }
    if api_fails:
        env["FAKE_API_FAIL"] = "1"
    if epic_lookup_fails:
        env["FAKE_EPIC_FAIL"] = "1"
    return FakeGh(env=env, log=log, body_out=body_out)
