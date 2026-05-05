"""Architecture test: no direct case_roles mutation outside participant.py (PRM-05-004)."""

import re
from pathlib import Path

# vultron/core/ root
_CORE_ROOT = Path(__file__).parents[2] / "vultron" / "core"
# The one module that is permitted to mutate case_roles directly
_PARTICIPANT_MODULE = _CORE_ROOT / "models" / "participant.py"

# Patterns that indicate direct case_roles mutation on an instance:
#   .case_roles = ...   (attribute assignment)
#   .case_roles.append  (in-place list mutation)
_MUTATION_RE = re.compile(r"\.case_roles\s*=|\.case_roles\s*\.\s*append")


def test_no_direct_case_roles_mutation_in_core():
    """No core file outside participant.py may mutate case_roles directly (PRM-05-004).

    Constructor keyword-argument form (`case_roles=...`) is permitted and is
    NOT flagged by this test because it lacks the leading dot.
    """
    violations: list[str] = []
    for py_file in sorted(_CORE_ROOT.rglob("*.py")):
        if py_file == _PARTICIPANT_MODULE:
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
