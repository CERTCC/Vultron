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
"""An ownership transfer moves CASE_OWNER on every replica (#4439).

Accepting a transfer changes three objects at the CASE_MANAGER: the old
owner's participant record loses ``CASE_OWNER``, the new owner's gains it, and
the case's ``attributed_to`` names the new owner.  Each change follows the
``Accept`` entry as its own CASE_MANAGER-authored entry carrying the changed
object in full (CLP-07-013, ADR-0124), and a replica copies what each entry
carries (CM-23-016), so its roles and owner equal the CASE_MANAGER's.
"""

import json
from typing import Any, cast

import pytest

from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_semantic_types import (
    UPDATE_CASE_OWNER_SEMANTIC_TYPE,
    UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    propose_case_ownership_transfer_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

_ACCEPT = MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER.value


def _send(net: LedgerNetwork, activity: Any) -> None:
    """Deliver *activity* to the CASE_MANAGER, as its sender's outbox would."""
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(activity)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _transferred(case_id: str) -> LedgerNetwork:
    """OWNER proposes the case to BYSTANDER; the CASE_MANAGER makes the
    Offer, and BYSTANDER accepts it (ADR-0148)."""
    net = LedgerNetwork(case_id)
    case = as_VulnerabilityCase(id_=case_id, name="Ownership replay")
    proposal = propose_case_ownership_transfer_activity(
        case,
        target=as_Service(id_=BYSTANDER, name="Transferee"),
        actor=OWNER,
        to=[MANAGER],
        id_=f"{case_id}/proposals/1",
    )
    _send(net, proposal)
    offer = net.stores[MANAGER].read(
        ownership_offer_id(MANAGER, case_id, proposal.id_)
    )
    assert offer is not None
    _send(
        net,
        accept_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )
    return net


def _entries(net: LedgerNetwork, actor_id: str) -> list[CaseLedgerEntry]:
    return sorted(
        (
            cast(CaseLedgerEntry, e)
            for e in net.stores[actor_id].list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == net.case_id
        ),
        key=lambda e: e.log_index,
    )


def _participant(
    net: LedgerNetwork, store_of: str, member: str
) -> CaseParticipant:
    participant = net.stores[store_of].read(
        net.case(store_of).actor_participant_index[member]
    )
    assert isinstance(participant, CaseParticipant)
    return participant


def _owners(net: LedgerNetwork, store_of: str) -> dict[str, bool]:
    """Each member, and whether *store_of* records it holding CASE_OWNER."""
    return {
        member: _participant(net, store_of, member).has_role(
            CVDRole.CASE_OWNER
        )
        for member in net.case(MANAGER).actor_participant_index
    }


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-21-007")
def test_each_changed_object_follows_the_accept_as_its_own_entry():
    """Old owner's record, new owner's record, then the case (AC-1)."""
    net = _transferred("https://example.org/cases/ot-replay-entries")

    entries = _entries(net, MANAGER)
    semantic_types = [e.semantic_type for e in entries]
    accept_at = semantic_types.index(_ACCEPT)
    consequences = entries[accept_at + 1 :]

    assert [e.semantic_type for e in consequences] == [
        UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE,
        UPDATE_CASE_PARTICIPANT_SEMANTIC_TYPE,
        UPDATE_CASE_OWNER_SEMANTIC_TYPE,
    ]
    for entry in consequences:
        assert entry.payload_snapshot["type"] == "Update"
        assert entry.payload_snapshot["actor"] == MANAGER
    old, new, case = (e.payload_snapshot["object"] for e in consequences)
    old_record = _participant(net, MANAGER, OWNER)
    new_record = _participant(net, MANAGER, BYSTANDER)
    assert old["id"] == old_record.id_
    assert CVDRole.CASE_OWNER.value not in old["caseRoles"]
    assert new["id"] == new_record.id_
    assert CVDRole.CASE_OWNER.value in new["caseRoles"]
    assert case["id"] == net.case_id
    assert case["attributedTo"] == BYSTANDER


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("CM-21-001")
@pytest.mark.parametrize("replica", [OWNER, BYSTANDER])
def test_a_replica_holds_the_managers_owner_after_a_transfer(replica: str):
    """Roles and ``attributed_to`` equal the CASE_MANAGER's (AC-2)."""
    net = _transferred(f"https://example.org/cases/ot-replay-{replica[-1]}")
    assert _owners(net, replica) != _owners(net, MANAGER), (
        "the replica must not hold the new owner before the replay"
    )

    delivered = net.replay_ledger(replica)

    assert UPDATE_CASE_OWNER_SEMANTIC_TYPE in delivered
    assert _owners(net, replica) == _owners(net, MANAGER)
    assert _owners(net, replica)[BYSTANDER] is True
    assert net.case(replica).attributed_to == BYSTANDER
    assert net.case(replica).attributed_to == net.case(MANAGER).attributed_to


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("replica", [OWNER, BYSTANDER])
def test_a_replica_copies_each_participant_record_it_is_sent(replica: str):
    """Every id and time in the copy is the CASE_MANAGER's (AC-3).

    A replica that minted an id, read a clock, or rebuilt the record by role
    logic of its own would hold a record different from the CASE_MANAGER's.
    """
    net = _transferred(f"https://example.org/cases/ot-copy-{replica[-1]}")

    net.replay_ledger(replica)

    for member in (OWNER, BYSTANDER):
        assert _participant(net, replica, member).model_dump() == (
            _participant(net, MANAGER, member).model_dump()
        ), member
