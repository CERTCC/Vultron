#!/usr/bin/env python

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

"""
Embargo management action nodes and helpers for case behavior trees.

Provides helpers and action nodes for initializing default embargo events
during case creation.

Per specs/case-management.yaml CM-02, OX-03-001 and
notes/protocol-event-cascades.md D5-6-EMBARGORCP.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import isodate  # type: ignore[import-untyped]

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.protocols import CaseModel, is_case_model
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.em import EM, EMAdapter, create_em_machine
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases._helpers import _as_id

logger = logging.getLogger(__name__)

_DEFAULT_EMBARGO_DAYS = 90


# ============================================================================
# Embargo helpers
# ============================================================================


def _preferred_embargo_duration(
    dl: CasePersistence, node_name: str, node_logger: logging.Logger
) -> timedelta:
    duration = timedelta(days=_DEFAULT_EMBARGO_DAYS)
    policies = list(dl.list_objects(VultronObjectType.EMBARGO_POLICY))
    if not policies:
        return duration

    preferred = getattr(policies[0], "preferred_duration", None)
    if isinstance(preferred, timedelta):
        return preferred

    node_logger.warning(
        "%s: EmbargoPolicy preferred_duration %r is not a timedelta; "
        "falling back to default %d days",
        node_name,
        preferred,
        _DEFAULT_EMBARGO_DAYS,
    )
    return duration


def _activate_default_embargo(stored_case: CaseModel, embargo_id: str) -> None:
    stored_case.active_embargo = embargo_id
    em_machine = create_em_machine()
    em_adapter = EMAdapter(EM.NONE)
    em_machine.add_model(em_adapter, initial=EM.NONE)
    getattr(em_adapter, "propose")()
    getattr(em_adapter, "accept")()
    stored_case.current_status.em_state = EM(em_adapter.state)
    stored_case.record_event(embargo_id, "embargo_initialized")


# ============================================================================
# Action Nodes
# ============================================================================


class InitializeDefaultEmbargoNode(DataLayerAction):
    """
    Create a default embargo event for the newly created case.

    Looks up the actor's EmbargoPolicy from the DataLayer to determine the
    preferred duration (defaulting to 90 days if no policy is found).
    Creates a ``EmbargoEvent`` and attaches it to the case as
    ``active_embargo``.

    Participants learn about the embargo from ``VulnerabilityCase.active_embargo``
    embedded in the ``Create(Case)`` activity queued by ``CreateCaseActivity``
    (the subsequent node in the validate-report BT sequence). A separate
    ``Announce(embargo)`` is therefore redundant and is not emitted here.

    Must run after CreateCaseNode so case_id is available in the blackboard.

    Per specs/case-management.yaml CM-02, OX-03-001, and
    notes/protocol-event-cascades.md D5-6-EMBARGORCP.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            duration = _preferred_embargo_duration(
                self.datalayer, self.name, self.logger
            )
            end_time = datetime.now(tz=timezone.utc) + duration
            embargo = EmbargoEvent(end_time=end_time, context=case_id)

            try:
                self.datalayer.create(embargo)
            except ValueError:
                self.logger.debug(
                    "%s: Embargo %s already exists — skipping creation",
                    self.name,
                    embargo.id_,
                )

            self.logger.info(
                "Initialized default embargo '%s' for case '%s'"
                " (end_time: %s, duration: %s)",
                embargo.id_,
                case_id,
                end_time.isoformat(),
                isodate.duration_isoformat(duration),
            )

            stored_case = self.datalayer.read(case_id)
            if not is_case_model(stored_case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            if stored_case.active_embargo is None:
                _activate_default_embargo(stored_case, embargo.id_)
                self.datalayer.save(stored_case)
                self.logger.info(
                    "Attached embargo '%s' to case '%s' as active_embargo"
                    " (em_state: %s)",
                    embargo.id_,
                    case_id,
                    stored_case.current_status.em_state,
                )
                self._seed_owner_as_signatory(stored_case, case_id)

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error initializing default embargo: {e}"
            )
            return Status.FAILURE

    def _seed_owner_as_signatory(
        self, stored_case: "CaseModel", case_id: str
    ) -> None:
        """Seed the case-owner participant as SIGNATORY (CM-14-003).

        The owner created the embargo, so a separate accept step is
        paradoxical.  This method reads the owner participant from the
        DataLayer and sets ``embargo_consent_state`` to ``PEC.SIGNATORY``
        directly, bypassing the INVITE step.
        """
        if self.datalayer is None or self.actor_id is None:
            return
        participant_id = stored_case.actor_participant_index.get(self.actor_id)
        if not participant_id:
            self.logger.warning(
                "%s: No participant found for owner '%s' in case '%s'"
                " — cannot seed SIGNATORY",
                self.name,
                self.actor_id,
                case_id,
            )
            return
        participant = self.datalayer.read(participant_id)
        if participant is None or not hasattr(
            participant, "embargo_consent_state"
        ):
            self.logger.warning(
                "%s: Participant '%s' not found or lacks embargo_consent_state"
                " — cannot seed SIGNATORY",
                self.name,
                participant_id,
            )
            return
        embargo_id = _as_id(stored_case.active_embargo)
        cast(Any, participant).embargo_consent_state = PEC.SIGNATORY
        if (
            embargo_id
            and embargo_id not in cast(Any, participant).accepted_embargo_ids
        ):
            cast(Any, participant).accepted_embargo_ids.append(embargo_id)
        self.datalayer.save(participant)
        self.logger.info(
            "Seeded case-owner participant '%s' (actor '%s') as SIGNATORY"
            " for embargo in case '%s' (CM-14-003)",
            participant_id,
            self.actor_id,
            case_id,
        )
