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
"""Messages that each carry every slot their event requires, and their cuts.

Shared by the tests that pin where a message missing a required slot is
refused (#6493): one :class:`SlotCase` per slot a received ``execute()``
used to test for, a builder of each complete message from the production
factories, and :func:`without_slot`, which cuts the wire field that holds
the slot (ARCH-10-001, ADR-0032).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from test.support.future_dates import days_from_now
from test.support.objects import authored_at, make
from test.support.received import stamped
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.events import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.states.embargo_register import TerminationReason
from vultron.wire.as2 import factories as F
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
    as_Offer,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

SENDER = "https://example.org/actors/slot-sender"
RECEIVER = "https://example.org/actors/slot-receiver"
CASE_ID = "https://example.org/cases/slot-case"
_TAIL = LedgerPosition(log_index=-1, entry_hash="0" * 64)
_HELD_TAIL = LedgerPosition(log_index=0, entry_hash="1" * 64)


def _sent(**extra: Any) -> dict[str, Any]:
    return {"actor": SENDER, "to": [RECEIVER], "at": authored_at(), **extra}


def _answered(**extra: Any) -> dict[str, Any]:
    return {"actor": RECEIVER, "to": [SENDER], "at": authored_at(), **extra}


def _case() -> as_VulnerabilityCase:
    return make(
        as_VulnerabilityCase,
        id_=CASE_ID,
        attributed_to=SENDER,
        name="slot case",
        stub_summary="a parser memory-safety vul",
    )


def _embargo() -> as_EmbargoEvent:
    return make(
        as_EmbargoEvent,
        id_="https://example.org/embargoes/slot-embargo",
        context=CASE_ID,
        end_time=days_from_now(30),
    )


def _report() -> as_VulnerabilityReport:
    return make(
        as_VulnerabilityReport,
        id_="https://example.org/reports/slot-report",
        content="slot report",
    )


def _proposal() -> as_CaseProposal:
    return make(
        as_CaseProposal,
        attributed_to=SENDER,
        object_=gen_report(),
        target=RECEIVER,
    )


def _full_case_invite() -> as_Invite:
    return F.rm_invite_to_full_case_activity(
        RECEIVER, _case(), _TAIL, **_sent()
    )


def _stub_invite() -> as_Invite:
    return F.rm_invite_to_case_activity(RECEIVER, _case(), **_sent())


def _embargo_invite() -> as_Invite:
    return F.em_propose_embargo_activity(
        _embargo(), context=_case(), **_sent()
    )


def _participant_offer() -> as_Offer:
    return F.offer_case_participant_activity(
        "https://example.org/actors/slot-recommended",
        target=_case(),
        **_sent(),
    )


def _ledger_entry() -> Any:
    return HashChainLedgerRecord(
        case_id=CASE_ID,
        log_index=0,
        object_id="https://example.org/activities/slot-entry",
        semantic_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash="0" * 64,
        received_at=authored_at(),
    ).to_ledger_entry()


#: A builder of each complete message, by the name the rows use.
BUILDERS: dict[str, Callable[[], as_Activity]] = {
    "Invite(full case)": _full_case_invite,
    "Accept(full-case Invite)": lambda: F.rm_accept_full_case_invite_activity(
        _full_case_invite(), _TAIL, **_answered()
    ),
    "TentativeReject(full-case Invite)": lambda: (
        F.rm_tentative_reject_full_case_invite_activity(
            _full_case_invite(), _TAIL, **_answered()
        )
    ),
    "Reject(full-case Invite)": lambda: F.rm_reject_full_case_invite_activity(
        _full_case_invite(), _TAIL, **_answered()
    ),
    "Invite(stub)": _stub_invite,
    "Accept(stub Invite)": lambda: F.rm_accept_invite_to_case_activity(
        _stub_invite(), **_answered()
    ),
    "Reject(stub Invite)": lambda: F.rm_reject_invite_to_case_activity(
        _stub_invite(), **_answered()
    ),
    "Offer(CaseParticipant)": _participant_offer,
    "Accept(Offer(CaseParticipant))": lambda: (
        F.accept_case_participant_offer_activity(
            _participant_offer(), target=_case(), **_answered()
        )
    ),
    "Reject(Offer(CaseParticipant))": lambda: (
        F.reject_case_participant_offer_activity(
            _participant_offer(), target=_case(), **_answered()
        )
    ),
    "Offer(Actor)": lambda: F.recommend_actor_activity(
        "https://example.org/actors/slot-recommended",
        target=_case(),
        **_sent(),
    ),
    "Create(VulnerabilityCase)": lambda: F.create_case_activity(
        _case(), **_sent()
    ),
    "Join(VulnerabilityCase)": lambda: F.rm_engage_case_activity(
        _case(), **_sent()
    ),
    "Ignore(VulnerabilityCase)": lambda: F.rm_defer_case_activity(
        _case(), **_sent()
    ),
    "Add(VulnerabilityReport)": lambda: F.add_report_to_case_activity(
        _report(), target=_case(), **_sent()
    ),
    "Leave(VulnerabilityCase)": lambda: F.rm_close_case_activity(
        _case(), **_sent()
    ),
    "Accept(CaseProposal)": lambda: F.accept_case_proposal_activity(
        RECEIVER, _proposal(), [SENDER], at=authored_at()
    ),
    "Reject(CaseProposal)": lambda: F.reject_case_proposal_activity(
        RECEIVER, _proposal(), [SENDER], at=authored_at()
    ),
    "Add(EmbargoEvent)": lambda: F.activate_embargo_activity(
        _embargo(),
        "https://example.org/invites/slot",
        target=_case(),
        **_sent(),
    ),
    "Reject(EmbargoEvent)": lambda: F.reject_embargo_proposal_activity(
        _embargo(),
        "https://example.org/invites/slot",
        target=_case(),
        **_sent(),
    ),
    "Leave(EmbargoEvent)": lambda: F.withdraw_from_embargo_activity(
        _embargo(), context=_case(), **_sent()
    ),
    "Accept(Invite(EmbargoEvent))": lambda: F.em_accept_embargo_activity(
        _embargo_invite(), context=_case(), **_answered()
    ),
    "Reject(Invite(EmbargoEvent))": lambda: F.em_reject_embargo_activity(
        _embargo_invite(), context=_case(), **_answered()
    ),
    "Remove(EmbargoEvent)": lambda: F.remove_embargo_from_case_activity(
        _embargo(),
        origin=_case(),
        reason=TerminationReason.END_TIME_REACHED,
        **_sent(),
    ),
    "Add(Note)": lambda: F.add_note_to_case_activity(
        make(
            as_Note,
            id_="https://example.org/notes/slot-note",
            content="slot note",
            context=CASE_ID,
        ),
        target=_case(),
        **_sent(),
    ),
    "Accept(Offer(VulnerabilityReport))": lambda: (
        F.rm_validate_report_activity(
            F.rm_submit_report_activity(
                _report(), to=RECEIVER, actor=SENDER, at=authored_at()
            ),
            **_answered(),
        )
    ),
    "Announce(CaseLedgerEntry)": lambda: F.announce_log_entry_activity(
        _ledger_entry(), **_sent()
    ),
    "Reject(CaseLedgerEntry)": lambda: F.genesis_replay_reject_activity(
        CASE_ID, _TAIL, "https://example.org/announces/slot", **_sent()
    ),
    "Read(CaseLedgerEntry)": lambda: F.read_ledger_position_activity(
        CASE_ID, _HELD_TAIL, **_sent()
    ),
}


@dataclass(frozen=True)
class SlotCase:
    """One required slot, and the wire fields cut to leave it empty."""

    message: str
    semantics: MessageSemantics
    slot: str
    cuts: tuple[tuple[str, ...], ...]
    #: The semantics the cut message matches: its own when its pattern
    #: still matches, so the inbox's extraction reaches the event and raises;
    #: ``UNKNOWN`` when the pattern requires the field the cut removed.
    cut_matches: MessageSemantics = MessageSemantics.UNKNOWN

    @property
    def id(self) -> str:
        return f"{self.message}-{self.slot}"


_S = MessageSemantics
_OBJ = ("object_",)

#: Every slot one of #6493's 28 removed ``execute()`` checks tested.
CASES: tuple[SlotCase, ...] = (
    SlotCase(
        "Invite(full case)",
        _S.INVITE_ACTOR_TO_FULL_CASE,
        "case_id",
        (("target",),),
    ),
    SlotCase(
        "Invite(full case)",
        _S.INVITE_ACTOR_TO_FULL_CASE,
        "invitee_id",
        (_OBJ,),
    ),
    *(
        SlotCase(message, semantics, slot, cuts)
        for message, semantics in (
            ("Accept(full-case Invite)", _S.ACCEPT_INVITE_ACTOR_TO_FULL_CASE),
            (
                "TentativeReject(full-case Invite)",
                _S.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE,
            ),
            ("Reject(full-case Invite)", _S.REJECT_INVITE_ACTOR_TO_FULL_CASE),
        )
        for slot, cuts in (
            ("invite_id", (_OBJ,)),
            ("case_id", (("object_", "target"),)),
        )
    ),
    SlotCase(
        "Invite(stub)", _S.INVITE_ACTOR_TO_CASE, "case_id", (("target",),)
    ),
    SlotCase("Invite(stub)", _S.INVITE_ACTOR_TO_CASE, "invitee_id", (_OBJ,)),
    SlotCase(
        "Accept(stub Invite)",
        _S.ACCEPT_INVITE_ACTOR_TO_CASE,
        "invite_id",
        (_OBJ,),
    ),
    SlotCase(
        "Accept(stub Invite)",
        _S.ACCEPT_INVITE_ACTOR_TO_CASE,
        "case_id",
        (("object_", "target"),),
    ),
    SlotCase(
        "Accept(stub Invite)",
        _S.ACCEPT_INVITE_ACTOR_TO_CASE,
        "invitee_id",
        (("object_", "object_"),),
    ),
    SlotCase(
        "Reject(stub Invite)",
        _S.REJECT_INVITE_ACTOR_TO_CASE,
        "invite_id",
        (_OBJ,),
    ),
    SlotCase(
        "Reject(stub Invite)",
        _S.REJECT_INVITE_ACTOR_TO_CASE,
        "case_id",
        (("object_", "target"),),
    ),
    SlotCase(
        "Offer(CaseParticipant)",
        _S.OFFER_CASE_PARTICIPANT,
        "case_id",
        (("target",),),
    ),
    SlotCase(
        "Accept(Offer(CaseParticipant))",
        _S.ACCEPT_OFFER_CASE_PARTICIPANT,
        "case_id",
        (("target",), ("object_", "target")),
    ),
    SlotCase(
        "Reject(Offer(CaseParticipant))",
        _S.REJECT_OFFER_CASE_PARTICIPANT,
        "case_id",
        (("target",),),
        cut_matches=_S.REJECT_OFFER_CASE_PARTICIPANT,
    ),
    SlotCase(
        "Offer(Actor)", _S.OFFER_ACTOR_TO_CASE, "recommended_id", (_OBJ,)
    ),
    SlotCase(
        "Offer(Actor)", _S.OFFER_ACTOR_TO_CASE, "case_id", (("target",),)
    ),
    SlotCase("Create(VulnerabilityCase)", _S.CREATE_CASE, "case", (_OBJ,)),
    SlotCase("Join(VulnerabilityCase)", _S.ENGAGE_CASE, "case_id", (_OBJ,)),
    SlotCase("Ignore(VulnerabilityCase)", _S.DEFER_CASE, "case_id", (_OBJ,)),
    SlotCase(
        "Add(VulnerabilityReport)",
        _S.ADD_REPORT_TO_CASE,
        "report_id",
        (_OBJ,),
    ),
    SlotCase(
        "Add(VulnerabilityReport)",
        _S.ADD_REPORT_TO_CASE,
        "case_id",
        (("target",),),
    ),
    SlotCase("Leave(VulnerabilityCase)", _S.CLOSE_CASE, "case_id", (_OBJ,)),
    SlotCase(
        "Accept(CaseProposal)",
        _S.ACCEPT_CASE_PROPOSAL,
        "report_id",
        (("object_", "object_"),),
        cut_matches=_S.ACCEPT_CASE_PROPOSAL,
    ),
    SlotCase(
        "Reject(CaseProposal)",
        _S.REJECT_CASE_PROPOSAL,
        "report_id",
        (("object_", "object_"),),
        cut_matches=_S.REJECT_CASE_PROPOSAL,
    ),
    *(
        row
        for message, semantics, case_field, objectless in (
            (
                "Add(EmbargoEvent)",
                _S.ACTIVATE_EMBARGO_ON_CASE,
                "target",
                _S.UNKNOWN,
            ),
            (
                "Reject(EmbargoEvent)",
                _S.REJECT_EMBARGO_PROPOSAL_ON_CASE,
                "target",
                # A Reject naming a case and no object is the genesis
                # replay request (SYNC-16-027).
                _S.REJECT_CASE_LEDGER_ENTRY,
            ),
            (
                "Leave(EmbargoEvent)",
                _S.WITHDRAW_FROM_EMBARGO_ON_CASE,
                "context",
                _S.UNKNOWN,
            ),
        )
        for row in (
            SlotCase(message, semantics, "embargo_id", (_OBJ,), objectless),
            SlotCase(message, semantics, "case_id", ((case_field,),)),
        )
    ),
    SlotCase(
        "Accept(Invite(EmbargoEvent))",
        _S.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        "invite_id",
        (_OBJ,),
    ),
    SlotCase(
        "Accept(Invite(EmbargoEvent))",
        _S.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        "embargo_id",
        (("object_", "object_"),),
    ),
    SlotCase(
        "Reject(Invite(EmbargoEvent))",
        _S.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        "invite_id",
        (_OBJ,),
    ),
    SlotCase(
        "Reject(Invite(EmbargoEvent))",
        _S.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        "embargo_id",
        (("object_", "object_"),),
    ),
    SlotCase(
        "Reject(Invite(EmbargoEvent))",
        _S.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        "case_id",
        (("object_", "context"),),
    ),
    SlotCase(
        "Remove(EmbargoEvent)",
        _S.REMOVE_EMBARGO_EVENT_FROM_CASE,
        "embargo_id",
        (_OBJ,),
    ),
    SlotCase(
        "Remove(EmbargoEvent)",
        _S.REMOVE_EMBARGO_EVENT_FROM_CASE,
        "case_id",
        (("origin",),),
        cut_matches=_S.REMOVE_EMBARGO_EVENT_FROM_CASE,
    ),
    SlotCase("Add(Note)", _S.ADD_NOTE_TO_CASE, "note", (_OBJ,)),
    SlotCase("Add(Note)", _S.ADD_NOTE_TO_CASE, "case_id", (("target",),)),
    SlotCase(
        "Accept(Offer(VulnerabilityReport))",
        _S.VALIDATE_REPORT,
        "offer_id",
        (_OBJ,),
    ),
    SlotCase(
        "Accept(Offer(VulnerabilityReport))",
        _S.VALIDATE_REPORT,
        "report_id",
        (("object_", "object_"),),
    ),
    SlotCase(
        "Announce(CaseLedgerEntry)",
        _S.ANNOUNCE_CASE_LEDGER_ENTRY,
        "log_entry",
        (_OBJ,),
    ),
    SlotCase(
        "Reject(CaseLedgerEntry)",
        _S.REJECT_CASE_LEDGER_ENTRY,
        "rejected_case_id",
        (("target",),),
    ),
    SlotCase(
        "Read(CaseLedgerEntry)",
        _S.READ_CASE_LEDGER_ENTRY,
        "replay_case_id",
        (("context",),),
        cut_matches=_S.READ_CASE_LEDGER_ENTRY,
    ),
)

#: The messages the rows cover, one complete build each.
MESSAGES = sorted({case.message for case in CASES})


def complete(message: str) -> as_Activity:
    """The complete *message*, stating its sender's ledger position."""
    return stamped(BUILDERS[message]())


def _cut(activity: Any, path: tuple[str, ...]) -> Any:
    head, *rest = path
    value = None if not rest else _cut(getattr(activity, head), tuple(rest))
    return activity.model_copy(update={head: value})


def without_slot(case: SlotCase) -> as_Activity:
    """The complete message with *case*'s wire fields cut."""
    activity = complete(case.message)
    for path in case.cuts:
        activity = _cut(activity, path)
    return activity


def slot_reason(case: SlotCase) -> str:
    """The reason the event's construction gives for *case*'s slot."""
    return f"is missing its required {case.slot} (ARCH-10-001)"
