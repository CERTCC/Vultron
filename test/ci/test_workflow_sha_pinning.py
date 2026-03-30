"""CI security tests — verify GitHub Actions SHA pinning.

Implements CI-SEC-01-001 and CI-SEC-01-002 from specs/ci-security.md:
- Every `uses:` line in .github/workflows/*.yml MUST reference a full
  40-character commit SHA (not a mutable tag or branch name).
- Every SHA-pinned line MUST carry an inline human-readable version comment
  (e.g., ``# v4.1.0``).
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Matches a `uses:` value ending in @<40-hex-char SHA>
_SHA_RE = re.compile(r"@([0-9a-f]{40})\s*$", re.IGNORECASE)

# Matches an inline comment of the form  # <word>  (e.g., # v4.1.0)
_VERSION_COMMENT_RE = re.compile(r"#\s*\S+")


def _uses_lines(workflow_path: Path) -> list[tuple[int, str]]:
    """Return (line_number, stripped_line) pairs for every ``uses:`` line."""
    lines = []
    for lineno, raw in enumerate(
        workflow_path.read_text().splitlines(), start=1
    ):
        stripped = raw.strip()
        if stripped.startswith("uses:") or re.match(r"^-\s+uses:", stripped):
            lines.append((lineno, stripped))
    return lines


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


# ---------------------------------------------------------------------------
# Parametrize: one test case per (workflow_file, uses_line)
# ---------------------------------------------------------------------------


def _uses_params() -> list[tuple[Path, int, str]]:
    params = []
    for wf in _workflow_files():
        for lineno, line in _uses_lines(wf):
            params.append((wf, lineno, line))
    return params


@pytest.fixture(scope="module")
def workflow_files() -> list[Path]:
    files = _workflow_files()
    assert files, f"No workflow files found under {WORKFLOWS_DIR}"
    return files


def test_workflow_files_exist(workflow_files: list[Path]) -> None:
    """At least one workflow file must be present."""
    assert len(workflow_files) >= 1


@pytest.mark.parametrize("wf,lineno,line", _uses_params())
def test_uses_pinned_to_sha(wf: Path, lineno: int, line: str) -> None:
    """CI-SEC-01-001: every ``uses:`` value MUST be pinned to a 40-char SHA.

    Mutable references (version tags, branch names) are not allowed.
    """
    # Extract the action reference after 'uses:'
    uses_match = re.search(r"uses:\s*(\S+)", line)
    assert (
        uses_match
    ), f"{wf.name}:{lineno} — could not parse uses: line: {line!r}"
    ref = uses_match.group(1)
    sha_match = _SHA_RE.search(ref)
    assert sha_match, (
        f"{wf.name}:{lineno} — uses: reference is not SHA-pinned.\n"
        f"  Got: {ref!r}\n"
        f"  Expected: <action>@<40-char-sha>"
    )


@pytest.mark.parametrize("wf,lineno,line", _uses_params())
def test_uses_has_version_comment(wf: Path, lineno: int, line: str) -> None:
    """CI-SEC-01-002: every SHA-pinned ``uses:`` line MUST carry a version comment.

    The comment (e.g., ``# v4.1.0``) makes the pin human-readable for code
    review without decoding the SHA.
    """
    uses_match = re.search(r"uses:\s*(\S+)", line)
    if not uses_match:
        return  # malformed line; covered by test_uses_pinned_to_sha
    ref = uses_match.group(1)
    if not _SHA_RE.search(ref):
        return  # not SHA-pinned; covered by test_uses_pinned_to_sha

    # Everything after the action reference should include a version comment
    after_ref = line[uses_match.end() :]
    assert _VERSION_COMMENT_RE.search(after_ref), (
        f"{wf.name}:{lineno} — SHA-pinned uses: line is missing a version comment.\n"
        f"  Line: {line!r}\n"
        f"  Expected a comment like  # v4.1.0  after the SHA."
    )
