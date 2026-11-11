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
"""Regression guard: mdlint.sh --fix MUST NOT reach plan/history/.

`plan/history/` entries are write-once records (HM-01-005). `mdlint.sh`
runs `markdownlint-cli2 --fix`, which rewrote history entries in PR #2931
(commit `7de4a6c0`), forcing a repair commit that itself violated HM-01-005.

Two independent exclusions prevent recurrence:

1. `mdlint.sh` lists `#plan/history/**` as a negated glob, so the --fix
   sweep cannot reach those files even if the markdownlint config ignores
   list is accidentally trimmed.
2. `.markdownlint-cli2.yaml` lists `plan/history/**` in its `ignores`,
   so every markdownlint invocation (with or without --fix) skips those
   files.

The first two tests check each exclusion's text, so each fails only when its
own exclusion is removed. A third runs `markdownlint-cli2` itself and fails if
any route (a re-include, a nested config) makes a history entry reachable.

Source: #2952.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MDLINT_SH = _REPO_ROOT / "mdlint.sh"
_MARKDOWNLINT_CONFIG = _REPO_ROOT / ".markdownlint-cli2.yaml"

# The exact pattern used in mdlint.sh to exclude plan/history/**
_HISTORY_EXCLUSION_PATTERN = re.compile(r'"#plan/history/\*\*"')


@pytest.mark.spec("HM-01-005")
def test_mdlint_sh_excludes_plan_history() -> None:
    """mdlint.sh MUST exclude plan/history/** from the --fix sweep.

    A line-initial issue reference (``#2670``) in a history entry looks like
    an ATX heading to markdownlint, and ``--fix`` rewrites the file.  The
    negated glob ``"#plan/history/**"`` prevents that.
    """
    text = _MDLINT_SH.read_text(encoding="utf-8")
    assert _HISTORY_EXCLUSION_PATTERN.search(text), (
        "mdlint.sh is missing the '#plan/history/**' exclusion. "
        "markdownlint-cli2 --fix can rewrite write-once history entries, "
        "forcing HM-01-005 violations. Add '\"#plan/history/**\"' to the "
        "markdownlint-cli2 invocation in mdlint.sh."
    )


@pytest.mark.spec("HM-01-005")
def test_markdownlint_config_ignores_plan_history() -> None:
    """The root .markdownlint-cli2.yaml MUST ignore plan/history/**.

    Belt-and-suspenders: even if mdlint.sh is edited to remove the negated
    glob, markdownlint will not reach write-once history files because they
    are listed in the config-level ignores.
    """
    config = yaml.safe_load(_MARKDOWNLINT_CONFIG.read_text(encoding="utf-8"))
    ignores: list[str] = config.get("ignores", [])
    assert "plan/history/**" in ignores, (
        ".markdownlint-cli2.yaml is missing 'plan/history/**' in its ignores "
        "list. Add it so that every markdownlint run (with or without --fix) "
        "skips write-once history entries (HM-01-005)."
    )


_MARKDOWNLINT = shutil.which("markdownlint-cli2")

# The summary line reads "Linting: 0 files" before markdownlint-cli2 0.21 and
# "Linting: 0 file(s)" from 0.21 on; both mean nothing was linted.
_LINTED_NONE = re.compile(r"^Linting: 0 file(?:s|\(s\))$", re.MULTILINE)
# Every run that starts prints this banner before it finds any file.
_BANNER = "markdownlint-cli2 v"


@pytest.mark.spec("HM-01-005")
@pytest.mark.skipif(
    _MARKDOWNLINT is None, reason="markdownlint-cli2 not on PATH"
)
def test_markdownlint_reaches_no_history_entry() -> None:
    """markdownlint-cli2 MUST lint zero files under plan/history/.

    The text checks above pass even if a later ``!plan/history/**``
    re-include or a nested config brings the entries back into scope; this
    asks the tool itself, without ``--fix``, so it cannot modify anything.
    """
    entries = sorted((_REPO_ROOT / "plan" / "history").rglob("*.md"))
    assert entries, (
        "no plan/history entry to probe; the check would be vacuous"
    )
    probe = entries[0].relative_to(_REPO_ROOT).as_posix()
    assert _MARKDOWNLINT is not None
    for target in (probe, "plan/history/**/*.md"):
        result = subprocess.run(
            [_MARKDOWNLINT, "--config", ".markdownlint-cli2.yaml", target],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        output = result.stdout + result.stderr
        if _BANNER not in output:
            # The tool never started (e.g. its node runtime cannot load), so it
            # gave no verdict on the exclusion; a failure here would blame the
            # repo for the host.
            pytest.skip(f"markdownlint-cli2 did not run:\n{output}")
        assert _LINTED_NONE.search(output), (
            f"markdownlint-cli2 reached plan/history/ for {target!r}; "
            f"history entries must stay out of every run (HM-01-005).\n{output}"
        )


@pytest.mark.parametrize(
    ("summary", "linted_none"),
    [
        ("Linting: 0 files", True),
        ("Linting: 0 file(s)", True),
        ("Linting: 1 file(s)", False),
        ("Linting: 10 files", False),
    ],
)
def test_linted_none_reads_every_summary_form(
    summary: str, linted_none: bool
) -> None:
    """The probe reads both markdownlint-cli2 summary forms, and only zero."""
    output = f"markdownlint-cli2 v0.21.0\n{summary}\nSummary: 0 error(s)\n"
    assert bool(_LINTED_NONE.search(output)) is linted_none


def test_probe_skips_when_the_tool_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tool that exits without its banner gave no verdict, so the probe skips."""
    false_bin = shutil.which("false")
    assert false_bin is not None
    monkeypatch.setattr(
        "test.metadata.test_mdlint_history_exclusion._MARKDOWNLINT", false_bin
    )
    with pytest.raises(pytest.skip.Exception, match="did not run"):
        test_markdownlint_reaches_no_history_entry()
