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
"""

import logging

from vultron.core.services.embargo_lifecycle.proposals import (
    _ProposalOperationsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
    TransitionMode,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


class _CreationOperationsMixin(_ProposalOperationsMixin):
    """``initialize_creation_embargo``."""

    def initialize_creation_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
    ) -> EmbargoLifecycleResult:
        """Propose and activate a case's creation-time embargo in one write.

        Drives ``NONE → PROPOSED → ACTIVE`` (PROPOSE then ACCEPT) in memory,
        sets ``case.active_embargo`` to *embargo_id* and saves the case once,
        so the intermediate ``EM.PROPOSED`` is never persisted (EP-04-002).
        Every check runs before that write: the P/X/A eligibility guard
        (EMB-01-002), the read of the ``EmbargoEvent`` being activated
        (EMB-18-003) and both STRICT transitions — so any refusal leaves the
        case at ``EM.NONE`` for a redelivered proposal to finish (EP-04-012).

        The consent effects are those of ``propose_embargo`` followed by
        ``activate_embargo``: a proposing *actor_id* that is a participant
        records the id in its ``accepted_embargo_ids`` (ADR-0093), then every
        non-signatory already holding the id becomes ``SIGNATORY``
        (``_consent_at_activation``).  The id never enters
        ``proposed_embargoes``: activation decides the proposal that carried
        it, so a stale listing is discarded in the same write (EP-08-003).

        Only the case is written once.  The consent records are participant
        writes made after it, so a failure there leaves the case ``ACTIVE``
        with consent part-recorded — a post-activation failure, tracked in
        #4142 rather than repaired here.

        Args:
            case_id: ID of the ``VulnerabilityCase`` to initialize.
            embargo_id: ID of the stored ``EmbargoEvent`` to activate.
            actor_id: Optional ID of the proposing actor, for logging and the
                proposer's consent record.

        Returns:
            :class:`EmbargoLifecycleResult` for ``NONE → ACTIVE``.

        Raises:
            VultronNotFoundError: If the case or the embargo does not resolve.
            VultronValidationError: If the embargo record is not an
                ``EmbargoEvent``.
            VultronInvalidStateTransitionError: If the case is not at
                ``EM.NONE``, already has an active embargo, or any of P/X/A
                is set.
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

        self._save_activation(case, em_after=em_after, embargo_id=embargo_id)

        participant_changes: list[ParticipantPECChange] = (
            self._record_proposer_consent(case, actor_id, embargo_id)
        )
        participant_changes.extend(
            self._consent_at_activation(
                case, embargo_id=embargo_id, ends_no_later=None
            )
        )

        logger.info(
            "Actor '%s' initialized creation-time embargo '%s' on case '%s'"
            " (EM %s → %s, EP-04-002)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
        )
        return self._activation_result(
            em_before=em_before,
            em_after=em_after,
            participant_changes=participant_changes,
        )
