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

"""Builders for the actor-suggestion and role-offer semantics.

The suggestion story runs on a ``LedgerNetwork``: a participant recommends
an actor to the CASE_MANAGER, which offers it on to the Case Owner, whose
answer the CASE_MANAGER then acts on and reports to the recommender.  The
role-offer story (CM-33) and the refusals use the plain stores of the
existing handler tests, whose guards they reuse.
"""

from typing import Any, cast

from test.support.ledger_rebuild import run_use_case
from test.support.objects import authored_at
from test.support.received import received_event, settle_as_the_inbox
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    accept_case_participant_offer_activity,
    accept_case_participant_role_activity,
    recommend_actor_activity,
    reject_case_participant_offer_activity,
    reject_case_participant_role_activity,
)
from vultron.wire.as2.parser import parse_activity

from .._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from ..actor import (
    test_offer_case_participant as offer_tests,
    test_recommendation_answer as answer_tests,
    test_role_offer_routing as role_tests,
)
from ..test_participant_removal_planned import (
    MANAGER as REMOVAL_MANAGER,
    OTHER as REMOVAL_OTHER,
    VENDOR as REMOVAL_VENDOR,
    _RemovalCase,
    _seed,
)
from . import Scenario, applied, refused
from ._net import deliver

_BASE = "https://example.org/cases/rerun-sweep"
#: The actor a participant recommends for the case.
_RECOMMENDED = "https://example.org/users/rerun-sweep-recommended"
#: The participant that recommends it; the network keeps its store.
_RECOMMENDER = BYSTANDER


def _settle(dl: SqliteDataLayer, event: Any) -> None:
    """Run *event* to its outcome, as an earlier delivery in the story."""
    verdict = run_use_case(dl, event)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    settle_as_the_inbox(dl, event, verdict)


def _receipt_recorded(dl: SqliteDataLayer, activity_id: str) -> str | None:
    """A receipt tree's whole effect: the message is recorded, nothing else.

    The tree commits nothing and sends nothing at this receiver, so its
    first run is checked for having recorded the receipt and for leaving
    the ledger and the outbox empty; the re-run comparison then shows that
    it still leaves them empty.
    """
    if dl.read(ReceivedActivityRecord.build_id(activity_id)) is None:
        return "the receipt was not recorded"
    if dl.list_objects("CaseLedgerEntry") or dl.outbox_list():
        return "a receipt-only tree committed or queued something"
    return None


# --- the suggestion story (CM-16) ------------------------------------------


def _recommendation(net: LedgerNetwork) -> Any:
    return recommend_actor_activity(
        _RECOMMENDED,
        target=net.case_id,
        actor=_RECOMMENDER,
        to=[MANAGER],
        content=f"{_RECOMMENDER} vouches for them",
        at=authored_at(),
    )


def _network(name: str) -> LedgerNetwork:
    """A network whose case has the summary a stub Invite carries."""
    net = LedgerNetwork(f"{_BASE}/{name}", em_state=EM.NONE)
    dl = net.stores[MANAGER]
    case = cast(VulnerabilityCase, dl.read(net.case_id))
    dl.save(
        case.model_copy(
            update={"stub_summary": "A case to join, details on acceptance"}
        )
    )
    return net


def _sent_to(net: LedgerNetwork, sender: str, to: str, type_: str) -> Scenario:
    """*sender*'s one queued *type_* body, as *to*'s inbox receives it."""
    (activity,) = net.queued(sender, to=to, type_=type_)
    body = read_sealed_body_dict(net.stores[sender], activity.id_)
    assert body is not None
    return Scenario(
        dl=net.stores[to],
        event=received_event(
            parse_activity(body), as_sent=True, receiving_actor_id=to
        ),
    )


