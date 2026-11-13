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

1. `mdlint.sh` lists `#**/plan/history/**` as a negated glob, so the --fix
   sweep cannot reach those files even if the markdownlint config ignores
   list is accidentally trimmed.
2. `.markdownlint-cli2.yaml` lists `**/plan/history/**` in its `ignores`,
   so every markdownlint invocation (with or without --fix) skips those
   files.

Both also exclude `.claude/worktrees/`, other agents' checkouts, whose own
`plan/history/` the root-anchored patterns used to miss (#6232).

The text tests check each exclusion's text, so each fails only when its own
exclusion is removed. A probe runs `markdownlint-cli2` itself and fails if any
route (a re-include, a nested config) makes a history entry reachable. The
sandbox tests run a copy of `mdlint.sh` in a scratch tree: with arguments it
fixes only those files, and bare it fixes no worktree or history entry.

Source: #2952, #6232.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MDLINT_SH = _REPO_ROOT / "mdlint.sh"
_MARKDOWNLINT_CONFIG = _REPO_ROOT / ".markdownlint-cli2.yaml"

# The exact patterns mdlint.sh uses to exclude every plan/history/ and every
# agent worktree. The leading **/ reaches a match at any depth, such as a
# plan/history/ inside a nested worktree or a path given absolutely (#6232).
_HISTORY_EXCLUSION_PATTERN = re.compile(r'"#\*\*/plan/history/\*\*"')
_WORKTREE_EXCLUSION_PATTERN = re.compile(r'"#\*\*/\.claude/worktrees/\*\*"')


def _mdlint_text() -> str:
    return _MDLINT_SH.read_text(encoding="utf-8")


def _config_ignores() -> list[str]:
    config = yaml.safe_load(_MARKDOWNLINT_CONFIG.read_text(encoding="utf-8"))
    ignores: list[str] = config.get("ignores", [])
    return ignores


@pytest.mark.spec("HM-01-005")
def test_mdlint_sh_excludes_plan_history() -> None:
    """mdlint.sh MUST exclude every plan/history/ from the --fix sweep.

    A line-initial issue reference (``#2670``) in a history entry looks like
    an ATX heading to markdownlint, and ``--fix`` rewrites the file.  The
    negated glob ``"#**/plan/history/**"`` prevents that.
    """
    assert _HISTORY_EXCLUSION_PATTERN.search(_mdlint_text()), (
        "mdlint.sh is missing the '#**/plan/history/**' exclusion. "
        "markdownlint-cli2 --fix can rewrite write-once history entries, "
        "forcing HM-01-005 violations. Add '\"#**/plan/history/**\"' to the "
        "markdownlint-cli2 invocation in mdlint.sh."
    )


@pytest.mark.spec("HM-01-005")
def test_mdlint_sh_excludes_agent_worktrees() -> None:
    """mdlint.sh MUST exclude agent worktrees, other sessions' checkouts.

    Each worktree holds its own plan/history/ entries (#6232).
    """
    assert _WORKTREE_EXCLUSION_PATTERN.search(_mdlint_text()), (
        "mdlint.sh is missing the '#**/.claude/worktrees/**' exclusion, so a "
        "repo-wide --fix rewrites other agents' worktrees (#6232)."
    )


@pytest.mark.spec("HM-01-005")
def test_markdownlint_config_ignores_plan_history() -> None:
    """The root .markdownlint-cli2.yaml MUST ignore every plan/history/.

    Belt-and-suspenders: even if mdlint.sh is edited to remove the negated
    glob, markdownlint will not reach write-once history files because they
    are listed in the config-level ignores.
    """
    assert "**/plan/history/**" in _config_ignores(), (
        ".markdownlint-cli2.yaml is missing '**/plan/history/**' in its "
        "ignores list. Add it so that every markdownlint run (with or without "
        "--fix) skips write-once history entries (HM-01-005)."
    )


@pytest.mark.spec("HM-01-005")
def test_markdownlint_config_ignores_agent_worktrees() -> None:
    """The root config MUST ignore agent worktrees for every run (#6232)."""
    assert "**/.claude/worktrees/**" in _config_ignores(), (
        ".markdownlint-cli2.yaml is missing '**/.claude/worktrees/**' in its "
        "ignores list; a repo-wide run lints other agents' worktrees."
    )


_MARKDOWNLINT = shutil.which("markdownlint-cli2")

# The summary line reads "Linting: 0 files" before markdownlint-cli2 0.21 and
# "Linting: 0 file(s)" from 0.21 on; both mean nothing was linted.
_LINTED_NONE = re.compile(r"^Linting: 0 file(?:s|\(s\))$", re.MULTILINE)
# A run that starts prints its banner (unless `noBanner` is set) and its
# summary line; a tool that never started prints neither.
_BANNER = "markdownlint-cli2 v"
_SUMMARY = "Linting:"


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
        if _BANNER not in output and _SUMMARY not in output:
            # The tool never started (e.g. its node runtime cannot load), so it
            # gave no verdict on the exclusion; a failure here would blame the
            # repo for the host. A run without its banner (`noBanner`) still
            # prints its summary, so it reaches the assertion.
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


def _fake_markdownlint(tmp_path: Path, stdout: str) -> str:
    """Write a stand-in markdownlint-cli2 that prints *stdout* and exits 1."""
    fake = tmp_path / "markdownlint-cli2"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' '{stdout}'\nexit 1\n")
    fake.chmod(0o755)
    return str(fake)


def test_probe_skips_when_the_tool_does_not_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A tool that prints neither banner nor summary gave no verdict: skip."""
    monkeypatch.setattr(
        sys.modules[__name__],
        "_MARKDOWNLINT",
        _fake_markdownlint(tmp_path, ""),
    )
    with pytest.raises(pytest.skip.Exception, match="did not run"):
        test_markdownlint_reaches_no_history_entry()


def test_probe_judges_a_run_without_its_banner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A run with `noBanner` set still reports its summary, so it is judged."""
    fake = _fake_markdownlint(tmp_path, "Linting: 3 file(s)")
    monkeypatch.setattr(sys.modules[__name__], "_MARKDOWNLINT", fake)
    with pytest.raises(AssertionError, match="reached plan/history/"):
        test_markdownlint_reaches_no_history_entry()


# A line ``--fix`` rewrites: a body line opening with an issue reference reads
# as an ATX heading missing its space (MD018), the #2952 damage itself.
_FIXABLE = "# Title\n\n#5589 makes a change.\n"


def _mdlint_sandbox(tmp_path: Path) -> dict[str, Path]:
    """Copy mdlint.sh and the root config into *tmp_path* beside fixable files.

    The run happens in a scratch tree, never the checkout, so ``--fix`` can
    reach nothing real. Returns the fixable files keyed by role.
    """
    shutil.copy(_MDLINT_SH, tmp_path / "mdlint.sh")
    shutil.copy(_MARKDOWNLINT_CONFIG, tmp_path / ".markdownlint-cli2.yaml")
    worktree = tmp_path / ".claude" / "worktrees" / "w"
    files = {
        "target": tmp_path / "notes" / "target.md",
        "bystander": tmp_path / "notes" / "bystander.md",
        "history": tmp_path / "plan" / "history" / "2611" / "entry.md",
        "nested_history": tmp_path / "sub" / "plan" / "history" / "entry.md",
        "worktree": worktree / "notes" / "x.md",
        "worktree_history": worktree
        / "plan"
        / "history"
        / "2611"
        / "entry.md",
    }
    for path in files.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_FIXABLE, encoding="utf-8")
    return files


