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

Provides action nodes for initializing the embargo a case is created with.
Eligibility and duration resolution live in the sibling
``embargo_resolution.py``.

The composite subtree assembling these leaf nodes is defined in the sibling
``embargo_tree.py`` module at the process-area root per BTND-07-003:

- ``InitializeDefaultEmbargoNode``

Per specs/case-management.yaml CM-02, OX-03-001 and
notes/protocol-event-cascades.md D5-6-EMBARGORCP.
"""

import logging

import isodate  # type: ignore[import-untyped]
from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id, from_now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    InitialEmbargoDuration,
)
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronError,
)

logger = logging.getLogger(__name__)


def persist_creation_time_embargo(
    datalayer: CasePersistence, embargo: EmbargoEvent, case_id: str
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
        datalayer.create(embargo)
    except VultronAlreadyExistsError:
        stored = datalayer.read(embargo.id_)
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


class CreateEmbargoEventNode(DataLayerActionWithPorts):
    """Create the initial embargo event and publish embargo_id to blackboard.

    Its duration is the ``InitialEmbargoDuration`` that
    ``ResolveEmbargoDurationNode`` resolved (EP-04-005 through EP-04-007).
    When the sender's proposal won, the event is the sender's own
    ``EmbargoEvent`` with its ``context`` rewritten from the report to the
    case — the same terms and identity the Reporter stated, now about the case
    (EP-04-004, EP-04-009).  Otherwise a fresh event is minted for the
    resolved duration.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "initial_embargo_duration": PortInformation(
            data_type=InitialEmbargoDuration, required=True
        ),
        "sender_proposed_embargo": PortInformation(
            data_type=object, required=False
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "default_embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "initial_embargo_duration": "/initial_embargo_duration",
            "sender_proposed_embargo": "/sender_proposed_embargo",
            "default_embargo_id": "/default_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.initial_embargo_duration_bb: InitialEmbargoDuration = (
            self.get_input("initial_embargo_duration")
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id not found in blackboard", self.name)
            return Status.FAILURE

        resolved = self.initial_embargo_duration_bb
        duration = resolved.duration
        sender_event = self._try_get_input("sender_proposed_embargo")
        if (
            resolved.source is EmbargoDurationSource.SENDER_PROPOSAL
            and isinstance(sender_event, EmbargoEvent)
        ):
            # The Reporter's terms carry over whole; only the subject changes
            # from the report to the case (EP-04-004).
            embargo = sender_event.with_subject(case_id)
            end_time = embargo.end_time
        else:
            end_time = from_now_utc(duration)
            embargo = EmbargoEvent(end_time=end_time, context=case_id)
        try:
            persist_creation_time_embargo(self.datalayer, embargo, case_id)
        except VultronError as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.error(self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self._set_output("default_embargo_id", embargo.id_)
        self.logger.info(
            "Initialized embargo '%s' for case '%s'"
            " (end_time: %s, duration: %s, source: %s)",
            embargo.id_,
            case_id,
            end_time.isoformat(),
            isodate.duration_isoformat(duration),
            resolved.source.value,
        )
        return Status.SUCCESS


class AdvanceEMStateToActiveNode(DataLayerActionWithPorts):
    """Advance EM state via EmbargoLifecycle propose+accept sequence."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "default_embargo_id": PortInformation(data_type=str, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "default_embargo_initialized": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_id": "/default_embargo_id",
            "default_embargo_initialized": "/default_embargo_initialized",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.default_embargo_id_bb: str = self.get_input("default_embargo_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self.case_id_bb
        embargo_id = self.default_embargo_id_bb
        if not isinstance(case_id, str) or not isinstance(embargo_id, str):
            self.logger.error(
                "%s: case_id/default_embargo_id not found in blackboard",
                self.name,
            )
            return Status.FAILURE

        stored_case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        if _as_id(stored_case.active_embargo) is not None:
            self.logger.debug(
                "%s: Case '%s' already has active_embargo '%s' — skipping EM advance",
                self.name,
                case_id,
                _as_id(stored_case.active_embargo),
            )
            self._set_output("default_embargo_initialized", False)
            return Status.SUCCESS

        # The creation-time embargo is the owner's to set: either the owner
        # creates the case itself, or the CASE_MANAGER creates it on the
        # owner's behalf from a proposal (CP-09-001, CP-09-003) — the case is
        # then attributed to the owner while the CASE_MANAGER runs this tree.
        owner_actor_id = _as_id(stored_case.attributed_to)
        if self.actor_id != owner_actor_id and self.actor_id != (
            resolve_case_manager_id(stored_case, self.datalayer)
        ):
            self.feedback_message = (
                f"actor '{self.actor_id}' is neither case owner"
                f" '{owner_actor_id}' nor the CASE_MANAGER of case '{case_id}'"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        status = self._propose_with_em_io(case_id, embargo_id)
        if status != Status.SUCCESS:
            return status

        self._set_output("default_embargo_initialized", True)
        return Status.SUCCESS

    def _propose_with_em_io(self, case_id: str, embargo_id: str) -> Status:
        """Run propose_embargo via EmbargoLifecycle service."""
        assert (
            self.datalayer is not None
        )  # caller guards; here for type narrowing
        assert self.actor_id is not None

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            lifecycle.propose_embargo(
                case_id=case_id,
                embargo_id=embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.STRICT,
            )
        except VultronError as exc:
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: Failed to propose embargo '%s' for case '%s': %s",
                self.name,
                embargo_id,
                case_id,
                exc,
            )
            return Status.FAILURE

        return Status.SUCCESS


class AttachEmbargoToCaseNode(DataLayerActionWithPorts):
    """Ensure case.active_embargo references the initialized embargo event."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "default_embargo_initialized": PortInformation(
            data_type=object, required=True
        ),
        "default_embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_initialized": "/default_embargo_initialized",
            "default_embargo_id": "/default_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.bb_case_id: str = self.get_input("case_id")
        self.bb_default_embargo_id: str = self.get_input("default_embargo_id")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.bb_case_id
        embargo_id = self.bb_default_embargo_id

        stored_case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        active_embargo_id = _as_id(stored_case.active_embargo)
        if active_embargo_id is None:
            lifecycle = EmbargoLifecycle(persistence=self.datalayer)
            try:
                lifecycle.activate_embargo(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    actor_id=self.actor_id,
                )
            except VultronError as exc:
                self.feedback_message = str(exc)
                self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                    "%s: Failed to activate embargo '%s' on case '%s': %s",
                    self.name,
                    embargo_id,
                    case_id,
                    exc,
                )
                return Status.FAILURE
            self.logger.info(
                "Attached embargo '%s' to case '%s' as active_embargo",
                embargo_id,
                case_id,
            )
            return Status.SUCCESS

        if active_embargo_id != embargo_id:
            self.logger.debug(
                "%s: Keeping existing active_embargo '%s' for case '%s'"
                " (new embargo '%s' left unattached)",
                self.name,
                active_embargo_id,
                case_id,
                embargo_id,
            )
        return Status.SUCCESS


