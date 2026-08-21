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

"""Reject-proposed-embargo BT nodes (EMB-16-001).

Handles the cascade arm triggered when CS.P/X/A fires while EM is PROPOSED:
abandon the proposed embargo via reject_embargo_invite() and queue an ER
activity to the Case Manager.

Extracted from lifecycle.py to keep that module under the BTND-07-004
500-line limit.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.em_state import (
    ReadEmStateNode,
    WriteEmStateNode,
)
from vultron.core.behaviors.embargo.nodes.emit import _SendEmbargoActivityBase
from vultron.core.behaviors.helpers import (
    DataLayerAction,
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.services.embargo_lifecycle import (
    EmbargoLifecycle,
    TransitionMode,
)
from vultron.core.states.em import EM
from vultron.errors import VultronError


class RejectProposedEmbargoLifecycleNode(DataLayerActionWithPorts):
    """Apply STRICT reject-invite transition reading embargo_id from the blackboard.

    Cascade-path variant of :class:`RejectEmbargoLifecycleNode` used by
    :func:`~vultron.core.behaviors.embargo.trigger_tree.reject_proposed_embargo_bt`.

    Reads ``embargo_id`` written by ``ReadProposedEmbargoIdNode`` so the
    transition uses the correct proposed embargo rather than a
    construction-time value.

    EMB-16-001: abandons a proposed embargo when P/X/A fires while EM is PROPOSED.
    """

    def __init__(
        self,
        case_id: str,
        result_out: dict[str, object],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id_value = case_id
        self._result_out = result_out

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["embargo_id"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"embargo_id": "/embargo_id"}

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        embargo_id = self.embargo_id

        read_node = ReadEmStateNode(
            case_id=self._case_id_value, result_out=self._result_out
        )
        read_node.datalayer = self.datalayer
        read_status = read_node.update()
        if read_status != Status.SUCCESS:
            self.feedback_message = read_node.feedback_message
            return Status.FAILURE
        em_before = self._result_out["em_before"]
        assert isinstance(em_before, EM)

        lifecycle = EmbargoLifecycle(persistence=self.datalayer)
        try:
            result = lifecycle.reject_embargo_invite(
                case_id=self._case_id_value,
                embargo_id=embargo_id,
                actor_id=self.actor_id,
                transition_mode=TransitionMode.STRICT,
                em_before=em_before,
            )
        except VultronError as exc:
            self._result_out["error"] = exc
            self.feedback_message = str(exc)
            return Status.FAILURE

        self._result_out["lifecycle_result"] = result
        self._result_out["em_after"] = result.em_after

        if result.em_after != em_before:
            write_node = WriteEmStateNode(
                case_id=self._case_id_value, result_out=self._result_out
            )
            write_node.datalayer = self.datalayer
            write_status = write_node.update()
            if write_status != Status.SUCCESS:
                self.feedback_message = write_node.feedback_message
                return Status.FAILURE

        return Status.SUCCESS


class ReadProposedEmbargoIdNode(DataLayerAction):
    """Read the first proposed embargo ID from the case and write it to the blackboard.

    Used by the EM PROPOSED cascade arm of ``PublicDisclosureBranchNode``
    (EMB-16-001): when public disclosure fires while EM is PROPOSED we must
    reject the proposed embargo.  Unlike ``ReadEmbargoIdNode`` (which reads
    ``active_embargo``), this node reads the first entry of
    ``proposed_embargoes``.

    Returns FAILURE when the case is not found, has no proposed embargoes, or
    the DataLayer is unavailable.  Returns SUCCESS and writes ``embargo_id``
    to the blackboard on success.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: object) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="embargo_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case = self.datalayer.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.feedback_message = f"Case '{self._case_id}' not found"
            return Status.FAILURE

        proposed = case.proposed_embargoes
        if not proposed:
            self.feedback_message = (
                f"No proposed embargoes on case '{self._case_id}'"
            )
            return Status.FAILURE

        embargo_id = _as_id(proposed[0])
        if embargo_id is None:
            self.feedback_message = (
                f"First proposed embargo on case '{self._case_id}' has no id"
            )
            return Status.FAILURE

        self.blackboard.embargo_id = embargo_id
        return Status.SUCCESS


class SendRejectEmbargoActivityNode(_SendEmbargoActivityBase):
    """Build and queue a ``Reject(EmbargoEvent)`` activity.

    Used as the emit step in the EM PROPOSED cascade arm
    (EMB-16-001): reads ``embargo_id`` and ``case_manager_id`` from the
    blackboard and constructs the outbound ER activity via
    ``trigger_activity_factory.reject_embargo``.

    Returns FAILURE (BT-14-001) when the factory is unavailable, a required
    blackboard key is missing, or dispatch raises an exception.
    Returns SUCCESS when the activity is created and queued.
    """

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(case_id=case_id, name=name)

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["embargo_id"] = PortInformation(data_type=str, required=True)
        ports["case_manager_id"] = PortInformation(
            data_type=str, required=True
        )
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "embargo_id": "/embargo_id",
            "case_manager_id": "/case_manager_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.embargo_id: str = self.get_input("embargo_id")
        self.case_manager_id: str = self.get_input("case_manager_id")

    def _on_factory_unavailable(self) -> Status:
        self.feedback_message = (
            "trigger_activity_factory not available"
            " — reject embargo broadcast FAILURE (BT-14-001)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _resolve_embargo_and_manager(self) -> "tuple[str, str] | Status":
        return self.embargo_id, self.case_manager_id

    def _call_factory(
        self, actor_id: str, embargo_id: str, case_manager_id: str
    ) -> tuple[str, object]:
        assert self.trigger_activity_factory is not None
        return self.trigger_activity_factory.reject_embargo(
            proposal_id=embargo_id,
            case_id=self._case_id,
            actor=actor_id,
            to=[case_manager_id],
        )

    def _on_outbox_write_failure(
        self, activity_id: str, exc: Exception
    ) -> Status:
        self.feedback_message = (
            f"Outbox write failed for Reject(EmbargoEvent)"
            f" '{activity_id}': {exc}"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE
