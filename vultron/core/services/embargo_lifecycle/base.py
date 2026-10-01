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
with, the P/X/A eligibility guard (EMB-01-002, EMB-02-002) and the EM
state-machine driver that turns a ``STRICT``/``OBSERVED`` transition request
into a resulting state.  Operation mixins in the sibling modules build on
this class; nothing here mutates the store.
"""

import logging

from transitions import MachineError

from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.embargo import pxa_is_embargo_eligible
from vultron.core.services.embargo_lifecycle.results import TransitionMode
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM, EM_Trigger, EMAdapter, create_em_machine
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

    def _drive_em_transition(
        self,
        *,
        case_id: str,
        em_before: EM,
        trigger: EM_Trigger,
        transition_mode: TransitionMode,
        fallback_dest: EM,
        actor_id: str | None = None,
    ) -> EM:
        """Drive an EM state-machine transition.

        In ``STRICT`` mode raises
        :exc:`~vultron.errors.VultronInvalidStateTransitionError` on failure.
        In ``OBSERVED`` mode logs a warning and returns *fallback_dest*
        instead of raising, enabling state-sync with a remote party.
        """
        adapter = EMAdapter(em_before)
        em_machine = create_em_machine()
        em_machine.add_model(adapter, initial=em_before)
        try:
            getattr(adapter, trigger)()
            return EM(adapter.state)
        except MachineError:
            if transition_mode == TransitionMode.STRICT:
                logger.warning(
                    "Invalid EM transition: actor '%s' cannot %s on case"
                    " '%s' (EM state '%s').",
                    actor_id,
                    trigger,
                    case_id,
                    em_before,
                )
                raise VultronInvalidStateTransitionError(  # noqa: B904  # ruff-baseline #3353
                    f"Cannot apply '{trigger}' to embargo: case '{case_id}'"
                    f" EM state '{em_before}' does not allow this transition."
                )
            logger.warning(
                "OBSERVED mode: EM transition '%s' (trigger '%s') failed"
                " for case '%s' — forcing state-sync to '%s'",
                em_before,
                trigger,
                case_id,
                fallback_dest,
            )
            return fallback_dest
