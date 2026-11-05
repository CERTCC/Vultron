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

"""No tracked shell script uses a construct macOS's stock bash lacks (#5698).

macOS ships bash 3.2, and every script here runs with the first ``bash`` on
``PATH``: the repository's own tests run ``.github/scripts/*.sh`` that way, and
a contributor runs the ``.agents/skills`` scripts that way.  A bash 4-only
builtin therefore fails on a macOS host while passing on the Linux runners,
which turns a correct change into a red local gate and hides real failures
among known ones — ``ensure-issue-type.sh`` used ``mapfile`` and exited 127 for
three ``test/ci/test_bot_issue_triage.py`` tests (#5698), and
``sync-epic-schedules.sh`` used an associative array.

The check is a text scan over every tracked ``*.sh``, so a script added in a
new directory, or a renamed one, is still a subject.  The construct list is
bash's own vocabulary rather than any script's names, so a rename cannot drop a
subject out of it (``notes/testing-pitfalls.md`` § ratchets, #5535).  It is not
a complete inventory of bash 4 features; it carries the ones that have bitten
and the neighbours of each.

What it cannot see: a construct bash 3.2 *parses* but treats differently.  The
one that bites is ``"${empty[@]}"`` under ``set -u``, an unbound variable
before bash 4.4 — too ambiguous to spot in a text scan, since whether the
array can be empty is a question about the script's logic.  Expand such an
array as ``${a[@]+"${a[@]}"}``, as ``sync-epic-schedules.sh`` does.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from test.ci._workflows import REPO_ROOT, load_workflow, triggers

PYTHON_APP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-app.yml"

#: Scripts that MUST be in the scanned set.  A floor stated as named paths
#: rather than a count: a count races concurrent PRs that add a script (#3984),
#: and a scan that silently found nothing would pass having checked nothing.
REQUIRED_SUBJECTS = (
    ".github/scripts/ensure-issue-type.sh",
    ".github/scripts/ensure-issue-triage.sh",
    ".agents/skills/shared/sync-epic-schedules.sh",
    ".agents/skills/shared/claim-issue.sh",
    "mdlint.sh",
    "start-dev.sh",
)

#: ``(pattern, bash version, a line that uses it, portable alternative)``.
#: The sample is not decoration: ``test_the_scan_recognizes_every_construct``
#: feeds each one back through its own pattern, so a typo in a regex fails
#: here instead of letting the scan pass having matched nothing.
_BASH4_CONSTRUCTS: tuple[tuple[str, str, str, str], ...] = (
    (
        r"(?:^|[;&|(]\s*|\s)(?:mapfile|readarray)\b",
        "4.0",
        "mapfile -t lines < <(cat f)",
        "read the lines with `while IFS= read -r line` or a `read` per field",
    ),
    (
        r"\b(?:declare|local|typeset|readonly)\s+-[a-zA-Z]*A\b",
        "4.0",
        "declare -A TIER_OF",
        "use an indexed array when the keys are numbers, else parallel "
        "arrays or a `case` lookup",
    ),
    (
        r"(?:^|[;&|(]\s*|\s)coproc\b",
        "4.0",
        "coproc gh api graphql",
        "use a named pipe or a plain background job",
    ),
    (
        r"\|&",
        "4.0",
        "make |& tee build.log",
        "spell the redirection `2>&1 |`",
    ),
    (
        r"&>>",
        "4.0",
        "make &>> build.log",
        "spell the redirection `>>file 2>&1`",
    ),
    (
        r";;&",
        "4.0",
        "  Focus|Now) echo early ;;&",
        "repeat the `case` arm, or test the alternatives in sequence",
    ),
    (
        r"\$\{[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?(?:\^\^?|,,?)\}",
        "4.0",
        'echo "${tier^^}"',
        "case-fold with `tr '[:lower:]' '[:upper:]'`",
    ),
    (
        r"\bglobstar\b",
        "4.0",
        "shopt -s globstar",
        "walk the tree with `find`",
    ),
    (
        r"\bdeclare\s+-[a-zA-Z]*g\b",
        "4.2",
        "  declare -g RAISED=0",
        "assign at the top level, outside any function",
    ),
    (
        r"\[\[\s+-v\s",
        "4.2",
        "if [[ -v GH_TOKEN ]]; then",
        'test `[ -n "${name+set}" ]`',
    ),
    (
        r"%\([^)]*\)T",
        "4.2",
        "printf '%(%Y-%m-%d)T\\n' -1",
        "format the time with `date`",
    ),
    (
        r"(?:^|[;&|(]\s*|\s)wait\s+-n\b",
        "4.3",
        "wait -n",
        "`wait` for each recorded PID in turn",
    ),
    (
        r"\$\{[A-Za-z_][A-Za-z0-9_]*(?:\[[^]]*\])?@[QEPAKauL]\}",
        "4.4",
        'echo "${repo@Q}"',
        "quote with `printf %q`",
    ),
)

#: Lines a portable script really contains.  None may match any pattern: a
#: regex wide enough to flag these would make the scan unusable.
PORTABLE_LINES = (
    "type_id=$(awk -F '\\t' -v want=\"$type_name\" '$1 == want')",
    'IFS= read -r issue_node_id || issue_node_id=""',
    "declare -a TIER_OF ANCESTORS_OF",
    'for epic in ${EPICS[@]+"${EPICS[@]}"}; do',
    'echo "skip #$epic: not an open Epic" >&2',
    "gh issue view \"$num\" --json id --jq '.id'",
    "find . -name '*.sh' -print0 | xargs -0 grep -l bash",
    'printf "%s\\n" "${lines[@]}" >> "$log" 2>&1',
    'case "$t" in Focus|Now) echo yes ;; *) echo no ;; esac',
    "wait",
)

_COMPILED = tuple(
    (re.compile(pattern), version, fix)
    for pattern, version, _sample, fix in _BASH4_CONSTRUCTS
)


def _tracked_scripts() -> list[Path]:
    """Every tracked ``*.sh`` in the repository, as paths relative to the root.

    ``git ls-files`` rather than a glob, so a vendored or generated script that
    is not checked in is not a subject and a tracked one never escapes the scan
    by sitting in a directory this test has not heard of.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(name) for name in listed.split("\0") if name]


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_the_suite_runs_when_a_shell_script_changes(event: str) -> None:
    """The gate's own trigger list reaches it (DOCBW-03-015).

    A check is only installed if the workflow that runs it fires on the change
    it polices.  ``python-app.yml`` listed Python, YAML and the lockfile, so a
    pull request touching only ``.github/scripts/*.sh`` ran no suite at all and
    this scan would never have seen it — the #4506 shape.
    """
    paths = triggers(load_workflow(PYTHON_APP_WORKFLOW))[event]["paths"]
    assert "**/*.sh" in paths, (
        f"python-app.yml's {event} paths must include '**/*.sh', or a shell "
        "script can change without the suite that reads it running:\n"
        + "\n".join(f"  {pattern}" for pattern in paths)
    )
    # The dot-directories `**` may not descend into, named as `*.py` is.
    for directory in (".agents", ".github", ".devcontainer"):
        assert f"{directory}/**/*.sh" in paths, (
            f"python-app.yml's {event} paths must name "
            f"'{directory}/**/*.sh' explicitly: a leading-dot directory is "
            "not reliably matched by '**'."
        )


