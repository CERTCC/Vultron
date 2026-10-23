#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from datetime import timedelta

from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_termination import FixDeployedCause
from vultron.core.states.embargo_register import TerminationReason
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    announce_embargo_activity,
    create_embargo_consent_activity,
    create_embargo_event_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    em_undo_embargo_invite_activity,
    reject_embargo_proposal_activity,
    remove_embargo_from_case_activity,
    update_embargo_consent_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Announce,
    as_Create,
    as_Invite,
    as_Leave,
    as_Reject,
    as_Remove,
    as_Undo,
    as_Update,
)
from vultron.wire.as2.vocab.examples._base import (
    EXAMPLE_TIMESTAMP,
    _example_stamp,
    case,
    case_actor,
    coordinator,
    finder,
    vendor,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent


def embargo_event(days: int = 90) -> as_EmbargoEvent:
    """An embargo of *days* days, starting at :data:`EXAMPLE_TIMESTAMP`.

    Reads no clock (#4095): ``start_time`` is the example timestamp, already
    on a whole minute, and ``end_time`` is midnight UTC *days* days later.
    Two calls therefore build equal embargoes whenever they run, so a test may
    compare an activity's embedded embargo with a fresh call.  The dates are
    fixed and so lie in the past.
    """
    start_at = EXAMPLE_TIMESTAMP
    end_at = (start_at + timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    _case = case()

    event = as_EmbargoEvent(
        id_=f"{_case.id_}/embargo_events/{end_at.isoformat()}",
        name=f"Embargo for {_case.name}",
        context=_case.id_,
        start_time=start_at,
        end_time=end_at,
        content=f"We propose to embargo {_case.name} for {days} days.",
        **_example_stamp(),
    )
    return event


def propose_embargo() -> as_Invite:
    embargo = embargo_event()
    _case = case()
    _vendor = vendor()

    activity = em_propose_embargo_activity(
        embargo,
        id_=f"{_case.id_}/embargo_proposals/1",
        actor=_vendor.id_,
        context=_case.id_,
        summary="We propose to embargo case 1 for 90 days.",
    )
    return activity


def relay_embargo_proposal() -> as_Invite:
    """The CASE_MANAGER's Invite asking one participant about a proposal.

    The CASE_MANAGER relays each adjudicated proposal as an ``Invite(Event)``
    of its own, one per participant other than the proposer, naming the
    proposer in ``attributedTo`` (EP-09-002, CM-24).  The wire form is the
    proposer's ``Invite(Event)``; only the sender and addressee differ
    (MSM-08-009).  The CASE_MANAGER stamps every relayed Invite with the
    RSVP deadline it alone evaluates, carried as the activity's ``endTime``
    and measured from its ``published`` time (CM-28-012, EP-07-002); here a
    week after publication, well inside the embargo.
    """
    embargo = embargo_event()
    _case = case()
    return em_propose_embargo_activity(
        embargo,
        id_=f"{_case.id_}/embargo_proposals/1/invites/coordinator",
        actor=case_actor().id_,
        attributed_to=vendor().id_,
        to=[coordinator().id_],
        context=_case.id_,
        published=EXAMPLE_TIMESTAMP,
        rsvp_deadline=EXAMPLE_TIMESTAMP + timedelta(days=7),
        summary="The vendor proposes to embargo case 1 for 90 days.",
    )


def undo_embargo_invite() -> as_Undo:
    """The CASE_MANAGER's withdrawal of an Invite it relayed (EMB-16-001).

    Once the case is public, an exploit is public or attacks are observed
    while the proposal is open, the CASE_MANAGER abandons it: it rejects the
    proposal it received, then withdraws each Invite it relayed for it.  An
    actor undoes only an activity it performed (ADR-0152).  It is addressed
    to nobody: each participant learns of it from the ledger entry
    (EP-09-009).
    """
    invite = relay_embargo_proposal()
    return em_undo_embargo_invite_activity(
        invite,
        id_=f"{invite.id_}/undo",
        actor=case_actor().id_,
        context=invite.context,
        published=EXAMPLE_TIMESTAMP,
    )


def create_embargo_event() -> as_Create:
    """The CASE_MANAGER's ``Create(EmbargoEvent)`` of a new case's embargo.

    A case's creation writes its default embargo, and the CASE_MANAGER
    commits it in full as the ``create_embargo_event`` entry right after the
    genesis entry (CLP-07-013).  It is addressed to nobody: each participant
    takes the embargo from the ledger.
    """
    _case = case()
    embargo = embargo_event()
    return create_embargo_event_activity(
        embargo,
        id_=f"{embargo.id_}/create",
        actor=case_actor().id_,
        context=_case.id_,
        published=EXAMPLE_TIMESTAMP,
    )


def create_embargo_consent() -> as_Create:
    """The CASE_MANAGER's ``Create(EmbargoConsent)`` of a participant's row.

    When an embargo is proposed, the CASE_MANAGER creates each participant's
    ``UNINVITED`` row for it and commits the row in full as its own
    ``create_embargo_consent`` entry (ADR-0122, CLP-07-013).  It is
    addressed to nobody: each participant takes the row from the ledger.
    """
    _case = case()
    row = EmbargoConsent(
        embargo_id=embargo_event().id_,
        state=EmbargoConsentState.UNINVITED,
        attributed_to=vendor().id_,
    )
    return create_embargo_consent_activity(
        row,
        id_=f"{row.id_}/create",
        actor=case_actor().id_,
        context=_case.id_,
        published=EXAMPLE_TIMESTAMP,
    )


def update_embargo_consent() -> as_Update:
    """The CASE_MANAGER's ``Update(EmbargoConsent)`` of a participant's row.

    When an embargo invitation's RSVP deadline passes unanswered, the
    CASE_MANAGER moves the invitee's row to ``TIMED_OUT`` and commits the
    changed row in full as its own ``update_embargo_consent`` entry
    (CM-28-009, ADR-0140).  It records a change of its own consent the same
    way (MSM-07-004).
    """
    _case = case()
    row = EmbargoConsent(
        embargo_id=embargo_event().id_,
        state=EmbargoConsentState.TIMED_OUT,
        attributed_to=vendor().id_,
    )
    return update_embargo_consent_activity(
        row,
        id_=f"{row.id_}/update",
        actor=case_actor().id_,
        context=_case.id_,
        published=EXAMPLE_TIMESTAMP,
    )


def accept_embargo() -> as_Accept:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = em_accept_embargo_activity(
        proposal,
        actor=_vendor.id_,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def reject_embargo() -> as_Reject:
    proposal = propose_embargo()
    _vendor = vendor()
    activity = em_reject_embargo_activity(
        proposal,
        actor=_vendor.id_,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )
    return activity


def propose_embargo_revision() -> as_Invite:
    """EV: a proposal sent while an embargo is active, so it is a revision.

    The wire form is the same ``Invite(Event)`` as an initial proposal
    (MSM-02-001); only the receiver's EM state makes it a revision.
    """
    revision = embargo_event(120)
    _case = case()
    return em_propose_embargo_activity(
        revision,
        id_=f"{_case.id_}/embargo_proposals/2",
        actor=vendor().id_,
        context=_case.id_,
        summary="We propose to extend the embargo on case 1 to 120 days.",
    )


def accept_embargo_revision() -> as_Accept:
    """EC: a participant's consent to a proposed revision."""
    proposal = propose_embargo_revision()
    return em_accept_embargo_activity(
        proposal,
        actor=vendor().id_,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )


def reject_embargo_revision() -> as_Reject:
    """EJ: a participant's refusal of a proposed revision."""
    proposal = propose_embargo_revision()
    return em_reject_embargo_activity(
        proposal,
        actor=vendor().id_,
        context=proposal.context,
        to="https://vultron.example/cases/1/participants",
    )


def activate_embargo() -> as_Accept:
    """The case owner's activation of the proposed embargo (ADR-0122)."""
    _case = case()
    _vendor = vendor()
    activity = activate_embargo_activity(
        embargo_event(),
        actor=_vendor.id_,
        target=_case.id_,
        context=_case.id_,
    )
    return activity


def reject_embargo_proposal() -> as_Reject:
    """The case owner's rejection of the proposed embargo (ADR-0122)."""
    _case = case()
    _vendor = vendor()
    activity = reject_embargo_proposal_activity(
        embargo_event(),
        actor=_vendor.id_,
        target=_case.id_,
        context=_case.id_,
    )
    return activity


def withdraw_from_embargo() -> as_Leave:
    """A signatory withdraws from the embargo in force (MSM-07-010).

    The finder, a signatory with no ``Invite(EmbargoEvent)`` of its own,
    sends the ``Leave`` to the CASE_MANAGER (EP-09-013, PCR-08).
    """
    _case = case()
    return withdraw_from_embargo_activity(
        embargo_event(),
        actor=finder().id_,
        context=_case.id_,
        to=case_actor().id_,
    )


def announce_embargo() -> as_Announce:
    _vendor = vendor()
    _case = case()

    activity = announce_embargo_activity(
        embargo_event(90),
        actor=_vendor.id_,
        context=_case.id_,
        to=f"{_case.id_}/participants",
    )
    return activity


def announce_embargo_termination() -> as_Announce:
    """The CASE_MANAGER announces that the embargo has ended (EMB-19-001).

    After it tears the embargo down on a Case Owner's ``Remove(Event)`` sent
    before the end time, the CASE_MANAGER sends ``Announce(Event)`` naming
    the terminated embargo to every other active participant except a Closed
    Participant, the Case Owner (the vendor) included (CM-10-004,
    CM-23-004).  The wire form is the same as ``announce_embargo``'s; the
    embargo it names, which the case's register records as terminated, makes
    it a termination announcement.
    """
    _case = case()
    return announce_embargo_activity(
        embargo_event(90),
        actor=case_actor().id_,
        context=_case.id_,
        to=[vendor().id_, coordinator().id_, finder().id_],
    )


def remove_embargo() -> as_Remove:
    """The Case Owner's ``Remove(Event)`` ending the embargo early.

    It names why as ``terminationCause`` (EMB-13-005): here the fix is
    deployed.  The CASE_MANAGER records the owner's cause as given.
    """
    _vendor = vendor()
    _case = case()
    activity = remove_embargo_from_case_activity(
        embargo_event(90),
        actor=_vendor.id_,
        origin=_case.id_,
        reason=TerminationReason.EARLY,
        cause=FixDeployedCause(),
    )
    return activity


def notify_embargo_termination() -> as_Remove:
    """The CASE_MANAGER's ``Remove(Event)`` telling a participant the embargo
    has ended.

    The CASE_MANAGER addresses its own termination to every other participant
    (EMB-19-001), naming the Case Owner it acts for in ``attributedTo``
    (CM-24).  The wire form is the Case Owner's ``Remove(Event)``; only the
    sender and addressee differ (MSM-08-009).
    """
    _case = case()
    return remove_embargo_from_case_activity(
        embargo_event(90),
        actor=case_actor().id_,
        attributed_to=vendor().id_,
        to=[coordinator().id_],
        origin=_case.id_,
        context=_case.id_,
        reason=TerminationReason.EARLY,
    )
