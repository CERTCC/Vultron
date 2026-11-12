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

"""Builders for the case lifecycle, its creation and its proposal."""

from collections.abc import Callable

from test.core.behaviors.case.test_create_case_received_tree import (
    _CASE_ID as _CREATED_CASE_ID,
    _CREATOR,
    _RECEIVER,
    _case,
    _link,
)
from test.support.objects import authored_at, make
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models._helpers import _as_id
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import (
    add_report_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.examples._base import gen_report

from .._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from ..actor.test_announce import (
    _CASE_ACTOR_ID,
    _CASE_ID as _ANNOUNCED_CASE_ID,
    _RECEIVER_ID,
    _anchor_expected_authority,
    _owned,
)
from ..test_case_manager_note_replay import _set_rm
from ..test_case_proposal import (
    _CASE_ACTOR_URI,
    _VENDOR_URI,
    _make_proposal,
    _seed_vendor_link,
)
from . import Scenario, applied
from ._net import deliver

_BASE = "https://example.org/cases/rerun-sweep"


def _stored(object_id: str) -> Callable[[SqliteDataLayer], str | None]:
    """A replica's effect is a stored record: check *object_id* is there."""

    def _check(dl: SqliteDataLayer) -> str | None:
        if dl.read(object_id) is not None:
            return None
        return f"{object_id} was not stored"

    return _check


def _rm_move(tag: str, build, rm: RM) -> Scenario:
    net = LedgerNetwork(f"{_BASE}/{tag}", em_state=EM.NONE)
    _set_rm(net, BYSTANDER, rm)
    return deliver(
        net,
        build(
            net.case(BYSTANDER),
            actor=BYSTANDER,
            to=[MANAGER],
            at=authored_at(),
        ),
    )


@applied(MessageSemantics.ENGAGE_CASE)
def engage_case() -> Scenario:
    """A participant at RM.VALID engages: committed and announced."""
    return _rm_move("engage-case", rm_engage_case_activity, RM.VALID)


@applied(MessageSemantics.DEFER_CASE)
def defer_case() -> Scenario:
    """A participant at RM.VALID defers: committed with its status."""
    return _rm_move("defer-case", rm_defer_case_activity, RM.VALID)


@applied(MessageSemantics.CLOSE_CASE)
def close_case() -> Scenario:
    """A participant that is not the owner leaves: closed and announced."""
    return _rm_move("close-case", rm_close_case_activity, RM.ACCEPTED)


@applied(MessageSemantics.ADD_REPORT_TO_CASE)
def add_report_to_case() -> Scenario:
    """The case owner adds a new report: attached, committed, announced."""
    net = LedgerNetwork(f"{_BASE}/add-report", em_state=EM.NONE)
    return deliver(
        net,
        add_report_to_case_activity(
            gen_report(),
            target=net.case_id,
            actor=OWNER,
            to=[MANAGER],
            at=authored_at(),
        ),
    )


@applied(MessageSemantics.CREATE_CASE)
def create_case() -> Scenario:
    """The case's creator seeds a reporter's replica on the trusted route."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    dl.save(_link())
    event = received_event(
        create_case_activity(
            _case(), actor=_CREATOR, to=[_RECEIVER], at=authored_at()
        ),
        at=dl,
    )
    return Scenario(dl=dl, event=event, reached=_stored(_CREATED_CASE_ID))


@applied(MessageSemantics.ANNOUNCE_VULNERABILITY_CASE)
def announce_vulnerability_case() -> Scenario:
    """The invited case's CASE_MANAGER announces it: the invitee seeds it."""
    from test.support.case_owner import CASE_OWNER_ID
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCase,
    )

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER_ID)
    _anchor_expected_authority(dl)
    case = make(
        as_VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_=_ANNOUNCED_CASE_ID,
        name="re-run sweep announce",
    )
    event = received_event(
        announce_vulnerability_case_activity(
            _owned(case),
            actor=_CASE_ACTOR_ID,
            to=[_RECEIVER_ID],
            context=_ANNOUNCED_CASE_ID,
            at=authored_at(),
        ),
        at=dl,
    )
    return Scenario(dl=dl, event=event, reached=_stored(_ANNOUNCED_CASE_ID))


@applied(MessageSemantics.CREATE_CASE_PROPOSAL)
def create_case_proposal() -> Scenario:
    """A vendor proposes a case: the case actor creates it and accepts."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    event = received_event(
        make(
            as_Create,
            actor=make(VultronOrganization, id_=_VENDOR_URI),
            object_=_make_proposal(),
            to=[_CASE_ACTOR_URI],
        ),
        receiving_actor_id=_CASE_ACTOR_URI,
    )
    return Scenario(dl=dl, event=event)


def _answer(activity_cls) -> Scenario:
    """The case actor's answer to the vendor's proposal, at the vendor."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    _seed_vendor_link(dl, proposal)
    report_id = _as_id(proposal.object_)
    assert report_id is not None
    link_id = VultronReportCaseLink.build_id(report_id)
    before = dl.read(link_id)
    event = received_event(
        make(
            activity_cls,
            actor=_CASE_ACTOR_URI,
            object_=proposal,
            to=[_VENDOR_URI],
        ),
        receiving_actor_id=_VENDOR_URI,
    )

    def _recorded(store: SqliteDataLayer) -> str | None:
        if store.read(link_id) != before:
            return None
        return f"the answer left the report-case link {link_id} as it was"

    return Scenario(dl=dl, event=event, reached=_recorded)


@applied(MessageSemantics.ACCEPT_CASE_PROPOSAL)
def accept_case_proposal() -> Scenario:
    """The case actor accepts: the vendor records it on its link."""
    return _answer(as_Accept)


@applied(MessageSemantics.REJECT_CASE_PROPOSAL)
def reject_case_proposal() -> Scenario:
    """The case actor rejects: the vendor marks its link rejected."""
    return _answer(as_Reject)
