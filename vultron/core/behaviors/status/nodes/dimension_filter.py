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

"""Per-dimension partial-accept filtering for received ParticipantStatus.

An inbound ``Add(ParticipantStatus, CaseParticipant)`` carries a snapshot of
several *independent* state machines: ``rm`` (Report Management), ``vfd``
(vendor fix path), ``pxa`` (public state), ``em`` (embargo) and ``consent``
(participant embargo consent).  Because they are independent, a value that is
unacceptable in one dimension says nothing about the others.

Before RSH-05, one refused dimension discarded the entire snapshot: the
receiving Case Actor dropped the accepted dimensions along with the refused
one and aborted the enclosing ``AddParticipantStatusBT`` Sequence, which also
skipped the StatusAdoptionGate → EmbargoTeardownAuthorizationGate emit and therefore embargo teardown
(ISSUE-2235, RSH-01-003, RSH-01-004).

:class:`FilterParticipantStatusDimensionsNode` adjudicates each dimension on
its own and publishes a *filtered* status in which refused dimensions carry
forward the participant's current value.  It is a read-only precondition guard
(CLP-10-006): it reads the DataLayer but writes only to the blackboard, so it
runs *before* ``GuardedCommit`` and the canonical ledger entry can record the
accepted portion rather than the raw assertion.

Per specs/received-status-handling.yaml RSH-05.
"""

import logging
from typing import TYPE_CHECKING, Any

import py_trees
from py_trees.common import Status

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.case.nodes.lifecycle import (
    BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
)
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.behaviors.status.nodes._adjudication import (
    _adjudicate_dimensions,
)
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)

logger = logging.getLogger(__name__)

#: Blackboard key carrying the per-dimension filter outcome for the append
#: nodes downstream (``ResolveAndPersistStatusObjectNode``,
#: ``ValidateRMTransitionNode``).  ``None`` when nothing was filtered.
BB_DIMENSION_FILTER = "append_status_dimension_filter"

#: Blackboard key for RM transition anomaly info published by
#: :class:`FilterParticipantStatusDimensionsNode` (non-adjacent forward jump)
#: and :class:`~vultron.core.behaviors.status.nodes.rm_validation.ValidateRMTransitionNode`
#: (backward regression on the standalone path).  ``None`` when no anomaly.
#: When set: ``{"anomaly_type": "gap"|"regression", "from_rm": RM, "to_rm": RM}``.
BB_RM_ANOMALY = "rm_transition_anomaly"


def _accepted_wire_patch(
    filtered: ParticipantStatus,
    port: "WireRenderPort",
) -> dict[str, Any]:
    """Return the adjudicated dimension values keyed by their wire aliases.

    The canonical ledger's ``payload_snapshot['object']`` is the *sender's*
    wire-shaped ``ParticipantStatus`` — flat ``rmState``/``vfdState``, nested
    ``caseStatus``, plus ``@context``, ``emConsentState`` and ``cvdRole``.  The
    override is therefore published as a **patch** rather than a replacement
    object: patching leaves the snapshot's shape exactly as the non-override
    path produces it and rewrites only what was adjudicated (RSH-05-004,
    RSH-05-009).  Wire key names are obtained from the port rather than
    hardcoded here (CLP-07-009, CLP-07-010, ADR-0063).
    """
    rendered = port.render(filtered)
    return {
        k: rendered[k]
        for k in ("rmState", "vfdState", "caseStatus")
        if k in rendered
    }


def _to_core_status(status_obj: Any) -> ParticipantStatus | None:
    """Return *status_obj* as a core :class:`ParticipantStatus`, or ``None``.

    ``SqliteDataLayer.read`` already returns core models.  For any other
    object (e.g. a wire-layer ``as_ParticipantStatus`` supplied as a
    fallback by the tree factory), call ``to_core()`` to project it to the
    core type (ARCH-20-007).
    """
    if isinstance(status_obj, ParticipantStatus):
        return status_obj
    if status_obj is None:
        return None
    to_core = getattr(status_obj, "to_core", None)
    if to_core is None:
        return None
    try:
        result = to_core()
        return result if isinstance(result, ParticipantStatus) else None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "FilterParticipantStatusDimensionsNode: could not normalise"
            " status object '%s' to a core ParticipantStatus: %s",
            _as_id(status_obj),
            exc,
        )
        return None


