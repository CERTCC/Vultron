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

"""Creation-time EM operation: ``initialize_creation_embargo``.

At case creation the CASE_OWNER's published default (or the terms the sender
proposed) is proposed and accepted in one step: the PROPOSE and ACCEPT
triggers are applied together and only ``EM.ACTIVE`` is ever persisted
(EP-04-002).  Running ``propose_embargo`` and then ``activate_embargo`` would
save the case at ``EM.PROPOSED`` in between, and a failure there left it
stranded, because the once-per-case guard reads any state but ``NONE`` as
"already initialized" (EP-04-012, #4123).

What follows activation — the consent records, the owner's SIGNATORY seed
(CM-14-003) and a contested creation's pending revision (EP-04-003) — is
committed with it, in one ``save_many``.  Written after the case was saved
``ACTIVE``, a failure there left the owner unseeded or the revision
unregistered, and the same guard then refused the rerun that would have
finished them (#4142).
"""

import logging

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle.proposals import (
    _ProposalOperationsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
    TransitionMode,
)
from vultron.core.services.embargo_lifecycle.staged_persistence import (
    StagedCasePersistence,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)

logger = logging.getLogger(__name__)


def persist_creation_time_embargo(
    persistence: CasePersistence, embargo: EmbargoEvent, case_id: str
) -> None:
    """Store *embargo* for *case_id*, refusing a stored twin that is not it.

    Before #3392 every creation-time ``EmbargoEvent`` carried a freshly minted
    id, so ``VultronAlreadyExistsError`` could only mean a replay of this same
    write.  The Reporter's own event now arrives under the Reporter's id, and
    an id is a sender-supplied value: when the store already holds it, the
    stored object must be *this* embargo — about this case, ending when this
    one ends — or the case would be bound to someone else's terms while
    shortest-wins compared the terms the sender stated.

    Raises:
        VultronError: when the stored twin is not an ``EmbargoEvent`` about
            *case_id* with the same ``end_time``.
    """
    try:
        persistence.create(embargo)
    except VultronAlreadyExistsError:
        stored = persistence.read(embargo.id_)
        if (
            not isinstance(stored, EmbargoEvent)
            or stored.context != case_id
            or stored.end_time != embargo.end_time
        ):
            raise VultronError(  # noqa: B904  # ruff-baseline #3353
                f"embargo id {embargo.id_!r} is already held by a different"
                f" object ({type(stored).__name__}, context"
                f" {getattr(stored, 'context', None)!r}); refusing to bind"
                f" case {case_id!r} to it (EP-04-004)"
            )
        logger.debug(
            "Embargo %s already stored for case %s — skipping creation",
            embargo.id_,
            case_id,
        )