def test_the_scan_recognizes_every_construct() -> None:
    """Each pattern matches a line that really uses its construct.

    Without this a mistyped regex would make the scan below pass having
    matched nothing — green for the wrong reason (#5535).
    """
    blind: list[str] = []
    for pattern, _version, sample, _fix in _BASH4_CONSTRUCTS:
        if not re.search(pattern, sample):
            blind.append(f"{pattern} does not match its own sample: {sample}")
    assert blind == [], "\n".join(blind)


def test_the_scan_passes_the_portable_spellings() -> None:
    """No pattern flags a line a portable script really contains."""
    wrong: list[str] = []
    for line in PORTABLE_LINES:
        for pattern, _version, fix in _COMPILED:
            if pattern.search(line):
                wrong.append(f"{pattern.pattern} flags {line!r} ({fix})")
    assert wrong == [], "\n".join(wrong)


def test_the_scan_covers_every_tracked_shell_script() -> None:
    """The subject set holds the known scripts, so the scan is not vacuous."""
    scanned = {path.as_posix() for path in _tracked_scripts()}
    missing = [name for name in REQUIRED_SUBJECTS if name not in scanned]
    assert missing == [], (
        "These scripts are no longer in the scanned set, so the portability "
        "scan below no longer reads them. Update REQUIRED_SUBJECTS if one was "
        "deliberately removed or renamed:\n"
        + "\n".join(f"  {name}" for name in missing)
    )


def test_no_tracked_shell_script_uses_a_bash_4_construct() -> None:
    """Every tracked script runs on macOS's stock bash 3.2 (#5698).

    Every breach is reported, not just the first: a run that named one hit
    would send a contributor round the loop once per script.
    """
    breaches: list[str] = []
    for path in _tracked_scripts():
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            # A whole-line comment is prose, and the prose that explains why a
            # script avoids `mapfile` names `mapfile`.  An inline comment is
            # still scanned: stripping one would need to know which `#` is
            # inside a quoted string.
            if line.lstrip().startswith("#"):
                continue
            for pattern, version, fix in _COMPILED:
                if pattern.search(line):
                    breaches.append(
                        f"{path.as_posix()}:{number}: "
                        f"{pattern.pattern} needs bash {version}; {fix}"
                    )
    assert breaches == [], (
        "These scripts use a construct macOS's stock bash 3.2 does not have, "
        "so they fail on a macOS host while passing on the Linux runners "
        "(#5698):\n" + "\n".join(f"  {breach}" for breach in breaches)
    )