class SeedOwnerAsSignatoryNode(DataLayerActionWithPorts):
    """Seed the case-owner participant as SIGNATORY (CM-14-003).

    The owner is read from the case — ``attributed_to``, the CASE_OWNER
    (CM-02-008, CP-09-001) — never from the actor running the tree.  On the
    CASE_MANAGER's creation path those differ: the CASE_MANAGER runs the tree
    and the proposing actor owns the case.  Keying on the executing actor
    seeds nobody there, so the owner comes from the case and every creation
    path shares this one seeding node.

    The owner's participant record is created before the embargo is
    initialized (CM-14-002), so a missing record — or a case naming no owner
    — is a broken precondition: the node fails rather than report a seed it
    did not make (ARCH-15).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "default_embargo_initialized": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "default_embargo_initialized": "/default_embargo_initialized",
        }

    def initialise(self) -> None:
        super().initialise()
        self.bb_case_id: str = self.get_input("case_id")
        self.embargo_initialized = self.get_input(
            "default_embargo_initialized"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self.bb_case_id
        embargo_initialized = self.embargo_initialized
        if embargo_initialized is False:
            return Status.SUCCESS

        stored_case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        owner_id = _as_id(stored_case.attributed_to)
        participant_id = (
            stored_case.actor_participant_index.get(owner_id)
            if owner_id is not None
            else None
        )
        participant = (
            self.datalayer.read(participant_id, raise_on_missing=False)
            if participant_id
            else None
        )
        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"case owner '{owner_id}' has no participant record in case"
                f" '{case_id}' — cannot seed SIGNATORY (CM-14-002 creates it"
                " first)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        embargo_id = _as_id(stored_case.active_embargo)
        if participant.embargo_consent_state not in (
            PEC.SIGNATORY,
            PEC.DECLINED,
        ):
            participant.apply_pec_transition(PEC_Trigger.ACCEPT)
        if embargo_id:
            participant.add_accepted_embargo(embargo_id)
        self.datalayer.save(participant)
        self.logger.info(
            "Seeded case-owner participant '%s' (actor '%s') as SIGNATORY"
            " for embargo in case '%s' (CM-14-003)",
            participant_id,
            owner_id,
            case_id,
        )
        return Status.SUCCESS
