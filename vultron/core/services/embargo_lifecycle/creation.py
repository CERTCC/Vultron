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

from vultron.core.models.dimensions import EmDimension
from vultron.core.services.embargo_lifecycle.pec import (
    _PecEffectsMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantPECChange,
    TransitionMode,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.errors import VultronInvalidStateTransitionError

logger = logging.getLogger(__name__)


class _CreationOperationsMixin(_PecEffectsMixin):
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
        ``proposed_embargoes``: activation would discard it at once
        (EP-08-003).

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
                ``EM.NONE`` or any of P/X/A is set.
        """
        case = self._read_case(case_id)
        em_before = case.current_status.em.state
        self._assert_pxa_embargo_eligible(
            case.current_status.pxa.state, case_id, "initialize embargo"
        )
        if em_before is not EM.NONE:
            # PROPOSE then ACCEPT is legal from more than NONE (ACTIVE →
            # REVISE → ACTIVE, for one), so the machine alone would not refuse
            # a case that has already left NONE; creation is only from NONE.
            raise VultronInvalidStateTransitionError(
                f"Cannot initialize the creation-time embargo on case"
                f" '{case_id}': EM state '{em_before}' is not NONE"
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

        case.current_status.em = EmDimension(state=em_after)
        case.set_embargo(embargo_id)
        self._persistence.save(case)

        participant_changes: list[ParticipantPECChange] = []
        if actor_id is not None and actor_id in case.actor_participant_index:
            participant_changes.extend(
                self._record_actor_pec_acceptance(
                    case, actor_id, embargo_id, advance=False
                )
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
        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=True,
            case_embargo_changed=True,
            pec_reset=False,
            participant_changes=participant_changes,
        )
