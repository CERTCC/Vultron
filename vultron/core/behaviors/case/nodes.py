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
Case management behavior tree nodes.

Provides condition and action nodes for the create_case workflow,
implementing idempotency guards, persistence, and outbox management
for VulnerabilityCase creation.

Per specs/behavior-tree-integration.yaml BT-07 and specs/case-management.yaml
CM-02 requirements.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import isodate  # type: ignore[import-untyped]

import py_trees
from py_trees.common import Status

from vultron.core.models.actor_config import ActorConfig
from vultron.core.models.embargo_event import VultronEmbargoEvent
from vultron.core.models.enums import VultronObjectType
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.models.protocols import CaseModel, has_outbox, is_case_model
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronCreateCaseActivity,
    VultronParticipant,
)
from vultron.core.states.em import EM, EMAdapter, create_em_machine
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.factories import add_participant_to_case_activity
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerCondition,
)
from vultron.core.behaviors.helpers import UpdateActorOutbox  # noqa: F401
from vultron.core.ports.case_persistence import (
    CasePersistence,
    CaseOutboxPersistence,
)
from vultron.core.use_cases._helpers import (
    _report_phase_status_id,
    update_participant_rm_state,
)
from vultron.core.use_cases.triggers.sync import commit_log_entry_trigger

logger = logging.getLogger(__name__)


# ============================================================================
# Condition Nodes
# ============================================================================


