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

"""RM transition nodes for the report behavior tree.

Two shapes of RM transition live here, and the difference between them is the
whole point of the module layout:

**Report-phase transitions** (:class:`TransitionRMtoValid`,
:class:`TransitionRMtoInvalid`, :class:`TransitionRMtoClosed`) record the
current RM state on the report's ``VultronReportCaseLink`` record
(BTND-10-006, ADR-0089).  That field is the idempotency source read by
``CheckRMStateValid`` / ``CheckRMStateReceivedOrInvalid``.

**Case-scoped transitions** advance the actor's RM state on
its ``CaseParticipant`` inside a ``VulnerabilityCase``.

``RM.VALID`` is *both*: DUR-07-004 requires an established embargo, which only
exists on a case, and engage-case reads the participant's case-scoped state.  So
``TransitionRMtoValid`` requires the case and performs the case-scoped half
*before* updating the ReportCaseLink field (ID-04-005).  ``RM.INVALID`` and
``RM.CLOSED`` in report phase do not: a receiver may declare a bare report
invalid or closed without ever promoting it to a case.

Every node that *requires* the case reads ``/case_id`` from the blackboard
rather than looking the case up itself; the single lookup site is
:class:`~vultron.core.behaviors.case.nodes.case_lookup.RequireCaseForReport`
(ARCH-15-004).
"""

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM, is_valid_rm_transition

from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.ports.case_persistence import CasePersistence


def _read_report_case_link(
    datalayer: CasePersistence, report_id: str
) -> VultronReportCaseLink | None:
    """Read the ReportCaseLink for *report_id*, or None if absent or mistyped.

    Shared by the report-phase transition nodes and :class:`TransitionRMtoValid`
    so the id derivation and type guard live in one place (CS-22-001).
    """
    link = datalayer.read(VultronReportCaseLink.build_id(report_id))
    return link if isinstance(link, VultronReportCaseLink) else None


class _ReportPhaseRMTransition(DataLayerActionWithPorts):
    """Write the report-phase RM state for one RM state on ReportCaseLink.

    Subclasses set :attr:`_target_rm`.  The RM state is stored on the
    ``VultronReportCaseLink`` record rather than as a deterministic
    ``ParticipantStatus`` latch (BTND-10-006, ADR-0089).

    **Deliberately outside the composed ParticipantStatus evaluator.**
    This node operates on a *report* before a case exists; there is no
    case participant, no VF/D/PXA dimension and no role gate for the
    shared evaluator to apply.  RM adjacency on ``ReportCaseLink.rm_state``
    is the whole rule set that applies here.
    """

    #: Target RM state; set by each concrete subclass.
    _target_rm: RM

    def __init__(
        self,
        report_id: str,
        offer_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize a report-phase RM transition node.

        Args:
            report_id: ID of the VulnerabilityReport whose RM state advances.
            offer_id: ID of the Offer activity that carried the report.
            sender_actor_id: Retained for API compatibility; no longer used
                for state reads or writes (ADR-0089).
            name: Optional custom node name (defaults to the class name).
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id
        self.sender_actor_id = sender_actor_id

    def _get_link(self) -> VultronReportCaseLink | None:
        """Read the ReportCaseLink for this report from the DataLayer."""
        assert self.datalayer is not None
        return _read_report_case_link(self.datalayer, self.report_id)

    def update(self) -> Status:
        """Guard the transition, then update ReportCaseLink.rm_state.

        Returns:
            SUCCESS once the field is written; FAILURE when the DataLayer
            is unavailable, the ReportCaseLink is missing, the transition
            is illegal, or the write raises.
        """
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        link = self._get_link()
        if link is None:
            self.feedback_message = (
                f"ReportCaseLink not found for report '{self.report_id}'"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        current_rm = link.rm_state
        if current_rm != self._target_rm and not is_valid_rm_transition(
            current_rm, self._target_rm
        ):
            self.feedback_message = (
                f"Invalid RM transition {current_rm!r} → {self._target_rm!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            link.rm_state = self._target_rm
            self.datalayer.save(link)
            self.logger.info(
                "RM → %s for report '%s'",
                self._target_rm.name,
                self.report_id,
            )
            return Status.SUCCESS
        except Exception as e:
            self.logger.error(
                "%s: Error transitioning to %s: %s",
                self.name,
                self._target_rm.name,
                e,
            )
            return Status.FAILURE


class TransitionRMtoValid(DataLayerActionWithPorts):
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
    permanently: a same-state ``VALID → VALID`` participant write passes
    validation and the link save retries.  That re-run appends a redundant
    ``RM.VALID`` ``ParticipantStatus`` rung (state converges, history does not
    dedupe); in normal operation ``CheckRMStateValid`` short-circuits the whole
    validate tree once the link is ``VALID``, so this node is not re-entered for
    an already-valid report except on the rare save-retry path.
    """

    def __init__(
        self,
        report_id: str,
        offer_id: str,
        sender_actor_id: str | None = None,
        name: str | None = None,
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
        """
        super().__init__(name=name or "TransitionRMtoValid")
        self.report_id = report_id
        self.offer_id = offer_id  # unused; kept for call-site compatibility
        self.sender_actor_id = sender_actor_id
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

    def update(self) -> Status:
        """Validate the link, advance the participant, then latch the link.

        Returns:
            SUCCESS once both records read ``RM.VALID``; FAILURE when the
            DataLayer is unavailable, the report-phase transition is illegal,
            the case-scoped write does not succeed, or the final link save
            raises.  An absent link advances the participant but is left
            unpersisted, not a failure (issue #3283).
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
        if current_rm != RM.VALID and not is_valid_rm_transition(
            current_rm, RM.VALID
        ):
            self.feedback_message = (
                f"Invalid RM transition {current_rm!r} → {RM.VALID!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # 2. Case-scoped write FIRST (ID-04-005), through the sole
        #    ParticipantStatus writer.
        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        from vultron.core.behaviors.bridge import BTBridge

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
            self.logger.error(
                "%s: Error latching RM.VALID on the report link: %s",
                self.name,
                e,
            )
            return Status.FAILURE


class TransitionRMtoInvalid(_ReportPhaseRMTransition):
    """Transition the report to RM.INVALID in report phase.

    Updates ``ReportCaseLink.rm_state`` to ``RM.INVALID``.
    Deliberately case-**optional**: a receiver may declare a bare report
    invalid before any case exists.

    The matching case-scoped move, when a case does exist, is handled
    via ``CreateParticipantStatusNode``.
    """

    _target_rm = RM.INVALID


class TransitionRMtoClosed(_ReportPhaseRMTransition):
    """Transition the report to RM.CLOSED in report phase.

    Updates ``ReportCaseLink.rm_state`` to ``RM.CLOSED``.
    Used by both the reject-report and close-report trigger workflows.
    Case-**optional** for the same reason as
    :class:`TransitionRMtoInvalid`: a report can be closed without ever having
    been promoted to a case.

    The matching case-scoped move, when a case does exist, is handled
    via ``CreateParticipantStatusNode``.
    """

    _target_rm = RM.CLOSED