# CI's markdownlint job sets this so a sandbox test that cannot run fails
# instead of skipping: an all-skipped run reports green while checking nothing.
_REQUIRE_ENV = "VULTRON_REQUIRE_MARKDOWNLINT"


def _unavailable(reason: str) -> None:
    """Skip for *reason*, or fail when the environment requires the tool."""
    if os.environ.get(_REQUIRE_ENV):
        pytest.fail(f"{_REQUIRE_ENV} is set but {reason}")
    pytest.skip(reason)


def _run_mdlint(tmp_path: Path, *args: str) -> str:
    """Run the sandboxed mdlint.sh and return its output.

    Skips (or fails, under the CI job) if markdownlint-cli2 never started.
    """
    if _MARKDOWNLINT is None:
        _unavailable("markdownlint-cli2 not on PATH")
    result = subprocess.run(
        ["sh", "mdlint.sh", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    output = result.stdout + result.stderr
    if _BANNER not in output and _SUMMARY not in output:
        _unavailable(f"markdownlint-cli2 did not run:\n{output}")
    return output


def _changed(files: dict[str, Path]) -> set[str]:
    return {
        role
        for role, path in files.items()
        if path.read_text(encoding="utf-8") != _FIXABLE
    }


@pytest.mark.spec("HM-01-005")
def test_mdlint_sh_with_arguments_fixes_only_those_files(
    tmp_path: Path,
) -> None:
    """``./mdlint.sh <file>`` lints and fixes that file and no other (#6232)."""
    files = _mdlint_sandbox(tmp_path)
    _run_mdlint(tmp_path, "notes/target.md")
    assert _changed(files) == {"target"}


@pytest.mark.spec("HM-01-005")
def test_bare_mdlint_sh_spares_worktrees_and_every_history_dir(
    tmp_path: Path,
) -> None:
    """A bare ``./mdlint.sh`` fixes no agent worktree and no history entry.

    The two notes files prove the run reached ordinary Markdown, so an
    unchanged history entry is the exclusion at work, not an empty run (#6232).
    """
    files = _mdlint_sandbox(tmp_path)
    _run_mdlint(tmp_path)
    assert _changed(files) == {"target", "bystander"}


@pytest.mark.spec("HM-01-005")
@pytest.mark.parametrize(
    "absolute", [False, True], ids=["relative", "absolute"]
)
def test_mdlint_sh_given_an_excluded_path_fixes_nothing(
    tmp_path: Path, absolute: bool
) -> None:
    """Naming a worktree or history file, however written, changes nothing.

    The exclusions match at any depth, so an absolute path into a worktree is
    refused like a relative one (#6232).
    """
    files = _mdlint_sandbox(tmp_path)
    excluded = ("worktree", "worktree_history", "history", "nested_history")
    args = [
        str(files[role] if absolute else files[role].relative_to(tmp_path))
        for role in excluded
    ]
    output = _run_mdlint(tmp_path, *args)
    # Unchanged files alone could hide a run that linted them without a fix.
    assert _LINTED_NONE.search(output), output
    assert _changed(files) == set()


def test_sandbox_skips_without_the_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Off CI's markdownlint job, a missing tool skips the sandbox tests."""
    monkeypatch.delenv(_REQUIRE_ENV, raising=False)
    monkeypatch.setattr(sys.modules[__name__], "_MARKDOWNLINT", None)
    with pytest.raises(pytest.skip.Exception, match="not on PATH"):
        _run_mdlint(tmp_path)


def test_sandbox_fails_without_the_tool_when_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Under CI's markdownlint job, a missing tool fails instead of skipping."""
    monkeypatch.setenv(_REQUIRE_ENV, "1")
    monkeypatch.setattr(sys.modules[__name__], "_MARKDOWNLINT", None)
    with pytest.raises(pytest.fail.Exception, match="not on PATH"):
        _run_mdlint(tmp_path)


def test_sandbox_fails_when_required_and_the_tool_does_not_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A tool that prints nothing fails the run when the job requires it."""
    monkeypatch.setenv(_REQUIRE_ENV, "1")
    fake = _fake_markdownlint(tmp_path, "")
    monkeypatch.setattr(sys.modules[__name__], "_MARKDOWNLINT", fake)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    shutil.copy(_MDLINT_SH, tmp_path / "mdlint.sh")
    with pytest.raises(pytest.fail.Exception, match="did not run"):
        _run_mdlint(tmp_path)