class CheckCaseAlreadyExists(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists in DataLayer.

    Returns SUCCESS if the case already exists (idempotency early exit).
    Returns FAILURE if the case does not exist (proceed with creation).

    Per specs/idempotency.yaml ID-04-004.
    """

    def __init__(self, case_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.read(self.case_id)
            if existing is None:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} not found, proceeding"
                )
                return Status.FAILURE

            # A case record that exists but has no participants was
            # pre-stored by the inbox endpoint as a dehydrated reference.
            # It still needs full initialisation (participant creation,
            # CaseActor setup, etc.), so return FAILURE to let the
            # CreateCaseFlow run.
            participants = getattr(existing, "case_participants", None) or []
            if not participants:
                self.logger.debug(
                    f"{self.name}: Case {self.case_id} exists but has no"
                    " participants — proceeding with initialisation"
                )
                return Status.FAILURE

            self.logger.info(
                f"{self.name}: Case {self.case_id} already exists"
                " — skipping creation (idempotent)"
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error checking case existence: {e}"
            )
            return Status.FAILURE


class CheckCaseExistsForReport(DataLayerCondition):
    """
    Check if a VulnerabilityCase already exists for the given report.

    Uses ``find_case_by_report_id`` to check whether a case linked to the
    report already exists with participants. Returns SUCCESS if so (idempotency
    early exit), FAILURE otherwise.

    Per specs/idempotency.yaml ID-04-004.
    """

    def __init__(self, report_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            existing = self.datalayer.find_case_by_report_id(self.report_id)
            if existing is None:
                self.logger.debug(
                    f"{self.name}: No case found for report {self.report_id}"
                )
                return Status.FAILURE

            # A case record that exists but has no participants was
            # pre-stored by the inbox endpoint as a dehydrated reference.
            # It still needs full initialisation, so return FAILURE.
            participants = getattr(existing, "case_participants", None) or []
            if not participants:
                self.logger.debug(
                    f"{self.name}: Case for report {self.report_id} exists"
                    " but has no participants — proceeding with initialisation"
                )
                return Status.FAILURE

            self.logger.info(
                "%s: Case %s already exists for report %s"
                " — skipping (idempotent)",
                self.name,
                existing.id_,
                self.report_id,
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error checking case existence: {e}"
            )
            return Status.FAILURE


class ValidateCaseObject(DataLayerCondition):
    """
    Validate the incoming VulnerabilityCase object has required fields.

    Returns SUCCESS if the case object passes validation.
    Returns FAILURE if required fields are missing.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        try:
            if self.case_obj is None:
                self.logger.error(f"{self.name}: case_obj is None")
                return Status.FAILURE

            if not getattr(self.case_obj, "id_", None):
                self.logger.error(f"{self.name}: Case object missing id_")
                return Status.FAILURE

            self.logger.debug(
                f"{self.name}: Case {self.case_obj.id_} passes validation"
            )
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error validating case: {e}")
            return Status.FAILURE


# ============================================================================
# Action Nodes
# ============================================================================


class PersistCase(DataLayerAction):
    """
    Persist a VulnerabilityCase to the DataLayer.

    Creates the case record in DataLayer and stores the case_id in the
    blackboard for subsequent nodes.

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            self.datalayer.save(self.case_obj)
            self.logger.info(
                f"{self.name}: Persisted VulnerabilityCase"
                f" {self.case_obj.id_}"
            )

            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = self.case_obj.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error persisting case: {e}")
            return Status.FAILURE


class CreateCaseActorNode(DataLayerAction):
    """
    Create a CaseActor (Service) for the new VulnerabilityCase.

    Each VulnerabilityCase MUST have exactly one associated CaseActor.
    The CaseActor is an ActivityStreams Service that manages case
    communications (inbox/outbox).

    Per specs/case-management.yaml CM-02-001.
    """

    def __init__(self, case_id: str, actor_id: str, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.actor_id = actor_id

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_actor = VultronCaseActor(
                name=f"CaseActor for {self.case_id}",
                attributed_to=self.actor_id,
                context=self.case_id,
            )
            try:
                self.datalayer.create(case_actor)
                self.logger.info(
                    f"{self.name}: Created CaseActor {case_actor.id_}"
                    f" for case {self.case_id}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CaseActor {case_actor.id_}"
                    f" already exists: {e}"
                )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating CaseActor: {e}")
            return Status.FAILURE


class EmitCreateCaseActivity(DataLayerAction):
    """
    Generate a CreateCaseActivity activity and persist it to the DataLayer.

    Reads case_id from the blackboard (set by PersistCase), creates a
    CreateCaseActivity activity, and stores the activity_id in the blackboard for
    UpdateActorOutbox.
    """

    def __init__(self, name: str | None = None):
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

            # Read full case to embed as object_ and derive addressees from
            # actor_participant_index, mirroring CreateCaseActivity in
            # report/nodes.py (D5-6-CASEPROP).
            case_obj = self.datalayer.read(case_id)
            if is_case_model(case_obj):
                addressees = [
                    actor_id
                    for actor_id in case_obj.actor_participant_index.keys()
                    if actor_id != self.actor_id
                ]
            else:
                addressees = []
            if addressees:
                self.logger.info(
                    f"{self.name}: Notifying addressees: {addressees}"
                )

            activity = VultronCreateCaseActivity(
                actor=self.actor_id,
                object_=case_obj if case_obj is not None else case_id,
                to=addressees if addressees else None,
            )
            try:
                self.datalayer.create(activity)
                self.logger.info(
                    f"{self.name}: Created CreateCaseActivity activity"
                    f" {activity.id_}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CreateCaseActivity activity {activity.id_}"
                    f" already exists: {e}"
                )

            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.activity_id = activity.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCaseActivity activity: {e}"
            )
            return Status.FAILURE


class SetCaseAttributedTo(DataLayerAction):
    """
    Set VulnerabilityCase.attributed_to to the receiving actor's ID.

    Must run before PersistCase so the stored case already carries the
    vendor/coordinator owner reference.

    Per specs/case-management.yaml CM-02-008.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error(f"{self.name}: actor_id not available")
            return Status.FAILURE

        self.case_obj.attributed_to = self.actor_id
        self.logger.debug(
            f"{self.name}: Set attributed_to={self.actor_id}"
            f" on case {self.case_obj.id_}"
        )
        return Status.SUCCESS


def _create_and_attach_participant(
    dl: CasePersistence,
    participant: "VultronParticipant",
    case_id: str,
    actor_id_for_index: str,
    node_logger: logging.Logger,
) -> "CaseModel | None":
    """
    Create a VultronParticipant in the DataLayer if it does not exist,
    attach it to the case, and return the **unsaved** updated case object.

    The caller is responsible for any additional case mutations (e.g.,
    ``record_event``, RM advancement) and for calling ``dl.save(case)``
    after this function returns.

    Args:
        dl: DataLayer instance for persistence.
        participant: The participant object to create and attach.
        case_id: ID of the case to attach the participant to.
        actor_id_for_index: Actor ID key for the case's
            ``actor_participant_index``.
        node_logger: Logger from the calling BT node.

    Returns:
        The updated (unsaved) case object on success, or ``None`` if the
        case was not found.
    """
    if dl.read(participant.id_) is None:
        dl.create(participant)
        node_logger.info(
            "Created CaseParticipant '%s' for actor '%s'",
            participant.id_,
            participant.attributed_to,
        )
    else:
        node_logger.debug(
            "CaseParticipant %s already exists — skipping creation",
            participant.id_,
        )

    stored_case = dl.read(case_id)
    if not is_case_model(stored_case):
        node_logger.error("Case %s not found in DataLayer", case_id)
        return None

    existing_ids = {
        p.id_ if hasattr(p, "id_") else p
        for p in stored_case.case_participants
    }
    if participant.id_ not in existing_ids:
        stored_case.case_participants.append(participant.id_)
    if (
        stored_case.actor_participant_index.get(actor_id_for_index)
        != participant.id_
    ):
        stored_case.actor_participant_index[actor_id_for_index] = (
            participant.id_
        )

    node_logger.info(
        "CaseParticipant '%s' attached to case '%s'",
        participant.id_,
        stored_case.id_,
    )
    return stored_case


class CreateCaseOwnerParticipant(DataLayerAction):
    """
    Create and persist a case-owner participant for the receiving actor,
    then add it to the case's case_participants list.

    Roles are sourced from ``actor_config.default_case_roles``
    (CFG-07-004); ``CVDRole.CASE_OWNER`` is always appended
    (BTND-05-002).  When ``actor_config`` is ``None`` the participant
    receives only the ``CASE_OWNER`` role.

    Seeds the participant with the deterministic status record for the
    given ``initial_rm_state`` (defaulting to ``RM.VALID``). When
    ``report_id`` is provided, the node first looks for an existing status
    record in the DataLayer (created by an earlier use case) and reuses it
    to avoid duplicating history. If no existing record is found, a fresh
    ``VultronParticipantStatus`` is created.

    Optionally advances the actor's RM to ACCEPTED
    (``advance_to_accepted=True``) after the participant is created — use
    this in the validate-report BT where case creation is the act of
    engaging the case.

    Must run after the case exists in the DataLayer (``PersistCase`` or
    ``CreateCaseNode``).

    Per specs/case-management.yaml CM-02-008 (SHOULD),
    specs/behavior-tree-node-design.yaml BTND-05-002 (MUST), and
    specs/configuration.yaml CFG-07-004 (MUST).
    """

    def __init__(
        self,
        actor_config: ActorConfig | None = None,
        report_id: str | None = None,
        case_obj: VultronCase | None = None,
        advance_to_accepted: bool = False,
        initial_rm_state: RM = RM.VALID,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self.actor_config = actor_config
        self.report_id = report_id
        self.case_obj = case_obj
        self.advance_to_accepted = advance_to_accepted
        self.initial_rm_state = initial_rm_state

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
            case_id = self.case_obj.id_ if self.case_obj is not None else None
            if case_id is None:
                case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(f"{self.name}: case_id not available")
                return Status.FAILURE

            # Reuse the deterministic status record for initial_rm_state
            # (if report_id is known), otherwise create a fresh one.
            initial_status: VultronParticipantStatus | None = None
            if self.report_id is not None:
                status_id = _report_phase_status_id(
                    self.actor_id,
                    self.report_id,
                    self.initial_rm_state.value,
                )
                if self.datalayer.read(status_id) is not None:
                    # A status record with this deterministic ID already
                    # exists (e.g. created by CreateReportReceivedUseCase).
                    # Reuse its ID so we don't create a duplicate.
                    initial_status = VultronParticipantStatus(
                        id_=status_id,
                        context=case_id,
                        rm_state=self.initial_rm_state,
                        attributed_to=self.actor_id,
                    )
            if initial_status is None:
                initial_status = VultronParticipantStatus(
                    context=case_id,
                    rm_state=self.initial_rm_state,
                    attributed_to=self.actor_id,
                )

            # Derive effective roles: config roles + CASE_OWNER (deduped,
            # order-preserving).
            base_roles = (
                self.actor_config.default_case_roles
                if self.actor_config is not None
                else []
            )
            effective_roles: list[CVDRole] = list(
                dict.fromkeys(base_roles + [CVDRole.CASE_OWNER])
            )

            participant = VultronParticipant(
                attributed_to=self.actor_id,
                context=case_id,
                case_roles=effective_roles,
                participant_statuses=[initial_status],
            )

            stored_case = _create_and_attach_participant(
                self.datalayer,
                participant,
                case_id,
                self.actor_id,
                self.logger,
            )
            if stored_case is None:
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            # Optionally advance the actor's RM to ACCEPTED — creating the
            # case is the act of engaging it in the validate-report BT, so
            # no separate engage-case trigger is needed.  The create-case BT
            # seeds VALID only (ADR-0013).
            if self.advance_to_accepted:
                self.datalayer.save(stored_case)
                advanced = update_participant_rm_state(
                    case_id, self.actor_id, RM.ACCEPTED, self.datalayer
                )
                if advanced:
                    self.logger.info(
                        "Owner RM: VALID → ACCEPTED for actor '%s' in case"
                        " '%s' (case creation = case engagement)",
                        self.actor_id,
                        case_id,
                    )
                else:
                    self.logger.warning(
                        "%s: Could not advance owner RM to ACCEPTED for"
                        " actor '%s' in case '%s'",
                        self.name,
                        self.actor_id,
                        case_id,
                    )
            else:
                self.datalayer.save(stored_case)

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating case-owner participant: {e}"
            )
            return Status.FAILURE


class RecordCaseCreationEvents(DataLayerAction):
    """
    Backfill pre-case events into the case event log at case creation.

    Records a trusted-timestamp event for the case creation itself.
    If the triggering activity has an ``in_reply_to`` reference (e.g. an
    originating Offer), that event is also backfilled as an
    ``"offer_received"`` entry.

    Must run after PersistCase so the case exists in the DataLayer.
    Reads ``case_id`` and optionally ``activity`` from the blackboard.

    Per specs/case-management.yaml CM-02-009.
    """

    def __init__(self, case_obj: VultronCase, name: str | None = None):
        super().__init__(name=name or self.__class__.__name__)
        self.case_obj = case_obj

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error(f"{self.name}: DataLayer not available")
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            case = self.datalayer.read(case_id)
            if not is_case_model(case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            # Backfill originating offer receipt if available.
            # The activity key is optional — the node handles its absence.
            try:
                activity = self.blackboard.get("activity")
            except KeyError:
                activity = None
            if activity is not None:
                offer_ref = getattr(activity, "in_reply_to", None)
                if offer_ref is not None:
                    offer_id = (
                        offer_ref.id_
                        if hasattr(offer_ref, "id_")
                        else str(offer_ref)
                    )
                    case.record_event(offer_id, "offer_received")
                    self.logger.info(
                        f"{self.name}: Recorded offer_received event"
                        f" for {offer_id} on case {case_id}"
                    )

            # Record the case creation event
            case.record_event(case_id, "case_created")
            self.logger.info(
                f"{self.name}: Recorded case_created event on case {case_id}"
            )

            self.datalayer.save(case)
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error recording case creation events: {e}"
            )
            return Status.FAILURE


_DEFAULT_EMBARGO_DAYS = 90


class InitializeDefaultEmbargoNode(DataLayerAction):
    """
    Create a default embargo event for the newly created case.

    Looks up the actor's EmbargoPolicy from the DataLayer to determine the
    preferred duration (defaulting to 90 days if no policy is found).
    Creates a ``VultronEmbargoEvent`` and attaches it to the case as
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

            # Determine embargo duration from stored policy (wire-layer object
            # accessed via raw dict to avoid importing the wire type).
            duration = timedelta(days=_DEFAULT_EMBARGO_DAYS)
            policies = self.datalayer.by_type(VultronObjectType.EMBARGO_POLICY)
            if policies:
                first = next(iter(policies.values()))
                duration_str = first.get(
                    "preferred_duration", f"P{_DEFAULT_EMBARGO_DAYS}D"
                )
                try:
                    parsed = isodate.parse_duration(duration_str)
                    if isinstance(parsed, timedelta):
                        duration = parsed
                    else:
                        self.logger.warning(
                            "%s: EmbargoPolicy preferred_duration %r uses"
                            " calendar units (years/months); falling back to"
                            " default %d days",
                            self.name,
                            duration_str,
                            _DEFAULT_EMBARGO_DAYS,
                        )
                except Exception:
                    self.logger.warning(
                        "%s: Could not parse EmbargoPolicy preferred_duration"
                        " %r; falling back to default %d days",
                        self.name,
                        duration_str,
                        _DEFAULT_EMBARGO_DAYS,
                    )

            end_time = datetime.now(tz=timezone.utc) + duration
            embargo = VultronEmbargoEvent(end_time=end_time, context=case_id)

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

            # Attach embargo to the case.
            stored_case = self.datalayer.read(case_id)
            if not is_case_model(stored_case):
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            if stored_case.active_embargo is None:
                stored_case.active_embargo = embargo.id_
                # Apply PROPOSE + ACCEPT atomically so em_state lands at
                # EM.ACTIVE immediately (EP-04-001, EP-04-002).  The
                # intermediate PROPOSED state is never persisted externally.
                em_machine = create_em_machine()
                em_adapter = EMAdapter(EM.NONE)
                em_machine.add_model(em_adapter, initial=EM.NONE)
                getattr(em_adapter, "propose")()  # NONE → PROPOSED
                getattr(em_adapter, "accept")()  # PROPOSED → ACTIVE
                stored_case.current_status.em_state = EM(em_adapter.state)
                stored_case.record_event(embargo.id_, "embargo_initialized")
                self.datalayer.save(stored_case)
                self.logger.info(
                    "Attached embargo '%s' to case '%s' as active_embargo"
                    " (em_state: %s)",
                    embargo.id_,
                    case_id,
                    stored_case.current_status.em_state,
                )

            # Participants learn about the embargo from VulnerabilityCase.active_embargo
            # embedded in the Create(Case) activity queued by the subsequent
            # CreateCaseActivity node. No separate Announce(embargo) is needed
            # (D5-6-EMBARGORCP, OX-03-001).

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error initializing default embargo: {e}"
            )
            return Status.FAILURE


class CreateCaseParticipantNode(DataLayerAction):
    """
    Create and persist a CaseParticipant for the given actor, then attach
    it to the case.

    Parameterized by ``actor_id`` (the actor being added as a participant)
    and ``roles`` (the CVD roles to assign).

    When ``report_id`` is supplied, the node reuses the deterministic
    report-phase ``VultronParticipantStatus`` for ``RM.ACCEPTED`` that was
    created during ``SubmitReportReceivedUseCase``, preserving engagement
    history.

    Emits ``AddParticipantToCaseActivity(object_=<CaseParticipant>)`` to
    the actor's outbox so downstream actors are notified.  Using the typed
    activity (not a bare ``VultronActivity``) satisfies MV-09-001 and
    avoids the ``VultronOutboxObjectIntegrityError`` caused by bare-string
    ``object_`` fields after dehydration.

    Must run after ``CreateCaseNode`` (so ``case_id`` is on the blackboard)
    and after ``CreateCaseOwnerParticipant``.
    """

    def __init__(
        self,
        actor_id: str,
        roles: list[CVDRole],
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_actor_id = actor_id
        self.roles = roles
        self.report_id = report_id

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

            # Reuse the report-phase RM.ACCEPTED status if available,
            # otherwise create a fresh one.
            accepted_status: VultronParticipantStatus | None = None
            if self.report_id is not None:
                accepted_status_id = _report_phase_status_id(
                    self.participant_actor_id,
                    self.report_id,
                    RM.ACCEPTED.value,
                )
                existing = self.datalayer.read(accepted_status_id)
                if existing is not None and isinstance(
                    existing, VultronParticipantStatus
                ):
                    accepted_status = existing
                else:
                    self.logger.info(
                        "%s: Creating fresh RM.ACCEPTED status for actor '%s'"
                        " (report-phase status not pre-created)",
                        self.name,
                        self.participant_actor_id,
                    )
                    accepted_status = VultronParticipantStatus(
                        id_=accepted_status_id,
                        context=self.report_id,
                        rm_state=RM.ACCEPTED,
                        attributed_to=self.participant_actor_id,
                    )
                    try:
                        self.datalayer.create(accepted_status)
                    except ValueError:
                        pass  # idempotent — already exists

            participant = VultronParticipant(
                attributed_to=self.participant_actor_id,
                context=case_id,
                case_roles=self.roles,
                participant_statuses=(
                    [accepted_status] if accepted_status is not None else []
                ),
            )

            stored_case = _create_and_attach_participant(
                self.datalayer,
                participant,
                case_id,
                self.participant_actor_id,
                self.logger,
            )
            if stored_case is None:
                self.logger.error(
                    f"{self.name}: Case {case_id} not found in DataLayer"
                )
                return Status.FAILURE

            stored_case.record_event(participant.id_, "participant_added")
            self.datalayer.save(stored_case)

            # Emit Add activity with a fully typed CaseParticipant object
            # (not a bare string ID) to satisfy MV-09-001.
            case_participant = CaseParticipant.model_validate(
                participant.model_dump(by_alias=True)
            )
            add_notification = add_participant_to_case_activity(
                participant=case_participant,
                target=case_id,
                actor=self.actor_id,
                to=[self.participant_actor_id],
            )
            try:
                self.datalayer.create(add_notification)
            except ValueError:
                pass  # idempotent

            actor_obj = self.datalayer.read(
                self.actor_id, raise_on_missing=True
            )
            if has_outbox(actor_obj):
                actor_obj.outbox.items.append(add_notification.id_)
                self.datalayer.save(actor_obj)
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                self.actor_id, add_notification.id_
            )
            self.logger.info(
                "Queued Add(CaseParticipant '%s' for actor '%s' to case '%s')"
                " activity '%s' to actor '%s' outbox",
                participant.id_,
                self.participant_actor_id,
                case_id,
                add_notification.id_,
                self.actor_id,
            )

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CaseParticipant: {e}"
            )
            return Status.FAILURE


class CommitCaseLogEntryNode(DataLayerAction):
    """
    Commit a hash-chained CaseLogEntry and fan it out to all case participants.

    Creates a :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`,
    persists it, and queues one ``Announce(CaseLogEntry)`` activity per
    participant to the actor's outbox.  The :class:`OutboxMonitor` delivers
    queued activities reactively — this node only writes to the outbox.

    ``case_id`` is resolved in order:

    1. Constructor parameter (if provided at tree-build time).
    2. ``case_id`` key in the py_trees blackboard (written by a prior node
       such as :class:`CreateCaseNode` or :class:`PersistCase`).

    If ``case_id`` cannot be resolved, the node returns ``SUCCESS`` silently
    (no-op for trees that run in a non-case context).

    ``event_type`` and ``object_id`` are derived from the ``activity``
    blackboard key (the inbound :class:`~vultron.core.models.events.base.VultronEvent`
    placed there by :class:`~vultron.core.behaviors.bridge.BTBridge`).

    Per specs/sync-log-replication.yaml SYNC-02-002, SYNC-02-003.
    """

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
    ):
        """
        Args:
            case_id: ID of the ``VulnerabilityCase`` to log against.  When
                ``None`` the node reads ``case_id`` from the blackboard.
            name: Optional display name for the node.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self._case_id or self.blackboard.get("case_id")
        except KeyError:
            case_id = self._case_id
        if not case_id:
            self.logger.debug(
                f"{self.name}: no case_id available — skipping log entry"
            )
            return Status.SUCCESS

        try:
            activity = self.blackboard.get("activity")
        except KeyError:
            activity = None
        if activity is not None:
            object_id: str = getattr(activity, "activity_id", case_id)
            semantic_type = getattr(activity, "semantic_type", None)
            event_type: str = (
                semantic_type.value
                if semantic_type is not None
                else getattr(activity, "activity_type", "case_event")
                or "case_event"
            )
        else:
            object_id = case_id
            event_type = "case_event"

        try:
            commit_log_entry_trigger(
                case_id=case_id,
                object_id=object_id,
                event_type=event_type,
                actor_id=self.actor_id,
                dl=cast(CaseOutboxPersistence, self.datalayer),
            )
            self.logger.info(
                "%s: committed log entry '%s' for case '%s'",
                self.name,
                event_type,
                case_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: failed to commit log entry for case '%s': %s",
                self.name,
                case_id,
                e,
            )
            return Status.FAILURE
