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
"""``send_announce_log_entry`` has one caller in core: the verified send.

``send_verified_log_entry()`` recomputes an entry's hash before it queues
``Announce(CaseLedgerEntry)`` and holds back one that does not verify
(SYNC-03-009).  It covers every send path (fan-out, the ``Reject`` and
``Read`` replays, the embargo backfill and the join-time backfill) only while
no other code in ``vultron/core/`` reaches the port method directly.
"""

import ast

import pytest

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_HELPER = "vultron/core/behaviors/sync/nodes/verified_send.py"
_ALLOWED = {
    _HELPER,
    # The port definition itself.
    "vultron/core/ports/sync_activity.py",
}


def _referrers() -> set[str]:
    found: set[str] = set()
    for path, tree in _corpus.files_mentioning(
        "send_announce_log_entry", under=_CORE
    ):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "send_announce_log_entry"
            ) or (
                isinstance(node, ast.Constant)
                and node.value == "send_announce_log_entry"
            ):
                found.add(path.relative_to(_corpus.REPO_ROOT).as_posix())
    return found


@pytest.mark.spec("SYNC-03-009")
def test_only_the_verified_send_calls_send_announce_log_entry() -> None:
    assert _referrers() - _ALLOWED == set(), (
        "send_announce_log_entry() queues an entry unchecked; core sends one"
        " only through send_verified_log_entry(), which holds back an entry"
        " whose hash does not verify (SYNC-03-009)"
    )


def test_the_scan_finds_the_verified_send() -> None:
    """Guards against a vacuous pass if the call moves or is renamed."""
    assert _HELPER in _referrers()
