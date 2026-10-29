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
"""A participant's act on a case names the case and never carries it (ADR-0165).

``Join``, ``Ignore`` and ``Leave`` of a case and the owner's ownership-transfer
proposal go to the CASE_MANAGER as the sealed body the sender's outbox would
deliver, through the inbox's own parse and routing edge
(``FastAPIIngressAdapter``: parse, staging and rehydration).  Each carries the case as a
typed reference, ``{"id", "type"}``; the CASE_MANAGER reads every detail from
its own case, ledgers the reference, and a replica applying the entry gains no
record from it.  A full case another sender still carries is not refused, but
nothing in it is read or stored, and a case the CASE_MANAGER does not hold is
refused, naming the activity and the case.
"""

import copy
from collections.abc import Callable
from typing import Any

import pytest

from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import run_use_case
from test.support.received import delivered_body
from vultron.adapters.driving.fastapi.inbox_handler import prepare_for_dispatch
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.wire.as2.factories import (
    propose_case_ownership_transfer_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-named-by-reference"
UNHELD_CASE_ID = "https://example.org/cases/case-the-manager-lacks"

#: The case reference every one of these acts carries (AKM-03-004).
_REFERENCE = {"id": CASE_ID, "type": "VulnerabilityCase"}

#: A participant the sender's copy lists and the CASE_MANAGER never added.
_PLANTED_ACTOR = "https://example.org/users/planted"
_PLANTED_PARTICIPANT = f"{CASE_ID}/participants/planted"


def _join(case: str) -> as_Activity:
    return rm_engage_case_activity(case, actor=BYSTANDER, to=[MANAGER])


def _ignore(case: str) -> as_Activity:
    return rm_defer_case_activity(case, actor=BYSTANDER, to=[MANAGER])


def _leave(case: str) -> as_Activity:
    return rm_close_case_activity(case, actor=BYSTANDER, to=[MANAGER])


def _propose(case: str) -> as_Activity:
    return propose_case_ownership_transfer_activity(
        case, target=BYSTANDER, actor=OWNER, to=[MANAGER]
    )


#: ``(build, semantic type it is ledgered as, path to the case it names)``.
_ACTS: dict[str, tuple[Callable[[str], as_Activity], str, tuple[str, ...]]] = {
    "Join": (_join, "engage_case", ("object",)),
    "Ignore": (_ignore, "defer_case", ("object",)),
    "Leave": (_leave, "close_case", ("object",)),
    "Offer(Offer)": (
        _propose,
        "propose_case_ownership_transfer",
        ("object", "object"),
    ),
}


def _slot(body: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = body
    for key in path:
        value = value[key]
    return value


def _without_context(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if k != "@context"}


def _carrying_a_full_case(
    net: LedgerNetwork, body: dict[str, Any], path: tuple[str, ...]
) -> dict[str, Any]:
    """*body* with the participant's own copy of the case in place of the
    reference, disagreeing with the CASE_MANAGER's: another name, and a
    participant the CASE_MANAGER never added, carried inline."""
    copy_ = net.case(MANAGER).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    copy_["name"] = "the participant's own copy"
    planted = CaseParticipant(
        id_=_PLANTED_PARTICIPANT,
        attributed_to=_PLANTED_ACTOR,
        context=CASE_ID,
    )
    # A row per register entry, as a well-formed copy carries (ADR-0122).
    planted.write_uninvited_rows([net.initial_embargo_id])
    copy_["caseParticipants"] = [
        *copy_.get("caseParticipants", []),
        planted.model_dump(mode="json", by_alias=True, exclude_none=True),
    ]
    carried = copy.deepcopy(body)
    holder = _slot(carried, path[:-1])
    holder[path[-1]] = copy_
    return carried


def _deliver(net: LedgerNetwork, body: dict[str, Any]) -> Any:
    """Route *body* to the CASE_MANAGER through the inbox's ingress edge.

    The body is parsed, staged and rehydrated as the inbox does it, so the
    case reference meets the store and rebuild a real delivery meets.
    """
    dl = net.stores[MANAGER]
    ingress = FastAPIIngressAdapter(dl)
    artifact = ingress.parse(copy.deepcopy(body))
    assert artifact is not None
    routed = ingress.rehydrate(artifact)
    event = prepare_for_dispatch(routed).model_copy(
        update={"receiving_actor_id": MANAGER}
    )
    return run_use_case(dl, event)


def _participant_ids(dl: Any) -> set[str]:
    return {o.id_ for o in dl.list_objects("CaseParticipant")}


def _entry_snapshot(
    net: LedgerNetwork, holder: str, semantic_type: str
) -> dict[str, Any]:
    (entry,) = [
        e
        for e in ledger_entries(net.stores[holder], CASE_ID)
        if e.semantic_type == semantic_type
    ]
    return entry.payload_snapshot


@pytest.mark.spec("AKM-03-004")
@pytest.mark.spec("CLP-07-011")
@pytest.mark.parametrize("act", sorted(_ACTS))
def test_the_ledgered_act_carries_only_the_case_reference(act):
    """The CASE_MANAGER commits the act, and its entry names the case.

    A replica applying the entry gains no record from it: the entry carries
    no case to take one from (ADR-0165).
    """
    build, semantic_type, path = _ACTS[act]
    net = LedgerNetwork(CASE_ID)
    body = delivered_body(build(CASE_ID))
    assert _without_context(_slot(body, path)) == _REFERENCE

    verdict = _deliver(net, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    snapshot = _entry_snapshot(net, MANAGER, semantic_type)
    assert _without_context(_slot(snapshot, path)) == _REFERENCE
    replica = net.stores[BYSTANDER]
    before = _participant_ids(replica)
    assert semantic_type in net.replay_ledger(BYSTANDER)
    assert _participant_ids(replica) == before


@pytest.mark.spec("AKM-03-005")
@pytest.mark.parametrize("act", sorted(_ACTS))
def test_a_carried_full_case_is_read_for_its_id_alone(act):
    """A full case another sender still carries is not refused.

    The CASE_MANAGER reads only its id: the case keeps its own name, the
    participant the copy lists is not stored, and a replica applying the
    entry takes nothing from the copy either (AKM-03-005).
    """
    build, semantic_type, path = _ACTS[act]
    net = LedgerNetwork(CASE_ID)
    name_before = net.case(MANAGER).name
    body = _carrying_a_full_case(net, delivered_body(build(CASE_ID)), path)

    verdict = _deliver(net, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert net.case(MANAGER).name == name_before
    assert net.stores[MANAGER].read(_PLANTED_PARTICIPANT) is None
    assert semantic_type in net.replay_ledger(BYSTANDER)
    assert net.stores[BYSTANDER].read(_PLANTED_PARTICIPANT) is None
    assert net.case(BYSTANDER).name == name_before


@pytest.mark.spec("AKM-03-006")
@pytest.mark.parametrize("act", sorted(_ACTS))
def test_an_act_naming_a_case_the_manager_lacks_is_refused(act):
    """The act carries no case to act on, so an unheld case is refused,
    and the reason names the activity and the case (AKM-03-006)."""
    build, _, _ = _ACTS[act]
    net = LedgerNetwork(CASE_ID)
    body = delivered_body(build(UNHELD_CASE_ID))
    entries_before = ledger_entries(net.stores[MANAGER], CASE_ID)

    verdict = _deliver(net, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert UNHELD_CASE_ID in (verdict.reason or "")
    assert body["id"] in (verdict.reason or "")
    assert net.stores[MANAGER].read(UNHELD_CASE_ID) is None
    assert ledger_entries(net.stores[MANAGER], CASE_ID) == entries_before
    assert net.stores[MANAGER].list_objects("DeadLetterRecord") == []
