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

"""Embargo lifecycle exchange helpers shared by the embargo demo scenarios.

Three helpers drive one embargo transition each through the real trigger
endpoints, so the behavior tree of every actor runs (they puppeteer; none
injects an activity into an inbox):

- :func:`demo_propose_and_activate_embargo` — a first proposal, ``EM.NONE`` to
  ``EM.ACTIVE`` (DEMOMA-20-002);
- :func:`demo_propose_embargo_revision` — revised terms, ``EM.ACTIVE`` to
  ``EM.REVISE`` and back (DEMOMA-21-002);
- :func:`demo_terminate_embargo` — ``EM.ACTIVE`` to ``EM.EXITED``
  (DEMOMA-20-003).

A proposer sends its ``Invite(EmbargoEvent)`` to the CASE_MANAGER only.  The
CASE_MANAGER adjudicates it and relays an Invite to every other participant
(EP-09-001, EP-09-002), each of which answers the Invite addressed to *it* —
no participant polls for another's message (EP-09-003).  The case owner's
answer is also the decision that activates the embargo (EP-09-005), so the
owner answers last, after the others have had their say (EP-09-006).  Shared
steps live in private functions here so the revision does not copy the
propose-and-activate sequence (DEMOMA-21-011).

Each helper takes :class:`~vultron.demo.actor_session.ActorSession` objects
rather than bare clients: a trigger needs the actor as well as its container
(DEMOMA-26-001).  Every session MUST be bound to its own container's view of
the actor; the helpers bind the case themselves.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.polling import (
    LEDGER_COVERAGE_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    find_embargo_invite_for_actor,
    resolve_case_actor_store_id,
    wait_for_case_em_state,
    wait_for_participant_embargo_accepted,
    wait_for_participant_embargo_consent,
)
from vultron.demo.utils import demo_check, demo_gate, demo_step, ref_id
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: Length of the embargo a first proposal states.
PROPOSED_EMBARGO_DAYS = 90
#: Length of the embargo a revision states — longer than the first, so the
#: revision is a real change and any signatory that did not answer it lapses
#: (EP-05-001).
REVISED_EMBARGO_DAYS = 120
#: Budgets reuse the shared constants (EDF-06-008).  An Invite bounds proposal
#: trigger -> CASE_MANAGER commit -> relay -> invitee inbox, the invitation-chain
#: budget; a commit showing in a store adds the ``Announce(CaseLedgerEntry)``
#: hop, the ledger-coverage budget.
INVITE_TIMEOUT_SECONDS = PARTICIPANT_JOIN_TIMEOUT
COMMIT_TIMEOUT_SECONDS = LEDGER_COVERAGE_TIMEOUT


def _end_time(days: int) -> datetime:
    """A timezone-aware embargo end *days* from now (the trigger requires one)."""
    return datetime.now().astimezone() + timedelta(days=days)


def _proposed_embargo_id(result_activity_object: object, verb: str) -> str:
    """The embargo id a proposal trigger's emitted Invite carries.

    Raises:
        AssertionError: when the emitted activity names no embargo.
    """
    embargo_id = ref_id(result_activity_object)
    if embargo_id is None:
        raise AssertionError(
            f"the {verb} trigger emitted an activity that names no embargo"
        )
    return embargo_id


def _answer_relayed_invite(
    answerer: ActorSession,
    embargo_id: str,
    label: str,
) -> bool:
    """Gate on *answerer*'s relayed Invite, then accept it.

    The delivered Invite is the cause of the answer, so the answer nests inside
    the gate: a timeout skips it instead of answering a proposal the actor never
    received (EDF-06-005, ADR-0058).  The answer records consent — and, for the
    case owner, activates the embargo — once the CASE_MANAGER commits it.
    The answer names no ``proposal_id``: the earliest-expiring open proposal
    is answered (EP-08-002), and only one is open while a demo helper runs.

    Returns:
        Whether the answer was posted — ``False`` when the Invite never arrived.
    """
    answered = False
    with demo_gate(f"{label} received the relayed Invite of {embargo_id}"):
        find_embargo_invite_for_actor(
            client=answerer.client,
            embargo_id=embargo_id,
            invitee_id=answerer.actor.id_,
            timeout_seconds=INVITE_TIMEOUT_SECONDS,
        )
        with demo_step(f"{label} accepts the embargo"):
            answerer.accept_embargo()
        answered = True
    return answered


def _answer_in_owner_order(
    proposer: ActorSession,
    answerers: list[tuple[str, ActorSession]],
    owner: tuple[str, ActorSession],
    embargo_id: str,
    committed: Callable[[ActorSession], None] | None = None,
) -> None:
    """Every non-owner answers the relayed Invite, then the owner does.

    The owner's answer decides the embargo (EP-09-005), so it goes last to
    let the others consent first (EP-09-006).  An owner that is also the
    proposer was never sent an Invite (EP-09-002), and its proposal already
    counts as its consent (ADR-0093); it only needs to decide, so it answers
    without waiting for an Invite.  *committed* gates the owner on each
    non-owner's answer having been committed, so the owner does not decide
    before the others have consented; it waits only for those that answered.
    """
    answered = [
        session
        for label, session in answerers
        if _answer_relayed_invite(session, embargo_id, label)
    ]
    owner_label, owner_session = owner
    # The trigger's 202 is no evidence the answer was committed (EDF-06-001),
    # so the owner decides only once each answer is seen where it commits.
    with demo_gate("Non-owner answers are committed before the owner decides"):
        if committed is not None:
            for session in answered:
                committed(session)
        if owner_session.actor.id_ == proposer.actor.id_:
            with demo_step(f"{owner_label} accepts its own proposal as owner"):
                owner_session.accept_embargo()
        else:
            _answer_relayed_invite(owner_session, embargo_id, owner_label)


def _await_consent_committed(
    observer: ActorSession,
    answerer: ActorSession,
    case_id: str,
    embargo_id: str,
) -> None:
    """Gate on *answerer*'s consent being ``ACCEPTED`` in the CASE_MANAGER's store.

    Only meaningful for a first proposal, where the answer moves the answerer
    from invited to accepted.  A signatory's answer to a revision changes no
    consent state (EP-09-004), so there is nothing to observe there.
    """
    wait_for_participant_embargo_consent(
        observer.client,
        case_id,
        answerer.actor.id_,
        embargo_id,
        EmbargoConsentState.ACCEPTED,
        COMMIT_TIMEOUT_SECONDS,
        dl_actor_id=resolve_case_actor_store_id(observer.client, case_id),
    )


def _verify_embargo_active(
    replicas: list[tuple[str, ActorSession]],
    case: as_VulnerabilityCase,
    embargo_id: str,
    canonical: ActorSession | None = None,
) -> None:
    """Check *embargo_id* is active in the CASE_MANAGER's store and every replica.

    The owner's answer is only committed some time after its trigger returns,
    and each replica learns of it from the ledger afterwards, so each read is
    polled.  The read also pins the active embargo's id: ``EM.ACTIVE`` alone
    cannot tell a replica that applied a revision from one that has not heard
    of it (``ACTIVE`` both before and after).
    """
    if canonical is not None:
        with demo_check(
            "CASE_MANAGER's canonical case has EM.ACTIVE with embargo"
            f" {embargo_id}"
        ):
            wait_for_case_em_state(
                canonical.client,
                case.id_,
                EM.ACTIVE,
                COMMIT_TIMEOUT_SECONDS,
                dl_actor_id=resolve_case_actor_store_id(
                    canonical.client, case.id_
                ),
                active_embargo_id=embargo_id,
            )
    for label, session in replicas:
        with demo_check(
            f"{label}'s replica has EM.ACTIVE with embargo {embargo_id}"
        ):
            wait_for_case_em_state(
                session.client,
                case.id_,
                EM.ACTIVE,
                COMMIT_TIMEOUT_SECONDS,
                active_embargo_id=embargo_id,
            )


def _distinct(
    labelled: list[tuple[str, ActorSession]],
) -> list[tuple[str, ActorSession]]:
    """Keep the first label of each actor, so an owner-proposer is read once."""
    seen: dict[str, tuple[str, ActorSession]] = {}
    for label, session in labelled:
        seen.setdefault(session.actor.id_, (label, session))
    return list(seen.values())


def demo_propose_and_activate_embargo(
    reporter: ActorSession,
    coordinator: ActorSession,
    vendor: ActorSession,
    case: as_VulnerabilityCase,
    days: int = PROPOSED_EMBARGO_DAYS,
) -> None:
    """Propose an embargo as the reporter and bring it to ``EM.ACTIVE``.

    Runs the relayed propose-and-activate sequence (EP-09): the reporter posts
    ``propose-embargo``, which sends the proposal to the CASE_MANAGER; the
    vendor and the coordinator each poll their own replica for the
    ``Invite(EmbargoEvent)`` the CASE_MANAGER relays to them and post
    ``accept-embargo`` — the vendor's records its consent, the coordinator's,
    as case owner, activates the embargo.  The helper then checks every replica
    for ``EM.ACTIVE`` and the coordinator's replica for ``PEC.SIGNATORY`` on all
    three participants (DEMOMA-20-002, DEMOMA-20-009).

    Args:
        reporter: The proposer, bound to the reporter's container.
        coordinator: The case owner, bound to the coordinator's container.
        vendor: The remaining participant, bound to the vendor's container.
        case: The case the embargo is for.
        days: Length of the proposed embargo, in days.

    A failed step is recorded by ``demo_gate`` / ``demo_check`` and skips the
    steps that depend on it; ``assert_demo_success()`` surfaces it.
    """
    sessions = {
        "Reporter": reporter.with_case(case),
        "Coordinator": coordinator.with_case(case),
        "Vendor": vendor.with_case(case),
    }
    with demo_gate("Reporter's proposal reaches the CASE_MANAGER"):
        proposal = sessions["Reporter"].propose_embargo(
            end_time=_end_time(days)
        )
        embargo_id = _proposed_embargo_id(
            proposal.activity.object_, "propose-embargo"
        )
        _answer_in_owner_order(
            proposer=sessions["Reporter"],
            answerers=[("Vendor", sessions["Vendor"])],
            owner=("Coordinator", sessions["Coordinator"]),
            embargo_id=embargo_id,
            committed=lambda answerer: _await_consent_committed(
                sessions["Coordinator"], answerer, case.id_, embargo_id
            ),
        )
        _verify_embargo_active(
            list(sessions.items()),
            case,
            embargo_id,
            canonical=sessions["Coordinator"],
        )
        for label, session in sessions.items():
            with demo_check(
                f"{label} is a SIGNATORY in the Coordinator's replica"
            ):
                wait_for_participant_embargo_consent(
                    sessions["Coordinator"].client,
                    case.id_,
                    session.actor.id_,
                    embargo_id,
                    EmbargoConsentState.ACCEPTED,
                    COMMIT_TIMEOUT_SECONDS,
                )


def demo_propose_embargo_revision(
    proposing: ActorSession,
    accepting: ActorSession,
    owner: ActorSession,
    case: as_VulnerabilityCase,
    days: int = REVISED_EMBARGO_DAYS,
) -> None:
    """Revise the active embargo and bring the revision to ``EM.ACTIVE``.

    Runs the relayed revision sequence (EP-09): *proposing* posts
    ``propose-embargo-revision``, which sends the proposal to the CASE_MANAGER
    (canonical ``EM.ACTIVE`` to ``EM.REVISE``); *accepting* polls its own
    replica for the relayed ``Invite(EmbargoEvent)`` and posts
    ``accept-embargo``, which records its consent and moves no EM state;
    *owner* posts ``accept-embargo``, which as the case owner's answer
    activates the revision (canonical ``EM.REVISE`` to ``EM.ACTIVE``).  The
    helper then checks the CASE_MANAGER's canonical case and every replica for
    ``EM.ACTIVE`` with the revision as the active embargo (DEMOMA-21-002,
    DEMOMA-21-010).

    *owner* may be the same session as *proposing*; it is then never sent an
    Invite and answers its own proposal.  *accepting* must be neither.
    The owner answers only once the acceptor's answer is in
    ``accepted_embargo_ids`` at the CASE_MANAGER: a signatory's answer to a
    revision leaves its consent state unchanged (EP-09-004), but an owner that
    activates a longer revision first lapses every signatory without that id
    (EP-05-001).

    Args:
        proposing: The proposer, bound to its own container.
        accepting: A participant other than the proposer and the owner.
        owner: The case owner.
        case: The case whose embargo is revised.
        days: Length of the revised embargo, in days.

    Failures are recorded as in :func:`demo_propose_and_activate_embargo`.
    """
    if accepting.actor.id_ in (owner.actor.id_, proposing.actor.id_):
        raise ValueError(
            "accepting must be a participant other than the owner and the"
            " proposer: the CASE_MANAGER relays the revision to neither"
            " (EP-09-002)"
        )
    proposer = proposing.with_case(case)
    acceptor = accepting.with_case(case)
    deciding = owner.with_case(case)
    with demo_gate("Proposer's revision reaches the CASE_MANAGER"):
        proposal = proposer.propose_embargo_revision(end_time=_end_time(days))
        embargo_id = _proposed_embargo_id(
            proposal.activity.object_, "propose-embargo-revision"
        )
        # The replicas still read EM.ACTIVE for the embargo being revised, so
        # the revision is confirmed where it commits before anything waits on
        # EM.ACTIVE again (EDF-06-001, EDF-06-002).
        with demo_gate(
            f"CASE_MANAGER's canonical case is at EM.REVISE for {embargo_id}"
        ):
            wait_for_case_em_state(
                deciding.client,
                case.id_,
                EM.REVISE,
                COMMIT_TIMEOUT_SECONDS,
                dl_actor_id=resolve_case_actor_store_id(
                    deciding.client, case.id_
                ),
            )
            _answer_in_owner_order(
                proposer=proposer,
                answerers=[("Acceptor", acceptor)],
                owner=("Owner", deciding),
                embargo_id=embargo_id,
                committed=lambda answerer: (
                    wait_for_participant_embargo_accepted(
                        deciding.client,
                        case.id_,
                        answerer.actor.id_,
                        embargo_id,
                        COMMIT_TIMEOUT_SECONDS,
                        dl_actor_id=resolve_case_actor_store_id(
                            deciding.client, case.id_
                        ),
                    )
                ),
            )
            _verify_embargo_active(
                _distinct(
                    [
                        ("Proposer", proposer),
                        ("Acceptor", acceptor),
                        ("Owner", deciding),
                    ]
                ),
                case,
                embargo_id,
                canonical=deciding,
            )


def demo_terminate_embargo(
    terminating: ActorSession, case: as_VulnerabilityCase
) -> None:
    """Terminate the active embargo and check the CASE_MANAGER recorded it.

    *terminating* posts ``terminate-embargo`` and the helper polls the
    CASE_MANAGER's canonical case for ``EM.EXITED`` (DEMOMA-20-003,
    DEMOMA-20-011).  It asserts no other participant's consent: consent
    propagates asynchronously and belongs to the scenario's phase assertions
    (DEMOMA-20-012).

    Args:
        terminating: Any SIGNATORY participant authorized to terminate, bound
            to its own container.  The CASE_MANAGER's store is read through
            that container when it is co-hosted there, else through the
            actor's own replica (:func:`resolve_case_actor_store_id`).
        case: The case whose embargo ends.
    """
    session = terminating.with_case(case)
    with demo_step("Terminating actor ends the embargo"):
        session.terminate_embargo()
    with demo_check("CASE_MANAGER's canonical case has EM.EXITED"):
        wait_for_case_em_state(
            session.client,
            case.id_,
            EM.EXITED,
            COMMIT_TIMEOUT_SECONDS,
            dl_actor_id=resolve_case_actor_store_id(session.client, case.id_),
        )
