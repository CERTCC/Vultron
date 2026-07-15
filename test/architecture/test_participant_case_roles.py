"""Architecture tests: case_roles access discipline in core (PRM-05-004, PRM-01-003)."""

import re
from pathlib import Path

# vultron/core/ root
_CORE_ROOT = Path(__file__).parents[2] / "vultron" / "core"
# The modules that are permitted to access case_roles directly
_ALLOWED_MODULES = frozenset(
    [
        _CORE_ROOT / "models" / "participant.py",
        _CORE_ROOT / "models" / "case_participant.py",
    ]
)

# Patterns that indicate direct case_roles mutation on an instance:
#   .case_roles = ...   (attribute assignment)
#   .case_roles.append  (in-place list mutation)
_MUTATION_RE = re.compile(r"\.case_roles\s*=|\.case_roles\s*\.\s*append")

# Pattern that indicates a direct getattr read of case_roles:
#   getattr(..., "case_roles", ...)  or  getattr(..., 'case_roles', ...)
_GETATTR_READ_RE = re.compile(r"""getattr\s*\([^)]+,\s*['"]case_roles['"]""")


def test_no_direct_case_roles_mutation_in_core():
    """No core file outside participant.py may mutate case_roles directly (PRM-05-004).

    Constructor keyword-argument form (`case_roles=...`) is permitted and is
    NOT flagged by this test because it lacks the leading dot.
    """
    violations: list[str] = []
    for py_file in sorted(_CORE_ROOT.rglob("*.py")):
        if py_file in _ALLOWED_MODULES:
            continue
        text = py_file.read_text()
        for lineno, line in enumerate(text.splitlines(), 1):
            if _MUTATION_RE.search(line):
                violations.append(
                    f"{py_file.relative_to(_CORE_ROOT)}:{lineno}: {line.strip()}"
                )
    assert not violations, (
        "Direct case_roles mutation found in vultron/core/ outside participant.py:\n"
        + "\n".join(violations)
    )


def test_no_getattr_case_roles_read_in_core():
    """No core file outside participant.py may read case_roles via getattr() (PRM-01-003).

    Use ``participant.roles`` (property) or ``participant.has_role(role)`` instead.
    Constructor keyword-argument form (``case_roles=...``) is permitted and is
    NOT flagged because it lacks the leading ``getattr(`` wrapper.
    """
    violations: list[str] = []
    for py_file in sorted(_CORE_ROOT.rglob("*.py")):
        if py_file in _ALLOWED_MODULES:
            continue
        text = py_file.read_text()
        for lineno, line in enumerate(text.splitlines(), 1):
            if _GETATTR_READ_RE.search(line):
                violations.append(
                    f"{py_file.relative_to(_CORE_ROOT)}:{lineno}: {line.strip()}"
                )
    assert not violations, (
        "getattr() read of case_roles found in vultron/core/ outside participant.py "
        "(use .roles or .has_role() instead — PRM-01-003):\n"
        + "\n".join(violations)
    )
