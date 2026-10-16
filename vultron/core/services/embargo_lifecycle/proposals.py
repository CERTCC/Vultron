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

"""Proposal-phase register operations: ``propose_embargo`` and
``check_abandonable``.

A proposal (first or revision) adds a ``PROPOSED`` entry to the case's
embargo register and records the proposer's own consent to the terms it
proposed; it changes nobody else's consent (EP-05-002).  Once the case is
public, exploited or attacked while no embargo is in force, the proposals are
cancelled rather than answered (EMB-16-001, ADR-0122): the CASE_MANAGER checks
the abandonment here, then commits and copies each cancel (ADR-0124).  Each participant's
answer to a proposal and the case owner's decision on it live in
``answers.py``, ``consent.py`` and ``activation.py``.
"""

import logging

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_register import (
    RegisterChange,
    proposal_changes,
)
from vultron.core.services.embargo_lifecycle.pec_activation import (
    _PecActivationMixin,
)
from vultron.core.services.embargo_lifecycle.results import (
    EmbargoLifecycleResult,
    ParticipantConsentChange,
    TransitionMode,
)
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
)
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


def _assert_abandonable(
    case: VulnerabilityCase, embargo_ids: list[str]
) -> None:
    """Raise unless the ``STRICT`` abandonment of *embargo_ids* is licensed.

    Every id must be an open proposal and no embargo may be in force: with
    one in force the threat signal terminates it instead (ADR-0122).  The
    P/X/A signal that licenses the abandonment is the caller's to detect
    (EMB-16-001): it may arrive in a participant's status before the case's
    own P/X/A moves, so the case's P/X/A is not checked here.
    """
    unknown = [i for i in embargo_ids if i not in case.proposed_embargo_ids]
    if not embargo_ids or unknown:
        raise VultronValidationError(
            f"Cannot abandon embargo proposals {unknown or embargo_ids}"
            f" on case '{case.id_}': not open proposals of the case."
        )
    if case.active_embargo_id is not None:
        raise VultronInvalidStateTransitionError(
            f"Cannot abandon embargo proposals on case '{case.id_}':"
            f" embargo '{case.active_embargo_id}' is in force"
            f" (EM '{case.em_state}')."
        )


def _cancel_changes(
    case: VulnerabilityCase, embargo_ids: list[str]
) -> list[RegisterChange]:
    """The register step that cancels each of *embargo_ids* still open."""
    open_ids = set(case.proposed_embargo_ids)
    return [
        RegisterChange(embargo_id=embargo_id, trigger=RegisterTrigger.CANCEL)
        for embargo_id in dict.fromkeys(embargo_ids)
        if embargo_id in open_ids
    ]


