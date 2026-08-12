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
skipped the Seam 1 → Seam 2 emit and therefore embargo teardown
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
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.lifecycle import (
    BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
)
from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    PxaDimension,
    RmDimension,
    VfdDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import (
    is_monotonic_pxa_forward,
    is_monotonic_vfd_forward,
)
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)

logger = logging.getLogger(__name__)

#: Blackboard key carrying the per-dimension filter outcome for the append
#: nodes downstream (``ResolveAndPersistStatusObjectNode``,
#: ``ValidateRMTransitionNode``).  ``None`` when nothing was refused.
BB_DIMENSION_FILTER = "append_status_dimension_filter"


def _to_core_status(status_obj: Any) -> ParticipantStatus | None:
    """Return *status_obj* as a core :class:`ParticipantStatus`, or ``None``.

    ``SqliteDataLayer.read`` already returns core models, but the fallback
    object supplied by the tree factory comes from the wire layer with flat
    ``rmState``/``vfdState`` fields.  The core model's ``_migrate_flat_fields``
    validator accepts that shape, so a dump-and-revalidate normalises both.
    """
    if isinstance(status_obj, ParticipantStatus):
        return status_obj
    if status_obj is None or not hasattr(status_obj, "model_dump"):
        return None
    try:
        return ParticipantStatus.model_validate(
            status_obj.model_dump(
                mode="json",
                by_alias=True,
                serialize_as_any=True,
                exclude_none=True,
            )
        )
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


def _rm_is_acceptable(current: RM, asserted: RM) -> bool:
    """Return True if *asserted* is an acceptable RM value given *current*.

    ``RM.CLOSED`` is terminal (DEMOMA-07-003): once a participant has closed,
    no further RM value — not even ``CLOSED`` again — is acceptable.  Otherwise
    a status confirmation (no change), a valid adjacent transition, or a
    non-adjacent but monotone forward jump are all acceptable; the sender is
    authoritative about its own RM progress.
    """
    if current == RM.CLOSED:
        return False
    if asserted == current:
        return True
    return is_valid_rm_transition(
        current, asserted
    ) or is_monotonic_rm_forward(current, asserted)


def _adjudicate_dimensions(
    current: ParticipantStatus, asserted: ParticipantStatus
) -> tuple[list[str], dict[str, Any]]:
    """Adjudicate ``rm``, ``vfd`` and ``pxa`` independently.

    Returns the names of the refused dimensions and the ``model_copy`` update
    that carries the current value forward for each of them.  ``em``,
    ``consent``, ``case_engagement``, ``embargo_adherence``, ``cvd_role`` and
    ``tracking_id`` are not adjudicated here — ``em`` in particular belongs to
    Seam 2 (ADR-0046, ISSUE-2256).
    """
    refused: list[str] = []
    update_fields: dict[str, Any] = {}

    if not _rm_is_acceptable(current.rm.state, asserted.rm.state):
        refused.append("rm")
        update_fields["rm"] = RmDimension(state=current.rm.state)

    current_vfd = current.vfd.state
    asserted_vfd = asserted.vfd.state
    if asserted_vfd != current_vfd and not is_monotonic_vfd_forward(
        current_vfd, asserted_vfd
    ):
        refused.append("vfd")
        update_fields["vfd"] = VfdDimension(state=current_vfd)

    asserted_cs = asserted.case_status
    current_cs = current.case_status
    if asserted_cs is not None and current_cs is not None:
        current_pxa = current_cs.pxa.state
        asserted_pxa = asserted_cs.pxa.state
        if asserted_pxa != current_pxa and not is_monotonic_pxa_forward(
            current_pxa, asserted_pxa
        ):
            refused.append("pxa")
            update_fields["case_status"] = asserted_cs.model_copy(
                update={"pxa": PxaDimension(state=current_pxa)}
            )

    return refused, update_fields


class FilterParticipantStatusDimensionsNode(DataLayerCondition):
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
    particular is Seam 2's to adjudicate (ADR-0046, ISSUE-2256).

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

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key=BB_DIMENSION_FILTER,
            access=py_trees.common.Access.WRITE,
        )
        self.blackboard.register_key(
            key=BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
            access=py_trees.common.Access.WRITE,
        )

    def _publish(
        self,
        refused: tuple[str, ...],
        filtered: ParticipantStatus | None,
    ) -> None:
        """Publish (or clear) the filter outcome on the blackboard.

        The py_trees blackboard is process-global and is not cleared between
        executions, so both keys are written on *every* tick — including with
        ``None`` when no filtering applies — to prevent a previous run's
        override from leaking into this one.
        """
        if filtered is None or not refused:
            self.blackboard.set(BB_DIMENSION_FILTER, None, overwrite=True)
            self.blackboard.set(
                BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE, None, overwrite=True
            )
            return

        self.blackboard.set(
            BB_DIMENSION_FILTER,
            {
                "status_id": self.status_id,
                "participant_id": self.participant_id,
                "refused": refused,
                "filtered_status": filtered,
            },
            overwrite=True,
        )
        self.blackboard.set(
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
            {
                "object_id": self.status_id,
                "object": filtered.model_dump(
                    mode="json",
                    by_alias=True,
                    serialize_as_any=True,
                    exclude_none=True,
                ),
            },
            overwrite=True,
        )

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
        if not refused:
            self._publish((), None)
            return Status.SUCCESS

        # ``name`` on a ParticipantStatus is a derived state summary (the wire
        # model rebuilds it from the dimension names whenever it is ``None``).
        # Carrying the sender's label forward would leave the recorded object
        # describing itself by the refused value, so clear it and let it be
        # regenerated from what was actually accepted.
        update_fields["name"] = None
        filtered = asserted.model_copy(update=update_fields)

        if _significant_state(filtered) == _significant_state(current):
            self.feedback_message = (
                f"Status '{self.status_id}' refused in full for participant"
                f" '{self.participant_id}': refused dimension(s)"
                f" {', '.join(refused)} and no other dimension carries new"
                " state"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            self._publish((), None)
            return Status.FAILURE

        self._publish(tuple(refused), filtered)
        self.feedback_message = (
            f"Partially accepted status '{self.status_id}' for participant"
            f" '{self.participant_id}': refused {', '.join(refused)}"
        )
        self.logger.warning(
            "%s: refused dimension(s) %s for participant '%s' (asserted"
            " rm=%s vfd=%s pxa=%s; recording rm=%s vfd=%s pxa=%s) — RSH-05"
            " partial accept",
            self.name,
            ", ".join(refused),
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
