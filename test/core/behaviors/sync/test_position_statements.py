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

"""Participant position statements: a participant says how far it has got.

Every test here is a strict ``xfail`` for unbuilt behaviour (ADR-0155). Each
implementation issue removes the ``xfail`` from the tests it makes pass and
replaces each name probe with a full behaviour test.
"""

import pytest

from vultron.core.models.events.base import MessageSemantics, VultronEvent


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-17: no Read(CaseLedgerEntry) message yet. Tracked by #5098.",
)
@pytest.mark.spec("SYNC-17-001")
@pytest.mark.spec("SYNC-17-002")
@pytest.mark.spec("SYNC-17-003")
@pytest.mark.spec("SYNC-17-004")
@pytest.mark.spec("SYNC-17-005")
@pytest.mark.spec("SYNC-17-006")
def test_read_case_ledger_entry_is_a_message_semantic() -> None:
    """A participant's ``Read(CaseLedgerEntry)`` has its own semantic type."""
    assert "READ_CASE_LEDGER_ENTRY" in MessageSemantics.__members__


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-03-004: received events carry no ledgerTail yet. Tracked by #5099.",
)
@pytest.mark.spec("SYNC-03-004")
@pytest.mark.spec("SYNC-17-008")
def test_received_event_carries_the_senders_stated_position() -> None:
    """A received event promotes the sender's stated ``ledgerTail``.

    The probe names ``stated_position``, not ``ledger_tail``: the extractor
    already parses a ``ledger_tail`` field from ``content`` for the full-case
    Invite events, so reusing that name would refuse every other activity.
    """
    assert "stated_position" in VultronEvent.model_fields