class _ProposalOperationsMixin(_PecActivationMixin):
    """``propose_embargo`` and ``check_abandonable``."""

    def propose_embargo(
        self,
        *,
        case_id: str,
        embargo_id: str,
        actor_id: str | None = None,
        transition_mode: TransitionMode = TransitionMode.STRICT,
    ) -> EmbargoLifecycleResult:
        """Propose or counter-propose an embargo on a case.

        Adds a ``PROPOSED`` register entry for *embargo_id*, so EM derives
        ``PROPOSED`` (no embargo in force) or ``REVISE`` (a revision of the
        embargo in force).  Proposing an embargo that is already an open
        proposal is idempotent; one the register has already decided, or a
        proposal once the case's embargo has ended, is refused in
        ``STRICT`` mode and skipped in ``OBSERVED`` mode.

        A proposal changes **no one's consent to the embargo in force**
        (EP-05-002, ADR-0093): while a revision is merely proposed the prior
        embargo is still in force and every signatory to it stays one.
        Carry-over to a shorter revision happens only when the owner activates
        it (``accept_embargo_invite`` / ``activate_embargo``, EP-05-001).
        Proposing terms is consenting to them, so when *actor_id* is a
        participant of the case its row for the proposed embargo is marked
        ``AGREED`` (MSM-07-005).

        The ``EmbargoEvent`` identified by *embargo_id* MUST already exist in
        the DataLayer before this method is called; the caller is responsible
        for creating it.

        Args:
            case_id: ID of the :class:`~...VulnerabilityCase` to update.
            embargo_id: ID of the pre-existing ``EmbargoEvent`` being proposed.
            actor_id: Optional ID of the proposing actor.  Used for logging and,
                when it names a case participant, to record the proposer's
                consent to the proposed terms; there is no ownership gate.
            transition_mode: ``STRICT`` (default) refuses a proposal the
                register refuses, or one made once any of P/X/A is set.
                ``OBSERVED`` skips a refused proposal instead.

        Returns:
            :class:`EmbargoLifecycleResult` describing what changed;
            ``participant_changes`` is always empty.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronInvalidStateTransitionError: If the register refuses the
                proposal (``STRICT`` mode only), or if any of P/X/A is set on
                the case (``STRICT`` mode only, per EMB-01-002).
        """
        case = self._read_case(case_id)
        em_before = case.em_state

        if transition_mode == TransitionMode.STRICT:
            self._assert_pxa_embargo_eligible(
                case.current_status.pxa.state,
                case_id,
                "propose embargo",
            )

        entry = case.embargo_register_entry(embargo_id)
        if entry is None:
            case_mutated = self._apply_register_step(
                case,
                proposal_changes(embargo_id),
                transition_mode=transition_mode,
                actor_id=actor_id,
            )
            if not case_mutated:
                # OBSERVED: the register refused the proposal, so there is no
                # entry and no row for the proposer to agree on.
                return self._unchanged_result(em_before)
        elif entry.status == EmbargoRegisterStatus.PROPOSED:
            case_mutated = False
        elif transition_mode == TransitionMode.STRICT:
            raise VultronInvalidStateTransitionError(
                f"Cannot propose embargo '{embargo_id}' on case '{case_id}':"
                f" its register entry is already {entry.status}."
            )
        else:
            logger.warning(
                "OBSERVED mode: embargo '%s' on case '%s' is already %s;"
                " proposal skipped",
                embargo_id,
                case_id,
                entry.status,
            )
            return self._unchanged_result(em_before)

        if case_mutated:
            self._persistence.save(case)

        # Proposing B is consent to B (ADR-0093).
        self._record_proposer_consent(case, actor_id, embargo_id)

        em_after = case.em_state
        logger.info(
            "Actor '%s' proposed embargo '%s' on case '%s' (EM %s → %s%s)",
            actor_id,
            embargo_id,
            case_id,
            em_before,
            em_after,
            "" if case_mutated else ", already proposed",
        )

        return EmbargoLifecycleResult(
            em_before=em_before,
            em_after=em_after,
            case_changed=case_mutated,
            case_embargo_changed=False,
            participant_changes=[],
        )

    def check_abandonable(
        self, *, case_id: str, embargo_ids: list[str]
    ) -> None:
        """Raise unless a ``STRICT`` abandonment of *embargo_ids* would apply.

        Writes nothing.  A caller that commits the abandonment's entries
        before it writes the abandonment checks here first, so no entry is
        committed for an abandonment the case then refuses (CLP-07-013).
        The check is the write itself, on a copy of the case: the same
        licence check, then one cancel step per proposal in the order the
        caller applies them, so the register's own rules are checked too.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
            VultronValidationError: An id is not an open proposal of the
                case, or *embargo_ids* is empty.
            VultronInvalidStateTransitionError: An embargo is in force, or
                the register refuses a cancel step.
        """
        case = self._read_case(case_id)
        _assert_abandonable(case, embargo_ids)
        trial = case.model_copy(deep=True)
        for embargo_id in dict.fromkeys(embargo_ids):
            trial.apply_embargo_register_step(
                _cancel_changes(trial, [embargo_id]), threat_signal=True
            )

    def _record_proposer_consent(
        self,
        case: VulnerabilityCase,
        actor_id: str | None,
        embargo_id: str,
    ) -> list[ParticipantConsentChange]:
        """Record that proposing *embargo_id* is *actor_id*'s consent to it.

        The proposer's row for *embargo_id* is marked ``AGREED`` — only that
        row, so its consent to the embargo in force is untouched (ADR-0093).
        A proposer with no participant record (the case-creation default, for
        one) has no consent to record.
        """
        if actor_id is None or actor_id not in case.actor_participant_index:
            return []
        return self._record_actor_acceptance(case, actor_id, embargo_id)
