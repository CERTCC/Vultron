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
"""The sender-sequence hold sweep is one act (ADR-0176)."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from test.support.act_clock import ACT_AT, CountingClock, tree_lock_held
from vultron.adapters.driving.fastapi import sender_sequence_holds as holds


@pytest.mark.spec("CS-13-002")
def test_the_sweep_judges_every_hold_at_one_instant_read_inside_the_lock(
    monkeypatch,
):
    seen: list[tuple[datetime, bool]] = []

    def _end(dl: object, now: datetime, wait: timedelta) -> int:
        seen.append((now, tree_lock_held()))
        return 0

    monkeypatch.setattr(holds, "end_expired_sender_sequence_holds", _end)
    monkeypatch.setattr(holds, "queue_due_held_activities", lambda dl: None)
    clock = CountingClock()

    assert holds.end_expired_holds(MagicMock(), clock) == 0

    assert clock.reads == 1
    assert clock.locked_at_read == [True]
    assert seen == [(ACT_AT, True)]
