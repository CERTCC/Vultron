"""Shared frame of the received use cases whose object is the ``EmbargoEvent``.

The case owner's decisions (``Add``/``Reject(EmbargoEvent)[target=VulnerabilityCase]``,
ADR-0122) and a signatory's withdrawal (``Leave(EmbargoEvent)``,
MSM-07-010) name the embargo itself, not an Invite, and only the
CASE_MANAGER applies them.  Each runs the same steps: shape checks that write
nothing, the door check (HP-01-005, ADR-0118), one tree (CLP-10-005), and a
refusal when the receiver's CASE_MANAGER gate turned it away (BT-17-001).
"""

import logging
from typing import TYPE_CHECKING, ClassVar

import py_trees

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.behaviors.case.received_run import run_received_tree
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.models.events.embargo import (
    ActivateEmbargoOnCaseReceivedEvent,
    RejectEmbargoProposalOnCaseReceivedEvent,
    WithdrawFromEmbargoOnCaseReceivedEvent,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence

logger = logging.getLogger(__name__)

EmbargoEventRequest = (
    ActivateEmbargoOnCaseReceivedEvent
    | RejectEmbargoProposalOnCaseReceivedEvent
    | WithdrawFromEmbargoOnCaseReceivedEvent
)
"""A received activity whose object is the ``EmbargoEvent`` on a case."""


class _EmbargoEventReceivedUseCase:
    """Run one CASE_MANAGER-applied tree for an activity on the ``EmbargoEvent``.

    Subclasses declare :attr:`sender_entitlement`, which the tree's factory
    composes into the sender guard (HP-01-008), and name their tree in
    :meth:`_build_tree`, so the ledger-commit inventory sees which received
    tree each one runs.  A guard's benign no-op is read as ``SKIPPED`` by
    the runner, from the guard's own repeat declaration (HP-01-014).
    """

    sender_entitlement: ClassVar[SenderRule]
    _label: ClassVar[str]
    _tree_label: ClassVar[str]

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: EmbargoEventRequest,
        *,
        sync_port: SyncActivityPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._wire_render_port = wire_render_port

    def _build_tree(
        self, case_id: str, embargo_id: str, sender_actor_id: str
    ) -> py_trees.behaviour.Behaviour:
        raise NotImplementedError

    def _applied_message(self, embargo_id: str, case_id: str) -> str | None:
        """An INFO line for an applied run, or ``None`` for none."""
        return None

    def execute(self) -> HandlerResult:
        request, label = self._request, self._label
        embargo_id, case_id = request.embargo_id, request.case_id
        if embargo_id is None or case_id is None:
            logger.warning("%s: missing embargo_id or case_id", label)
            return HandlerResult.refused(
                f"{label} is missing its embargo id or case id"
            )
        # The tree's door guards refuse a closed case, an unaddressed copy
        # (HP-01-005, ADR-0118) and a sender without standing first.  Only
        # the CASE_MANAGER applies: each tree declares the manager path
        # alone, so its path stage refuses a replica, which learns the
        # change from the ledger broadcast (BT-17-001, HP-01-039).
        tree = self._build_tree(case_id, embargo_id, request.actor_id)
        verdict = run_received_tree(
            tree,
            dl=self._dl,
            request=request,
            label=self._tree_label,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            # The commit fans the entry out to every participant replica
            # (EP-09-007, RSH-08-004); without the port nothing replays it.
            sync_port=self._sync_port,
        )
        if verdict.disposition is HandlerDisposition.APPLIED:
            message = self._applied_message(embargo_id, case_id)
            if message is not None:
                logger.info("%s", message)
        elif verdict.disposition is HandlerDisposition.SKIPPED:
            logger.info(
                "%s (embargo '%s', case '%s')",
                verdict.reason,
                embargo_id,
                case_id,
            )
        return verdict


__all__ = ["EmbargoEventRequest"]
