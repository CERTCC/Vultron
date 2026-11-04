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

"""``TransitionRMtoValid``: RM.VALID on the case participant and the report link.

Case-scoped first, then the report link (DUR-07-004, ID-04-005).
"""

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.behaviors.case.nodes.participant.trigger_validation import (
    check_participant_status_move,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.report.nodes.rm_transitions.report_phase import (
    _read_report_case_link,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM, RMRule, is_rm_write_permitted


class TransitionRMtoValid(DataLayerActionWithPorts, StateWriteCapable):
    """Advance RM to VALID on the case participant and the report link, in one node.

    ``RM.VALID`` is *both* case-scoped and report-phase (ID-04-005): it advances
    the actor's RM state on the ``CaseParticipant`` *and* records ``RM.VALID``
    on the report's ``VultronReportCaseLink`` — the field ``CheckRMStateValid``
    reads.

    Issue #3267: when these were the two children of a ``Sequence``, a partial
    failure (participant advanced, link write failed) left the two records
    disagreeing.  ``CheckRMStateValid`` — reading only the link — then reported
    the report as not-valid forever.  This node is not a database transaction:
    it performs both writes in one execution and *orders* them so a failure
    cannot permanently strand the records:

    1. It first *reads and validates* the link.  When the link is **absent**
       the participant is still advanced but the link is **left absent**
       (issue #3283): some stores legitimately reach this transition without a
       prior link-seeding node — e.g. the CaseActor's store, which tracks every
       participant of the one report — and the pre-#3267 design advanced the
       participant regardless of link presence.  Because the link is
       report-scoped *per store*, latching an absent link to ``RM.VALID`` for
       the first participant would make ``CheckRMStateValid`` short-circuit
       every sibling participant's validate in that shared store, stranding
       them at ``RM.RECEIVED`` (issue #3283 / #3266) — so an absent link is
       never persisted.  An **illegal** source state (``current → RM.VALID``
       not legal, and not already ``VALID``) still fails here, **before** the
       participant is touched, so the participant is never advanced when the
       link cannot follow.
    2. It then advances the case participant through
       :class:`CreateParticipantStatusNode` — the sole ``ParticipantStatus``
       writer (ADR-0089) — reading ``/case_id`` from the blackboard seeded by
       :class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`.
    3. Only then does it save ``RM.VALID`` on the link (ID-04-005: the
       case-scoped write precedes the link latch).

    The one remaining window — a transient DataLayer error on the final save —
    leaves the participant at ``VALID`` and the link one step behind, but the
    next tick re-runs and the two records reconverge rather than diverging
    permanently: the link save retries.  That re-run does not append a
    second ``RM.VALID`` ``ParticipantStatus`` rung: the node skips the
    case-scoped write when the participant already records ``RM.VALID``
    (RSH-08-002).  The same skip covers a store that holds no link, where
    ``CheckRMStateValid`` can never short-circuit the validate tree.
    """

    def __init__(
        self,
        report_id: str,
        offer_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
        rm_rule: RMRule = RMRule.TRANSITION,
        written_ids: list[str] | None = None,
        record_participant: bool = True,
    ) -> None:
        """Initialize the combined RM.VALID transition node.

        Args:
            report_id: ID of the VulnerabilityReport whose RM state advances.
            offer_id: Retained for call-site API compatibility with the other
                report-phase transitions; not read by this node.
            sender_actor_id: Subject actor for the case-scoped RM write.
                When ``None``, the executing actor's blackboard ``actor_id`` is
                used as a fallback (BTND-10-005, ADR-0089).
            name: Optional custom node name (defaults to ``"TransitionRMtoValid"``).
            rm_rule: The RM rule the case-scoped participant write is held to;
                passed to :class:`CreateParticipantStatusNode`.  The received
                side passes ``DECLARATION`` (RSH-06-006).  The report-link
                latch keeps its own adjacency check either way: it is the
                report-phase record, not the sender's participant.
            written_ids: Passed to :class:`CreateParticipantStatusNode`, which
                reports in it the id of the status it writes.
            record_participant: ``False`` checks the report link and the
                sender's move and writes nothing.  The trigger side passes
                it: the CASE_MANAGER latches its link and records the status
                when it accepts the validation, and the sender's replica
                copies that status from the ledger (RSH-08-006, CLP-07-013).
        """
        super().__init__(name=name or "TransitionRMtoValid")
        self.report_id = report_id
        self.offer_id = offer_id  # unused; kept for call-site compatibility
        self.sender_actor_id = sender_actor_id
        self._record_participant = record_participant
        # Pre-built once and executed via BTBridge.execute_with_setup, never
        # constructed inside update() (BTND-10-004, ADR-0089).  Its own stop()
        # resets the latched actor id after each tick (issue #3268).
        self._status_node = CreateParticipantStatusNode(
            actor_id=sender_actor_id or "",
            rm_state=RM.VALID,
            vf_state=None,
            d_state=None,
            pxa_state=None,
            name="CreateRMValidStatus",
            rm_rule=rm_rule,
            written_ids=written_ids,
        )

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb = self._try_get_input("case_id")

    def _read_link(self) -> VultronReportCaseLink | None:
        assert self.datalayer is not None
        return _read_report_case_link(self.datalayer, self.report_id)

    def _participant_already_valid(self, case: VulnerabilityCase) -> bool:
        """True when the sender's participant already records ``RM.VALID``.

        Without a ``sender_actor_id``, or for a participant this case does
        not hold, the answer is ``False``: the write node then runs and
        reports the outcome itself.
        """
        assert self.datalayer is not None
        if self.sender_actor_id is None:
            return False
        participant_id = case.actor_participant_index.get(self.sender_actor_id)
        if participant_id is None:
            return False
        current_rm, _, _ = resolve_participant_state_from_dl(
            self.datalayer, participant_id
        )
        return current_rm == RM.VALID

    def update(self) -> Status:
        """Validate the link, then advance the participant and latch the link.

        With ``record_participant=False`` (the trigger side) the node stops
        after the checks: it validates the link's move and the sender's
        participant move and writes nothing, the link included
        (RSH-08-006).

        Returns:
            Received side: SUCCESS once both records read ``RM.VALID``.
            Trigger side: SUCCESS once both moves check out.  FAILURE when the
            DataLayer is unavailable, the report-phase transition is illegal,
            the sender or its participant record is missing, the sender's
            move is refused, the case-scoped write does not succeed, or the
            final link save raises.  An absent link advances the participant
            but is left unpersisted, not a failure (issue #3283).
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        # 1. Validate the link BEFORE advancing the participant, so an illegal
        #    source state cannot strand the participant at VALID while the link
        #    — the record CheckRMStateValid reads — stays behind (issue #3267).
        link = self._read_link()
        link_existed = link is not None
        if link is None:
            # A store can reach the VALID transition with no link (issue #3283):
            # the pre-#3267 design advanced the participant regardless, so
            # fail-fast-on-absence regressed those paths.  Build a transient
            # link *only* to run the transition-legality guard below; it is NOT
            # persisted (see step 3).  An absent link must stay absent because
            # the link is report-scoped per store: in the CaseActor's store,
            # which tracks every participant of the one report, latching the
            # shared link to VALID for the first participant makes
            # CheckRMStateValid short-circuit every sibling's validate, so they
            # never advance (issue #3283 / #3266).
            link = VultronReportCaseLink(report_id=self.report_id)
            self.logger.info(
                "%s: no ReportCaseLink for report '%s'; advancing the"
                " participant without latching an absent (report-scoped) link"
                " (issue #3283)",
                self.name,
                self.report_id,
            )
        current_rm = link.rm_state
        if not is_rm_write_permitted(current_rm, RM.VALID):
            self.feedback_message = (
                f"Invalid RM transition {current_rm!r} → {RM.VALID!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # 2. Case-scoped write FIRST (ID-04-005), through the sole
        #    ParticipantStatus writer.
        if not self._record_participant:
            # Trigger side: check the move and write nothing, the link
            # included.  The CASE_MANAGER latches its own link and records
            # the status when it accepts the validation; latching here would
            # make an actor that is its own CASE_MANAGER skip that write
            # (CheckRMStateValid) and a redelivery stop short (RSH-08-006).
            return self._check_participant() or Status.SUCCESS
        failure = self._advance_participant()
        if failure is not None:
            return failure

        # 3. Latch RM.VALID on the link only after the participant advanced,
        #    and only when the link already existed.  Latching an *absent*
        #    (transient) link would persist a report-scoped VALID record that
        #    short-circuits sibling participants in a shared CaseActor store
        #    (issue #3283); leaving it absent matches the pre-#3267 behavior.
        if not link_existed:
            self.logger.info(
                "RM → VALID for participant on report '%s' (report link left"
                " unlatched: it was absent — issue #3283)",
                self.report_id,
            )
            return Status.SUCCESS
        try:
            link.rm_state = RM.VALID
            self.datalayer.save(link)
            self.logger.info("RM → VALID for report '%s'", self.report_id)
            return Status.SUCCESS
        except Exception as e:  # noqa: BLE001 — transient save failure retries
            self.logger.error(  # noqa: TRY400  # ruff-baseline #3353
                "%s: Error latching RM.VALID on the report link: %s",
                self.name,
                e,
            )
            return Status.FAILURE

    def _check_participant(self) -> Status | None:
        """Check the sender may move to VALID; write nothing (RSH-08-006, RSH-08-012).

        The trigger side sends the validation and leaves the record to the
        CASE_MANAGER, so the move is checked here as the write would check
        it (BTND-10-002); ``None`` when legal.
        """
        assert self.datalayer is not None
        sender_actor_id = self.sender_actor_id
        if sender_actor_id is None:
            # One actor path to trace: the trigger names its sender
            # (BTND-10-005, ADR-0089); no blackboard actor fallback.
            self.feedback_message = "no sender_actor_id to check the move for"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure
        return check_participant_status_move(
            self,
            self.datalayer,
            case,
            actor_id=sender_actor_id,
            rm_state=RM.VALID,
        )

    def _advance_participant(self) -> Status | None:
        """Advance the sender's participant to VALID; ``None`` on success."""
        assert self.datalayer is not None
        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure
        if self._participant_already_valid(case):
            # A restated VALID is a confirmation, recorded once (RSH-08-002):
            # in a store with no link to latch, the link check above cannot
            # short-circuit, so without this a redelivery appends a rung.
            self.logger.debug(
                "%s: participant already RM.VALID for report '%s'; no new"
                " ParticipantStatus (RSH-08-002)",
                self.name,
                self.report_id,
            )
        else:
            result = BTBridge(datalayer=self.datalayer).execute_with_setup(
                self._status_node,
                actor_id=self.actor_id or "",
                case_id=case_id,
            )
            if result.status != Status.SUCCESS:
                self.feedback_message = (
                    "case-scoped RM.VALID write did not succeed"
                    f" ({result.status.name})"
                )
                self.logger.error("%s: %s", self.name, self.feedback_message)
                return Status.FAILURE

        return None