def _significant_state(status: ParticipantStatus) -> tuple:
    """Return the protocol-significant fields of *status* as a comparable tuple.

    Used to decide whether a filtered status still carries information the
    case does not already hold.  Identity fields (``id``, timestamps, ``name``)
    are deliberately excluded — a status that merely restates the participant's
    current state under a new ID is not new information.
    """
    case_status = status.case_status
    return (
        status.rm.state,
        status.vfd.state,
        None if case_status is None else case_status.em.state,
        None if case_status is None else case_status.pxa.state,
        None if status.consent is None else status.consent.state,
        status.case_engagement,
        status.embargo_adherence,
        tuple(sorted(str(role) for role in status.cvd_role)),
    )


def _dimension_state(status: ParticipantStatus, dimension: str) -> Any:
    """Return the state of one adjudicated dimension of *status*.

    Used to tell a dimension that was genuinely *rewritten* from one that was
    blocked but whose recorded value matches the assertion anyway.
    """
    if dimension == "rm":
        return status.rm.state
    if dimension == "vfd":
        return status.vfd.state
    if dimension == "pxa":
        return (
            None
            if status.case_status is None
            else status.case_status.pxa.state
        )
    return None


class FilterParticipantStatusDimensionsNode(DataLayerConditionWithPorts):
    """Adjudicate each dimension of an inbound ParticipantStatus separately.

    Read-only precondition guard (CLP-10-006): reads the participant and the
    asserted status from the DataLayer and writes only to the blackboard.

    For each of ``rm``, ``vfd`` and ``pxa`` the asserted value is accepted when
    it confirms or monotonically advances the participant's current value, and
    refused otherwise.  Refused dimensions carry forward the current value into
    a *filtered* status which is published on the blackboard for the append
    nodes and, as a serialized ``object`` override, for the canonical ledger
    commit.  ``em``, ``consent``, ``case_engagement``, ``embargo_adherence``,
    ``cvd_role`` and ``tracking_id`` pass through untouched — ``em`` in
    particular is EmbargoTeardownAuthorizationGate's to adjudicate (ADR-0046, ISSUE-2256).

    Returns:
        SUCCESS when there is nothing to filter (no participant, no current
        status, idempotent re-delivery, or every dimension acceptable) and when
        a partial accept was computed.

        FAILURE only when at least one dimension was refused *and* the
        resulting filtered status is indistinguishable from the participant's
        current state — the assertion carried no acceptable information, so
        there is nothing to record and no ledger entry should be committed.

    Per specs/received-status-handling.yaml RSH-05.
    """

    def __init__(
        self,
        participant_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.participant_id = participant_id
        self.status_id = status_id
        self.status_obj_fallback = status_obj_fallback
        self.wire_render_port: "WireRenderPort | None" = None

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        return {
            **super().input_ports(),
            "wire_render_port": PortInformation(
                data_type=object, required=False
            ),
        }

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {
            BB_DIMENSION_FILTER: PortInformation(
                data_type=object, required=False
            ),
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE: PortInformation(
                data_type=object, required=False
            ),
            BB_RM_ANOMALY: PortInformation(data_type=object, required=False),
        }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "wire_render_port": "/wire_render_port",
            BB_DIMENSION_FILTER: f"/{BB_DIMENSION_FILTER}",
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE: f"/{BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE}",
            BB_RM_ANOMALY: f"/{BB_RM_ANOMALY}",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self.wire_render_port = self.get_input("wire_render_port")
        except Exception:
            self.wire_render_port = None

    def _publish(
        self,
        refused: tuple[str, ...],
        filtered: ParticipantStatus | None,
        rm_anomaly: dict | None = None,
    ) -> None:
        """Publish (or clear) the filter outcome on the blackboard.

        The py_trees blackboard is process-global and is not cleared between
        executions, so all keys are written on *every* tick — including with
        ``None`` when no filtering applies — to prevent a previous run's
        override from leaking into this one.
        """
        if filtered is None:
            self._set_output(BB_DIMENSION_FILTER, None)
            self._set_output(BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE, None)
            self._set_output(BB_RM_ANOMALY, None)
            return

        self._set_output(
            BB_DIMENSION_FILTER,
            {
                "status_id": self.status_id,
                "participant_id": self.participant_id,
                "refused": refused,
                "filtered_status": filtered,
            },
        )
        if self.wire_render_port is not None:
            override_fields: dict[str, Any] | None = _accepted_wire_patch(
                filtered, self.wire_render_port
            )
        else:
            logger.warning(
                "%s: wire_render_port not available; skipping"
                " BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE (RSH-05-004)",
                self.name,
            )
            override_fields = None
        self._set_output(
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
            (
                {
                    "object_id": self.status_id,
                    "producer_type": self.__class__.__name__,
                    "fields": override_fields,
                }
                if override_fields is not None
                else None
            ),
        )
        self._set_output(BB_RM_ANOMALY, rm_anomaly)

    def _detect_rm_anomaly(
        self,
        refused: list[str],
        current_rm: RM,
        asserted_rm: RM,
    ) -> dict | None:
        """Return an anomaly dict when an RM transition anomaly is detected.

        Returns ``None`` when there is nothing anomalous to record.
        """
        if "rm" in refused:
            return {
                "anomaly_type": "regression",
                "from_rm": current_rm,
                "to_rm": asserted_rm,
            }
        if (
            current_rm != RM.CLOSED
            and asserted_rm != current_rm
            and not is_valid_rm_transition(current_rm, asserted_rm)
            and is_monotonic_rm_forward(current_rm, asserted_rm)
        ):
            self.logger.warning(
                "%s: non-adjacent forward RM jump %s → %s for participant"
                " '%s'; accepting sender-authoritative state (RSH-06-001)",
                self.name,
                current_rm,
                asserted_rm,
                self.participant_id,
            )
            return {
                "anomaly_type": "gap",
                "from_rm": current_rm,
                "to_rm": asserted_rm,
            }
        return None

    def _resolve_asserted(self) -> ParticipantStatus | None:
        """Return the asserted status as a core model, DataLayer first."""
        assert self.datalayer is not None
        from_dl = (
            self.datalayer.read(self.status_id) if self.status_id else None
        )
        return _to_core_status(
            from_dl if from_dl is not None else self.status_obj_fallback
        )

    def update(self) -> Status:
        # Clear first, unconditionally: the no-op paths below must not inherit
        # a previous execution's override from the process-global blackboard,
        # and neither must the datalayer-missing early return (BT-17-003/004).
        self._publish((), None)

        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        participant = self.datalayer.read(self.participant_id)
        if not isinstance(participant, CaseParticipant):
            # LoadParticipantNode reports the missing participant; nothing to
            # filter against here.
            self._publish((), None)
            return Status.SUCCESS

        existing_ids = [
            _as_id(s) for s in getattr(participant, "participant_statuses", [])
        ]
        if self.status_id and self.status_id in existing_ids:
            # Idempotent re-delivery: the status is already recorded, so the
            # append subtree short-circuits and there is nothing to filter.
            self._publish((), None)
            return Status.SUCCESS

        current = getattr(participant, "participant_status", None)
        asserted = self._resolve_asserted()
        if not isinstance(current, ParticipantStatus) or asserted is None:
            self._publish((), None)
            return Status.SUCCESS

        refused, update_fields = _adjudicate_dimensions(current, asserted)
        rm_anomaly = self._detect_rm_anomaly(
            refused, current.rm.state, asserted.rm.state
        )

        if not update_fields:
            # No dimension filtering needed; publish the anomaly flag only.
            if rm_anomaly is not None:
                self._set_output(BB_RM_ANOMALY, rm_anomaly)
            return Status.SUCCESS

        # ``name`` on a ParticipantStatus is a derived state summary (the wire
        # model rebuilds it from the dimension names whenever it is ``None``).
        # Carrying the sender's label forward would leave the recorded object
        # describing itself by the refused value, so clear it and let it be
        # regenerated from what was actually accepted.
        update_fields["name"] = None
        filtered = asserted.model_copy(update=update_fields)

        # RSH-05-005: nothing acceptable was carried by this assertion, so
        # appending it would grow the status history and the hash chain without
        # recording a state change.  Reached both when every refused dimension
        # left the snapshot at the current state and when an omitted
        # ``case_status`` was the only thing carried forward.
        if _significant_state(filtered) == _significant_state(current):
            self.feedback_message = (
                f"Status '{self.status_id}' refused in full for participant"
                f" '{self.participant_id}': {self._carry_summary(refused)}"
                " and no other dimension carries new state"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            self._publish((), None)
            # Still publish the anomaly even on a wholly-refused assertion:
            # the receiver detected an anomaly and must emit a note (RSH-06).
            if rm_anomaly is not None:
                self._set_output(BB_RM_ANOMALY, rm_anomaly)
            return Status.FAILURE

        self._publish(tuple(refused), filtered, rm_anomaly=rm_anomaly)
        self.feedback_message = (
            f"Partially accepted status '{self.status_id}' for participant"
            f" '{self.participant_id}': {self._carry_summary(refused)}"
        )
        # A refused dimension whose recorded value equals the asserted one
        # discarded nothing — RM.CLOSED restated by a participant that has
        # already closed is the common case (RSH-05-006).  Naming it as a
        # refusal in the operator-facing log would misdescribe the audit trail,
        # so report what was actually rewritten.
        rewritten = [
            dim
            for dim in refused
            if _dimension_state(filtered, dim)
            != _dimension_state(asserted, dim)
        ]
        self.logger.warning(
            "%s: %s for participant '%s' (asserted rm=%s vfd=%s pxa=%s;"
            " recording rm=%s vfd=%s pxa=%s) — RSH-05 partial accept",
            self.name,
            (
                f"rewrote dimension(s) {', '.join(rewritten)}"
                if rewritten
                else "blocked dimension(s) "
                + ", ".join(refused)
                + " with no change to the asserted value"
            ),
            self.participant_id,
            asserted.rm.state,
            asserted.vfd.state,
            (
                None
                if asserted.case_status is None
                else asserted.case_status.pxa.state
            ),
            filtered.rm.state,
            filtered.vfd.state,
            (
                None
                if filtered.case_status is None
                else filtered.case_status.pxa.state
            ),
        )
        return Status.SUCCESS

    @staticmethod
    def _carry_summary(refused: list[str]) -> str:
        """Describe what the filter did, for feedback messages."""
        if refused:
            return f"refused dimension(s) {', '.join(refused)}"
        return "carried the current case_status forward (none asserted)"


def resolve_dimension_filter(
    blackboard: py_trees.blackboard.Client, status_id: str
) -> dict[str, Any] | None:
    """Return the filter outcome for *status_id*, or ``None``.

    Helper for the append nodes downstream of
    :class:`FilterParticipantStatusDimensionsNode`.  The ``status_id`` match
    guards against a stale entry from an earlier execution, since the py_trees
    blackboard is process-global.
    """
    try:
        payload = blackboard.get(BB_DIMENSION_FILTER)
    except KeyError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("status_id") != status_id:
        return None
    return payload
