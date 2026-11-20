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

"""Embargo removal and teardown nodes."""

from datetime import datetime
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
    optional_act_value,
)
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    EMBARGO_ID,
    TERMINATED_AT,
)
from vultron.core.behaviors.embargo.copy_commit import (
    read_embargo_case_file,
    save_case_file,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.embargo.nodes.emit import (
    _SendEmbargoActivityForCaseKey,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.narrative_log import log_em_transition
from vultron.core.behaviors.node_logger import fail_with_reason
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
)
from vultron.core.models._helpers import parse_published
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
    apply_embargo_change,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.recipients import case_content_recipients
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle import (
    decide_termination,
    termination_timing_violations,
)
from vultron.core.states.em import EM
from vultron.errors import (
    BtNodePreconditionError,
    VultronEntryRefusedError,
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
)


class ClearActiveEmbargoNode(DataLayerActionWithPorts, StateWriteCapable):
    """Terminate *embargo_id* if it is the embargo in force; EM → ``EXITED``.

    The receive-side effect of a ``Remove(EmbargoEvent)`` whose entry intake
    has already committed: the CASE_MANAGER's arm, and the arm of a paused
    signatory the ledger no longer reaches (CM-31-010).  The ``TERMINATE``
    step it applies goes through the one apply function
    (:func:`~vultron.core.models.embargo_apply.apply_embargo_change`,
    ADR-0124): the ``ACTIVE`` entry is ``TERMINATED`` recording
    *termination* and every open proposal is ``CANCELLED`` in the same step
    (EP-08-004, ADR-0122), in one save.  For a received ``Remove``,
    *termination* is the cause its ``terminationCause`` carries, claimed at
    its ``published`` time (*terminated_at*); an ``END_TIME_REACHED`` claimed
    before the embargo's end time is refused: FAILURE, nothing written.

    It ends the embargo the ``Remove`` names and no other.  An EM already
    ``EXITED`` is an idempotent no-op, and a named embargo that is not the
    one in force changes nothing (ADR-0122); both return SUCCESS, and
    :attr:`applied` tells a caller which happened.

    The case is read from ``/case_id`` and *embargo_id* from
    ``/embargo_id`` (BTND-01-008); *terminated_at* from ``/terminated_at``,
    which a ``Remove`` that claims no time leaves unset.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **act_key_ports(CASE_ID, EMBARGO_ID, TERMINATED_AT),
    }

    def __init__(
        self,
        termination: EmbargoTermination,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._termination = termination
        #: True only when this tick terminated an embargo.
        self.applied = False
        #: True when this tick's termination was refused (ADR-0122).
        self.refused = False

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(CASE_ID, EMBARGO_ID, TERMINATED_AT)

    def initialise(self) -> None:
        super().initialise()
        self.case_id: str = act_value(self, CASE_ID, str)
        self._embargo_id: str = act_value(self, EMBARGO_ID, str)
        self._terminated_at = optional_act_value(self, TERMINATED_AT, datetime)

    def _refuse(self, exc: VultronError) -> Status:
        self.refused = True
        return fail_with_reason(self, str(exc))

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        dl = cast(CasePersistence, self.datalayer)

        try:
            current_em = read_case_em_state(dl, self.case_id)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            return Status.FAILURE

        if current_em == EM.EXITED:
            self.feedback_message = (
                f"Case '{self.case_id}' EM already EXITED — idempotent no-op"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        before = read_embargo_case_file(dl, self.case_id)
        if before.case.active_embargo_id != self._embargo_id:
            self.feedback_message = (
                f"Embargo '{self._embargo_id}' is not the one in force on"
                f" case '{self.case_id}' (EM {current_em}) — teardown skipped"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        try:
            step = decide_termination(
                dl, before.case, self._termination, self._terminated_at
            )
            after = apply_embargo_change(before, step)
        except (
            VultronInvalidStateTransitionError,
            VultronEntryRefusedError,
        ) as exc:
            return self._refuse(exc)
        except VultronNotFoundError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        save_case_file(dl, before, after)

        em_after = after.case.em_state
        self.applied = True
        self.feedback_message = (
            f"Cleared active embargo on case '{self.case_id}'"
            f" (EM {current_em} → {em_after})"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        # SL-04-001/SL-04-006: embargo teardown is a protocol milestone.
        log_em_transition(
            self.logger,
            self.actor_id or "<unknown>",
            self.case_id,
            current_em,
            em_after,
        )
        return Status.SUCCESS


#: The ``Remove``'s key for the termination's why (EMB-13-005).
_TERMINATION_CAUSE = wire_key("termination_cause", VultronActivity)


class ApplyEmbargoTeardownNode(ApplyEmbargoChangeFromLedgerNode):
    """Copy a ``Remove(EmbargoEvent)`` entry onto this replica's case file.

    The ``EmbargoTeardown`` replica slot (RSH-08-004).  The entry is the
    whole ``TERMINATE`` register step (ADR-0122): applied through the one
    apply function, it terminates the embargo the ``Remove`` names (its
    ``object``), never whatever is in force locally, and cancels every open
    proposal in the same step (EP-08-004).  The ``TERMINATED`` entry records
    the cause the ``Remove`` carries as ``terminationCause``,
    ``END_TIME_REACHED`` included, copied as the entry states it: a replica
    never works a cause out from its own case state, and an entry with no
    ``terminationCause`` records an early end with an ``OTHER`` cause
    (EMB-13-005, ADR-0202).

    As on the CASE_MANAGER, where such a ``Remove`` is ledgered with no
    effect (CLP-02-013), an entry naming an embargo that is not the one in
    force changes nothing: SUCCESS, nothing written.  An entry whose
    ``terminationCause`` is malformed (EMB-13-012), that names no
    embargo, or that claims ``END_TIME_REACHED`` before the embargo's end
    time (its ``published`` time, ADR-0122), or against an embargo this
    store cannot read (EMB-18-003), is refused: FAILURE, which keeps the
    entry from being persisted (SYNC-12-001).  A step the apply function
    refuses is held for gap handling, as the frame does for every copied
    entry.
    """

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        snapshot = entry.payload_snapshot or {}
        embargo_id = _extract_id_from_field(snapshot.get("object"))
        if embargo_id is None:
            raise TypeError("the Remove names no EmbargoEvent")
        cause = snapshot.get(_TERMINATION_CAUSE)
        return RegisterStep(
            kind=RegisterStepKind.TERMINATE,
            embargo=embargo_id,
            termination=(
                EmbargoTermination.from_cause(None)
                if cause is None
                else EmbargoTermination.model_validate({"cause": cause})
            ),
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.context)
        if case is None:
            return super().update()  # Regime 2, or a malformed entry
        try:
            step = cast(RegisterStep, self._change(entry))
        except TypeError, ValueError:
            return super().update()  # reported by the frame
        if case.active_embargo_id != step.embargo_id:
            self.feedback_message = (
                f"{self.name}: '{entry.semantic_type}' entry '{entry.id_}' names"
                f" embargo '{step.embargo_id}', which is not the one in force"
                f" on case '{entry.context}' — nothing to copy (ADR-0122)"
            )
            self.logger.info("%s", self.feedback_message)
            return Status.SUCCESS
        try:
            violations = termination_timing_violations(
                cast(CasePersistence, self.datalayer),
                case,
                cast(EmbargoTermination, step.termination),
                parse_published(
                    (entry.payload_snapshot or {}).get("published")
                ),
            )
        except VultronError as exc:
            # An embargo that cannot be read fails closed (EMB-18-003).
            violations = [str(exc)]
        if violations:
            self.feedback_message = (
                f"Refused teardown entry '{entry.id_}' on case"
                f" '{entry.context}': " + "; ".join(violations)
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return super().update()


class SendAnnounceEmbargoEventNode(_SendEmbargoActivityForCaseKey):
    """Emit an ``Announce(EmbargoEvent)`` after embargo teardown.

    Resolves the Case Manager actor ID from the case, builds the outbound
    ``Announce(EmbargoEvent)`` activity via ``trigger_activity_factory``,
    and queues it to the actor's outbox.

    Best-effort semantics: returns SUCCESS with a WARNING log when the
    factory is unavailable, no Case Manager can be resolved, or the outbox
    write fails after the activity is already constructed — teardown must
    not be blocked by notification gaps.  Returns FAILURE only on hard data
    errors (case read fails, case not found, factory dispatch raises).

    Used immediately after ``ClearActiveEmbargoNode`` in the CASE_MANAGER's
    ``ActiveTeardown`` sequence of ``remove_embargo_from_case_tree`` so
    that all participants receive a protocol-level announcement of the
    embargo termination; a participant replica's arm never runs it
    (BT-17-008).

    The case is read from ``/case_id`` and the embargo from ``/embargo_id``
    (BTND-01-008).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_SendEmbargoActivityForCaseKey.INPUT_PORTS,
        **act_key_ports(EMBARGO_ID),
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name)
        self._recipients: list[str] = []

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            **super()._domain_port_remappings(),
            **act_key_remappings(EMBARGO_ID),
        }

    def initialise(self) -> None:
        super().initialise()
        self._embargo_id: str = act_value(self, EMBARGO_ID, str)

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — Announce(EmbargoEvent) skipped"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS

    def _resolve_embargo_and_manager(self) -> tuple[str, str] | Status:
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        case_manager_id = resolve_case_manager_id(case, self.datalayer)
        if case_manager_id is None:
            self.feedback_message = (
                f"No Case Manager found for case '{self._case_id}'"
                " — Announce(EmbargoEvent) skipped"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        # Recipients are every *other* participant, not the Case Manager.  This
        # node runs in the CASE_MANAGER arm of `remove_embargo_from_case_tree`
        # (its `manager_effects`), so the executing actor *is* the manager —
        # addressing the announce to the manager addressed it to itself and the
        # teardown reached nobody.  The Case Manager is still resolved above,
        # because "the case has a manager" remains the precondition for
        # announcing canonical case state at all.
        # Only active participants receive the announce (CM-10-004); the shared
        # selection decides who those are (CM-10-007).  A participant at RM
        # CLOSED gets no embargo announcement (CM-23-004); a closed signatory
        # gets the CM-31-009 notice instead.
        self._recipients = case_content_recipients(
            case, self.datalayer, excluding={self.actor_id or ""}
        )
        if not self._recipients:
            self.feedback_message = (
                f"No other participants on case '{self._case_id}'"
                " — Announce(EmbargoEvent) skipped"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS

        return self._embargo_id, case_manager_id

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.announce_embargo(
            embargo_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=self._recipients,
            at=self._require_act_instant(),
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"Outbox write failed for Announce(EmbargoEvent)"
            f" '{activity_id}': {exc}"
            " — activity constructed but not queued"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS
