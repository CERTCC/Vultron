#!/usr/bin/env python

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

"""Ratchet: core code producing the AS2 wire shape itself (ARCH-20-001).

ADR-0099 detail 2 puts ``alias_generator=to_camel`` on ``CoreObject``, so
``model_dump(by_alias=True)`` on a core object *is* the wire shape.  That is
the mechanism behind ``WireRenderPort``, not a licence: core logic still hands
delivery to the port.  Every ``by_alias=True`` call under ``vultron/core/`` is
counted per file and compared to an exact baseline, so a new call site fails
and a removed one must be ticked off (the set may only shrink).

The baseline counts calls, not uses: a ``by_alias=True`` dump of an object that
is already wire-shaped, or of a stored record whose persisted form happens to
be camelCase, is counted alongside a genuine core-to-wire rendering.  Audit a
site before removing it; do not add one without saying why in a comment.
"""

import ast
from collections import Counter

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"

# The "seven remaining call sites" the ARCH-20-001 comments at each site name.
_BASELINE: dict[str, int] = {
    "vultron/core/behaviors/case/nodes/accept_invite.py": 1,
    "vultron/core/behaviors/case/nodes/proposal_retry_marker.py": 1,
    "vultron/core/behaviors/inbox/nodes/dead_letter.py": 1,
    "vultron/core/behaviors/status/nodes/case_status.py": 1,
    "vultron/core/use_cases/_snapshot_helpers.py": 2,
    "vultron/core/use_cases/received/case_proposal.py": 1,
}


def _by_alias_calls() -> Counter[str]:
    counts: Counter[str] = Counter()
    for path, tree in _corpus.files_mentioning("by_alias", under=_CORE):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (
                    kw.arg == "by_alias"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
                    counts[rel] += 1
    return counts


def test_core_by_alias_dumps_match_baseline() -> None:
    actual = dict(_by_alias_calls())
    added = {f: n for f, n in actual.items() if n > _BASELINE.get(f, 0)}
    removed = {f: n for f, n in _BASELINE.items() if actual.get(f, 0) < n}
    assert actual == _BASELINE, (
        "by_alias=True call sites under vultron/core/ changed (ARCH-20-001).\n"
        f"  new or grown (route through WireRenderPort): {added}\n"
        f"  shrunk (lower the baseline): {removed}\n"
        f"  actual: {actual}"
    )
