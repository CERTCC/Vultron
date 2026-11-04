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

Both checks run as ratchets: either one failing signals that the
exclusion was removed and must be restored.

Source: #2952.
"""

from __future__ import annotations

import re
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
