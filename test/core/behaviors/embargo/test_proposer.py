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

"""``embargo_proposer_id``: who proposed an embargo, from the ledger (CM-24)."""

from typing import Any

import pytest

from vultron.core.behaviors.embargo.proposer import embargo_proposer_id
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry

CASE_ID = "https://example.org/cases/proposer"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"
MANAGER = "https://example.org/actors/case-manager"
VENDOR = "https://example.org/actors/vendor"


def _entry(
    index: int, semantic_type: str, snapshot: dict[str, Any]
) -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=index,
            object_id=f"urn:entry:{index}",
            semantic_type=semantic_type,
            payload_snapshot=snapshot,
            prev_log_hash="0" * 64,
        )
    )


def _invite(actor: str, attributed_to: str | None = None) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "type": "Invite",
        "actor": actor,
        "object": {"type": "EmbargoEvent", "id": EMBARGO_ID},
    }
    if attributed_to is not None:
        snapshot["attributedTo"] = attributed_to
    return snapshot


@pytest.mark.spec("EMB-17-003")
def test_a_proposal_names_its_sender():
    entries = [
        _entry(0, "invite_to_embargo_on_case", _invite(VENDOR)),
        _entry(1, "invite_to_embargo_on_case", _invite(MANAGER, VENDOR)),
    ]
    assert embargo_proposer_id(entries, EMBARGO_ID) == VENDOR


@pytest.mark.spec("EMB-17-003")
def test_a_relay_names_the_proposer_in_attributed_to():
    """A creation-time revision has only its relay (EP-04-011)."""
    entries = [
        _entry(0, "invite_to_embargo_on_case", _invite(MANAGER, VENDOR))
    ]
    assert embargo_proposer_id(entries, EMBARGO_ID) == VENDOR


@pytest.mark.spec("EMB-17-003")
def test_an_embargo_no_invite_carries_has_no_proposer():
    """The protocol default is made without a proposal: the caller names
    the CASE_MANAGER (ADR-0152)."""
    entries = [
        _entry(0, "accept_invite_to_embargo_on_case", _invite(VENDOR)),
        _entry(
            1,
            "invite_to_embargo_on_case",
            {**_invite(VENDOR), "object": "urn:other-embargo"},
        ),
    ]
    assert embargo_proposer_id(entries, EMBARGO_ID) is None