class _CreationOperationsMixin(_ProposalOperationsMixin):
    """``initialize_creation_embargo``."""

    def initialize_creation_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        revision: EmbargoEvent | None = None,
    ) -> EmbargoLifecycleResult:
        """Initialize a case's creation-time embargo in one commit.

        Drives ``NONE → PROPOSED → ACTIVE`` (PROPOSE then ACCEPT) in memory
        and sets ``case.active_embargo`` to *embargo_id*, so the intermediate
        ``EM.PROPOSED`` is never persisted (EP-04-002).  Every check runs
        before anything is written: the P/X/A eligibility guard (EMB-01-002),
        the case owner's participant record (CM-14-002), the read of the
        ``EmbargoEvent`` being activated (EMB-18-003) and both STRICT
        transitions.

        The consent effects are those of ``propose_embargo`` followed by
        ``activate_embargo``: a proposing *actor_id* that is a participant
        records the id in its ``accepted_embargo_ids`` (ADR-0093), then every
        non-signatory already holding the id becomes ``SIGNATORY``
        (``_consent_at_activation``).  The id never enters
        ``proposed_embargoes``: activation decides the proposal that carried
        it, so a stale listing is discarded in the same write (EP-08-003).
        The case owner — ``attributed_to``, never the executing actor, which
        on the CASE_MANAGER's creation path is someone else — is then seeded
        ``SIGNATORY`` of the embargo it set (CM-14-003).

        A *revision* is the longer creation-time proposal that lost
        shortest-wins (EP-04-003).  It is stored and proposed through
        ``propose_embargo`` (``ACTIVE → REVISE``, EMB-18-001) on behalf of
        *actor_id*.

        All of it is staged and committed through one ``save_many``, so any
        refusal or fault leaves the case at ``EM.NONE`` with nothing else
        written, for a redelivered proposal to finish (EP-04-012, #4142).

        Args:
            case_id: ID of the ``VulnerabilityCase`` to initialize.
            embargo_id: ID of the stored ``EmbargoEvent`` to activate.
            actor_id: Optional ID of the proposing actor, for logging and the
                proposer's consent record.
            revision: The losing creation-time proposal to register as a
                pending revision, or ``None`` when there was no contest.

        Returns:
            :class:`EmbargoLifecycleResult` from ``NONE`` to the state the
            case was committed at: ``ACTIVE``, or ``REVISE`` with a revision.

        Raises:
            VultronNotFoundError: If the case or the embargo does not
                resolve, or the case owner has no participant record.
            VultronValidationError: If the embargo record is not an
                ``EmbargoEvent``.
            VultronInvalidStateTransitionError: If the case is not at
                ``EM.NONE``, already has an active embargo, or any of P/X/A
                is set.
            VultronError: If *revision*'s id is held by a different object
                (``persist_creation_time_embargo``).
        """
        case = self._read_case(case_id)
        em_before = case.current_status.em.state
        self._assert_pxa_embargo_eligible(
            case.current_status.pxa.state, case_id, "initialize embargo"
        )
        if em_before is not EM.NONE or case.active_embargo_id is not None:
            # PROPOSE then ACCEPT is legal from more than NONE (ACTIVE →
            # REVISE → ACTIVE, for one), so the machine alone would not refuse
            # a case that has already left NONE; creation is only from NONE,
            # and never replaces an attached embargo (CSB-16: the service
            # checks its own preconditions, not the node ahead of it).
            raise VultronInvalidStateTransitionError(
                f"Cannot initialize the creation-time embargo on case"
                f" '{case_id}': EM state '{em_before}' is not NONE or an"
                f" embargo ('{case.active_embargo_id}') is already attached"
                " (EP-04-012)."
            )
        owner_id = self._owner_with_participant(case)
        self._activation_arm(
            previous_embargo_id=None, activated_embargo_id=embargo_id
        )
        em_proposed = self._drive_em_transition(
            case_id=case_id,
            em_before=em_before,
            trigger=EM_Trigger.PROPOSE,
            transition_mode=TransitionMode.STRICT,
            fallback_dest=EM.PROPOSED,
            actor_id=actor_id,
        )
        em_after = self._drive_em_transition(
            case_id=case_id,
            em_before=em_proposed,
            trigger=EM_Trigger.ACCEPT,
            transition_mode=TransitionMode.STRICT,
            fallback_dest=EM.ACTIVE,
            actor_id=actor_id,
        )

        # The shared helpers below save as they go and re-read what an
        # earlier one saved, so they run against a staging store whose
        # writes reach ``self._persistence`` together, at the flush.
        staged = StagedCasePersistence(self._persistence)
        work = type(self)(persistence=staged)
        work._save_activation(case, em_after=em_after, embargo_id=embargo_id)
        participant_changes: list[ParticipantPECChange] = (
            work._record_proposer_consent(case, actor_id, embargo_id)
        )
        participant_changes.extend(
            work._consent_at_activation(
                case, embargo_id=embargo_id, ends_no_later=None
            )
        )
        # CM-14-003: the owner set these terms, so it is their signatory.
        participant_changes.extend(
            work._record_actor_pec_acceptance(case, owner_id, embargo_id)
        )
        if revision is not None:
            persist_creation_time_embargo(staged, revision, case_id)
            em_after = work.propose_embargo(
                case_id=case_id, embargo_id=revision.id_, actor_id=actor_id
            ).em_after
        staged.flush()

        logger.info(
            "Actor '%s' initialized creation-time embargo '%s' on case '%s'"
            " (EM %s → %s, EP-04-002; revision %s, EP-04-003)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
            revision.id_ if revision is not None else None,
        )
        return self._activation_result(
            em_before=em_before,
            em_after=em_after,
            participant_changes=participant_changes,
        )

    def _owner_with_participant(self, case: VulnerabilityCase) -> str:
        """Return the id of *case*'s owner, which must hold a participant.

        The owner's participant record is created before the embargo is
        initialized (CM-14-002), so a case naming no owner, or an owner with
        no record, is a broken precondition: refused before anything is
        written, rather than an activation reported with no seed (ARCH-15).

        Raises:
            VultronNotFoundError: If the owner or its record does not resolve.
        """
        owner_id = _as_id(case.attributed_to)
        if (
            owner_id is None
            or self._participant_for_actor(case, owner_id, "owner seed")
            is None
        ):
            raise VultronNotFoundError(
                f"CaseParticipant of case '{case.id_}' for owner",
                str(owner_id),
            )
        return owner_id