def _offered(name: str) -> tuple[LedgerNetwork, Any]:
    """The CASE_MANAGER has offered the recommended actor to the owner."""
    net = _network(name)
    recommendation = deliver(net, _recommendation(net))
    _settle(recommendation.dl, recommendation.event)
    offer = _sent_to(net, MANAGER, OWNER, "Offer")
    return net, offer.event.activity


@applied(MessageSemantics.OFFER_ACTOR_TO_CASE)
def offer_actor_to_case() -> Scenario:
    """A participant recommends an actor: committed and offered on."""
    net = _network("offer-actor-to-case")
    return deliver(net, _recommendation(net))


@refused(MessageSemantics.OFFER_ACTOR_TO_CASE)
def offer_actor_to_case_removed() -> Scenario:
    """A recommendation of a removed participant: refused (CM-31-013)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=REMOVAL_MANAGER)
    removal = _RemovalCase(dl=dl, case=_seed(dl))
    removed = removal.remove(REMOVAL_VENDOR)
    assert removed.disposition is HandlerDisposition.APPLIED, removed.reason
    activity = recommend_actor_activity(
        REMOVAL_VENDOR,
        target=removal.read_case(),
        actor=REMOVAL_OTHER,
        to=[REMOVAL_MANAGER],
        at=authored_at(),
    )
    return Scenario(
        dl=dl,
        event=received_event(
            activity, receiving_actor_id=REMOVAL_MANAGER, at=dl
        ),
    )


@applied(MessageSemantics.OFFER_CASE_PARTICIPANT)
def offer_case_participant() -> Scenario:
    """A Case Owner that manages its case records the offer it is sent.

    At an owner that is not the CASE_MANAGER the receipt commits nothing
    (its commit is the CASE_MANAGER's), so the receiver that reaches the
    tree's commit is the managing owner (CM-16-004).
    """
    dl, _ = offer_tests._seed_dl_for_case_actor()
    offer = offer_tests._build_offer_activity(to=[offer_tests.CASE_ACTOR_ID])
    return Scenario(dl=dl, event=received_event(offer, at=dl))


@applied(MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT)
def accept_offer_case_participant() -> Scenario:
    """The owner accepts the offer: committed, and the actor is invited."""
    net, offer = _offered("accept-offer-case-participant")
    return deliver(
        net,
        accept_case_participant_offer_activity(
            offer,
            target=net.case_id,
            actor=OWNER,
            to=[MANAGER],
            at=authored_at(),
        ),
    )


@applied(MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT)
def reject_offer_case_participant() -> Scenario:
    """The owner rejects the offer: committed, and the recommender told."""
    net, offer = _offered("reject-offer-case-participant")
    return deliver(
        net,
        reject_case_participant_offer_activity(
            offer,
            target=net.case_id,
            actor=OWNER,
            to=[MANAGER],
            at=authored_at(),
        ),
    )


def _unrecorded_offer_answer(accept: bool) -> Scenario:
    """The owner answers an offer the CASE_MANAGER never recorded."""
    dl, _ = offer_tests._seed_dl_for_case_actor()
    build = (
        accept_case_participant_offer_activity
        if accept
        else reject_case_participant_offer_activity
    )
    answer = build(
        offer_tests._build_offer_activity(
            offer_id=offer_tests._NEVER_RECORDED_OFFER_ID
        ),
        target=offer_tests._case_ref(offer_tests.CASE_ID),
        actor=offer_tests.CASE_OWNER_ID,
        to=[offer_tests.CASE_ACTOR_ID],
        at=authored_at(),
    )
    return Scenario(dl=dl, event=received_event(answer, at=dl))


@refused(MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT)
def accept_offer_case_participant_unrecorded() -> Scenario:
    """An Accept of an offer never recorded: refused with a notice."""
    return _unrecorded_offer_answer(accept=True)


@refused(MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT)
def reject_offer_case_participant_unrecorded() -> Scenario:
    """A Reject of an offer never recorded: refused with a notice."""
    return _unrecorded_offer_answer(accept=False)


def _answer_receipt(verb: answer_tests.Verb) -> Scenario:
    """The recommender receives the CASE_MANAGER's answer: a receipt only.

    The CASE_MANAGER ledgered the answer when it sent it, and a participant
    commits nothing (CM-16-006, CLP-09-001), so the tree's effect here is
    the receipt alone.
    """
    dl = answer_tests._store()
    event = answer_tests._event(verb)
    return Scenario(
        dl=dl,
        event=event,
        reached=lambda store: _receipt_recorded(store, event.activity_id),
    )


@applied(MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION)
def accept_actor_recommendation() -> Scenario:
    """The recommender receives the Accept of its recommendation."""
    return _answer_receipt("accept")


@applied(MessageSemantics.REJECT_ACTOR_RECOMMENDATION)
def reject_actor_recommendation() -> Scenario:
    """The recommender receives the Reject of its recommendation."""
    return _answer_receipt("reject")


# --- the role-offer story (CM-33) ------------------------------------------


def _role_event(dl: SqliteDataLayer, activity: Any) -> Any:
    return received_event(activity, receiving_actor_id=dl.actor_id, at=dl)


def _role_answer(dl: SqliteDataLayer, offer: Any, *, accept: bool) -> Any:
    build = (
        accept_case_participant_role_activity
        if accept
        else reject_case_participant_role_activity
    )
    return _role_event(
        dl,
        build(
            offer=offer,
            actor=role_tests._TARGET_ID,
            to=[role_tests._CASE_MANAGER_ID],
            at=authored_at(),
        ),
    )


def _role_offered() -> tuple[SqliteDataLayer, Any]:
    """The CASE_MANAGER has recorded the owner's role offer and forwarded it."""
    dl = role_tests._store(role_tests._CASE_MANAGER_ID)
    offer = role_tests._offer()
    _settle(dl, _role_event(dl, offer))
    return dl, offer


@applied(MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE)
def offer_case_participant_role() -> Scenario:
    """The owner offers a role: committed and forwarded to the target."""
    dl = role_tests._store(role_tests._CASE_MANAGER_ID)
    return Scenario(dl=dl, event=_role_event(dl, role_tests._offer()))


@refused(MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE)
def offer_case_participant_role_already_held() -> Scenario:
    """A role the target already holds: refused with a notice (CM-33-003)."""
    dl = role_tests._store(role_tests._CASE_MANAGER_ID)
    return Scenario(
        dl=dl,
        event=_role_event(dl, role_tests._offer(role=CVDRole.REPORTER)),
    )


@applied(MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE)
def accept_case_participant_role() -> Scenario:
    """The target accepts: committed, granted and announced."""
    dl, offer = _role_offered()
    return Scenario(dl=dl, event=_role_answer(dl, offer, accept=True))


@applied(MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE)
def reject_case_participant_role() -> Scenario:
    """The target rejects: committed and announced, with no grant."""
    dl, offer = _role_offered()
    return Scenario(dl=dl, event=_role_answer(dl, offer, accept=False))


def _closed_role_offer(
    *, closed_by_accept: bool
) -> tuple[SqliteDataLayer, Any]:
    """The target's first answer has closed the role offer."""
    dl, offer = _role_offered()
    _settle(dl, _role_answer(dl, offer, accept=closed_by_accept))
    return dl, offer


@refused(MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE)
def accept_case_participant_role_closed() -> Scenario:
    """An Accept after the target's Reject closed the offer (CM-33-005)."""
    dl, offer = _closed_role_offer(closed_by_accept=False)
    return Scenario(dl=dl, event=_role_answer(dl, offer, accept=True))


@refused(MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE)
def reject_case_participant_role_closed() -> Scenario:
    """A Reject after the target's Accept closed the offer (CM-33-005)."""
    dl, offer = _closed_role_offer(closed_by_accept=True)
    return Scenario(dl=dl, event=_role_answer(dl, offer, accept=False))
