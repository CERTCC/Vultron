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

"""Shared foundation for the :class:`EmbargoLifecycle` operation mixins.

Holds the injected persistence port, the case lookup every operation starts
with, the P/X/A eligibility guard (EMB-01-002, EMB-02-002) and the embargo
register driver that applies a ``STRICT``/``OBSERVED`` register step to a case
in memory.  EM is derived from the register (ADR-0122), so the step is the
whole EM write.  Operation mixins in the sibling modules build on this class;
the only store write here is the ``UNINVITED`` consent row a proposal gives
every participant.
"""

import logging
from collections.abc import Iterator

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_register import RegisterChange
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.services.embargo_lifecycle.results import TransitionMode
from vultron.core.states.cs import CS_pxa
from vultron.core.states.embargo_register import RegisterTrigger
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)

logger = logging.getLogger(__name__)


class _LifecycleBase:
    """Persistence handle plus the guards and machine driver operations share."""

    def __init__(self, persistence: CasePersistence) -> None:
        self._persistence = persistence

    def _read_case(self, case_id: str) -> VulnerabilityCase:
        """Return the case for *case_id*, raising when it does not resolve.

        Raises:
            VultronNotFoundError: If *case_id* does not resolve to a case.
        """
        case = self._persistence.read_case(case_id)
        if case is None:
            raise VultronNotFoundError("VulnerabilityCase", case_id)
        return case

    @staticmethod
    def _assert_pxa_embargo_eligible(
        pxa_state: CS_pxa,
        case_id: str,
        operation: str,
    ) -> None:
        """Raise if the case is no longer embargo-eligible due to P/X/A.

        Per EMB-01-002 and EMB-02-002: once any of P, X, or A is set
        (i.e. ``pxa_state != CS_pxa.pxa``), no new embargo may be proposed
        or accepted.  This guard is only applied in STRICT mode.

        Raises:
            VultronInvalidStateTransitionError: When ``pxa_state != CS_pxa.pxa``.
        """
        if not pxa_is_embargo_eligible(pxa_state):
            raise VultronInvalidStateTransitionError(
                f"Cannot {operation} on case '{case_id}': public awareness,"
                f" exploit publication, or attack observation is set"
                f" (pxa_state='{pxa_state.name}')."
            )

    def _apply_register_step(
        self,
        case: VulnerabilityCase,
        changes: list[RegisterChange],
        *,
        transition_mode: TransitionMode,
        actor_id: str | None = None,
        threat_signal: bool = False,
    ) -> bool:
        """Apply one embargo register step to *case* in memory.

        In ``STRICT`` mode a refused step raises
        :exc:`~vultron.errors.VultronInvalidStateTransitionError`.  In
        ``OBSERVED`` mode — following a decision the CASE_MANAGER already
        committed — a refused step is logged and skipped, leaving the case as
        it was: the register is never forced into a state its rules refuse.

        A step that proposes an embargo also writes the consent table's new
        column: an ``UNINVITED`` row for it on every participant record,
        saved here (ADR-0122).  A participant created later gets its rows
        when it is added to the case (``VulnerabilityCase.add_participant``).

        Returns:
            ``True`` when the step was applied.
        """
        try:
            case.apply_embargo_register_step(
                changes, threat_signal=threat_signal
            )
        except VultronInvalidStateTransitionError as exc:
            if transition_mode == TransitionMode.STRICT:
                logger.warning(
                    "Refused embargo register step for actor '%s' on case"
                    " '%s': %s",
                    actor_id,
                    case.id_,
                    exc,
                )
                raise
            logger.warning(
                "OBSERVED mode: embargo register step on case '%s' refused,"
                " case left unchanged: %s",
                case.id_,
                exc,
            )
            return False
        proposed = [
            change.embargo_id
            for change in changes
            if change.trigger == RegisterTrigger.PROPOSE
        ]
        if proposed:
            for _, participant in self._each_participant(case):
                if participant.write_uninvited_rows(proposed):
                    self._persistence.save(participant)
        return True

    def _each_participant(
        self, case: VulnerabilityCase
    ) -> Iterator[tuple[str, CaseParticipant]]:
        """Yield ``(participant_id, participant)`` for every record on *case*."""
        for entry in case.case_participants:
            participant_id = _as_id(entry)
            if participant_id is None:
                continue
            participant = self._persistence.read(participant_id)
            if isinstance(participant, CaseParticipant):
                yield participant_id, participant
