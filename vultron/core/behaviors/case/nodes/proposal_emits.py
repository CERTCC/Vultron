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


"""Outbound-activity emit leaf nodes for the CaseProposal received tree.

Queue ``Accept(CaseProposal)`` and ``Create(VulnerabilityCase)`` to the
CaseActor outbox. Composed by ``create_case_proposal_received_tree``
(BTND-07-003).
"""

import logging
from typing import Any

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.case.nodes.proposal_announcement import (
    announced_case_id,
    create_case_activity_id,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.helpers.emit import _EmitSingleActivityBase
from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_register import carry_embargo_inline
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.errors import (
    VultronError,
    VultronNotFoundError,
    VultronProtocolViolationError,
    VultronValidationError,
)

logger = logging.getLogger(__name__)


class EmitAcceptCaseProposalNode(_EmitSingleActivityBase):
    """Build Accept(CaseProposal), store it, and queue it to the outbox.

    Sets ``accept_activity_id`` on the blackboard so the downstream
    ``EmitCreateVulnerabilityCaseNode`` can set the causal ``in_reply_to``
    link on ``Create(VulnerabilityCase)`` (CP-05-003, ADR-0045).

    Reads ``case_id`` from the blackboard (written by either
    ``LoadExistingCaseNode`` or ``CreateCaseFromProposalNode``) and
    sets ``result`` on the ``Accept`` activity to that URI.  For a
    duplicate proposal, this carries the existing-case reference required
    by CP-05-006 AC-2.  For a first-time proposal, it ties the Accept to
    the newly-created case.

    Failure here returns FAILURE so the Sequence aborts before the
    Create(VulnerabilityCase) is sent — the report receiver should not receive an
    unacknowledged case (BT-14-001).
    """

    def __init__(
        self,
        proposal_id: str,
        proposer_uri: str,
        proposal_dict: dict | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._proposer_uri = proposer_uri
        # proposal_dict is the wire-serialised proposal (model_dump(by_alias=True)).
        # The factory embeds it inline (CP-05-009, AKM-03-003); without it there
        # is nothing to embed, so the emit fails rather than sending a bare id.
        self._proposal_dict = proposal_dict

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "accept_activity_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "accept_activity_id": "/accept_activity_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str | None = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if (f := self._require_factory()) is not None:
            logger.error("%s: %s", self.name, self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None
        if self._proposal_dict is None:
            self.feedback_message = (
                f"Accept(CaseProposal) for '{self._proposal_id}' has no"
                " proposal to embed (CP-05-009, AKM-03-003)"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case_id = self._case_id_bb

        # The adapter builds, persists, and seals the Accept, so the body the
        # outbox delivers is the body the factory produced (VM-08-003).
        try:
            activity_id, blob = (
                self.trigger_activity_factory.accept_case_proposal(
                    actor=self.actor_id,
                    proposal=self._proposal_dict,
                    to=[self._proposer_uri],
                    result=case_id,
                )
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Accept(CaseProposal) activity creation failed: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # The Accept's id is derived from the proposal, so a redelivery names
        # the Accept its first delivery built and re-sends it unchanged
        # (CP-05-006).  A copy still waiting in the outbox already is that
        # re-send, and the outbox does not queue it again (OX-06-002,
        # ID-04-004).  Route through the shared emit seam (OX-14-001,
        # ASK-04-008; ADR-0073: the queue lives in the owning actor's store).
        if self._emit_through_seam(activity_id, blob):
            logger.info(
                "%s: Queued Accept(CaseProposal) '%s' to outbox for report"
                " receiver '%s'",
                self.name,
                activity_id,
                self._proposer_uri,
            )
        else:
            logger.info(
                "%s: Accept(CaseProposal) '%s' is still queued — not queueing"
                " it again (CP-05-006)",
                self.name,
                activity_id,
            )
        self._set_output("accept_activity_id", activity_id)
        return Status.SUCCESS


class EmitCreateVulnerabilityCaseNode(_EmitSingleActivityBase):
    """Build Create(VulnerabilityCase) for the report receiver and queue it.

    Reads ``case_id`` and ``accept_activity_id`` from the blackboard, and
    writes ``create_case_activity_id``: ``CommitNativeLedgerEntriesNode``
    commits this activity as the case's genesis entry, so the case's
    creation is one activity, delivered and ledgered (CLP-07-011).  The
    activity carries the full inline case (participants, active embargo and
    reports materialised, ADR-0041 AC-5), ``context`` = the case URI and
    ``in_reply_to`` = the ``Accept`` URI (CP-05-003, ADR-0045).  Its id is
    derived from the proposal (``create_case_activity_id``), so a redelivered
    proposal names the activity its first delivery queued (CP-05-005, #4146).

    The node runs inside the case-creation ``ActTransaction`` (ADR-0146): if
    the ``Create`` cannot be queued, the ``Accept`` and the case roll back
    with it.  Once the act commits, the durable outbox holds the ``Create``
    and retries its delivery (OX-13, CP-05-011); no separate marker is kept.

    Returns SUCCESS without queueing when the proposal's ``Create`` is already
    stored for this case, and FAILURE when it is stored for another case —
    the sender reused the proposal id (CP-05-005) — or when either blackboard
    key or the case is missing.
    """

    def __init__(
        self,
        proposal_id: str,
        owner_uri: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._proposal_id = proposal_id
        self._owner_uri = owner_uri
        self._case_id_bb: str | None = None
        self._accept_activity_id_bb: str | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        "accept_activity_id": PortInformation(data_type=str, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "create_case_activity_id": PortInformation(
            data_type=str, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "accept_activity_id": "/accept_activity_id",
            "create_case_activity_id": "/create_case_activity_id",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None
        try:
            self._accept_activity_id_bb = self.get_input("accept_activity_id")
        except (NoDataAvailable, NotImplementedError):
            self._accept_activity_id_bb = None

    def _build_case_object(
        self, raw_case: VulnerabilityCase
    ) -> VulnerabilityCase:
        assert self.datalayer is not None
        # Materialise each participant ref so store_embedded_participants
        # on the owner's side receives full objects, not bare ID strings (AC-5).
        # The owner seeds from this Create before it trusts the CASE_MANAGER,
        # so the records travel inline (CP-09-004): a participant this store
        # cannot read is refused here rather than sent as a bare id, which the
        # owner would refuse anyway (CBT-05-008).
        materialized: list[Any] = []
        for ref in raw_case.case_participants:
            if isinstance(ref, str):
                p_obj = self.datalayer.read(ref)
                if p_obj is None:
                    raise VultronValidationError(
                        f"case '{raw_case.id_}' names participant '{ref}',"
                        " which this store cannot read, so the"
                        " Create(VulnerabilityCase) cannot carry it inline"
                        " (CP-09-004, CBT-05-008)"
                    )
                materialized.append(p_obj)
            else:
                materialized.append(ref)
        updates: dict[str, Any] = {"case_participants": materialized}
        # Carry the active embargo inline too: a recipient refuses a case
        # naming an embargo its own store cannot read (EMB-18-003), and the
        # CASE_MANAGER minted this one, so no recipient holds it yet.  Raises
        # when this store cannot read it — sending the bare id would only
        # hand every recipient a case it must refuse.
        if isinstance(raw_case.active_embargo, str):
            try:
                embargo = read_embargo_event(
                    self.datalayer, raw_case.active_embargo
                )
            except (VultronNotFoundError, VultronValidationError) as exc:
                raise VultronValidationError(
                    f"case '{raw_case.id_}' names active embargo"
                    f" '{raw_case.active_embargo}', which this store cannot"
                    " read, so the Create(VulnerabilityCase) cannot carry it"
                    f" inline (EMB-18-003): {exc}"
                ) from exc
            updates["embargo_register"] = carry_embargo_inline(
                raw_case.embargo_register, embargo
            )
        # Carry the full reports inline (AKM-02-004, ISSUE-2134).  The owner
        # holds the report it proposed, so its extractor keeps only the ids.
        # The reports ride on the copy, so the Create renders as one object
        # graph: under ``vulnerabilityReports``, with no ``@context``
        # restated below the Create's own (VM-10-005, #6046).
        updates["vulnerability_reports"] = [
            self._inline_report(raw_case.id_, ref)
            for ref in raw_case.vulnerability_reports
        ]
        return raw_case.model_copy(update=updates)

    def _inline_report(
        self, case_id: str, report_ref: str | VulnerabilityReport
    ) -> str | VulnerabilityReport:
        """The report *report_ref* names, or its id when this store lacks it."""
        assert self.datalayer is not None
        if not isinstance(report_ref, str):
            return report_ref
        r_obj = self.datalayer.read(report_ref)
        if isinstance(r_obj, VulnerabilityReport):
            return r_obj
        # A proposal that did not inline its report (CP-01-004) still makes a
        # case here (ADR-0041 AC-2); the owner holds the report it proposed,
        # so the id stays.
        logger.warning(
            "%s: case '%s' names report '%s', which this store cannot read,"
            " so the Create carries its id, not the object; the proposal did"
            " not inline it (CP-01-004)",
            self.name,
            case_id,
            report_ref,
        )
        return report_ref

    def _check_announced(self, case_id: str) -> Status | None:
        """FAILURE when the derived id holds a Create for another case (or no
        Create at all), SUCCESS when this case was already announced, and
        ``None`` when it was not announced yet."""
        assert self.datalayer is not None
        violation: str | None = None
        try:
            announced = announced_case_id(self.datalayer, self._proposal_id)
        except VultronProtocolViolationError as exc:
            announced, violation = None, str(exc)
        if announced is not None and announced != case_id:
            violation = (
                f"proposal '{self._proposal_id}' already announced case"
                f" '{announced}', not '{case_id}': the sender reused the"
                " proposal id, so this case cannot be announced (CP-05-005)"
            )
        if violation is not None:
            self.feedback_message = violation
            logger.error("%s: %s", self.name, violation)
            return Status.FAILURE
        if announced is None:
            return None
        # Already built under the derived id: that Create is still the one
        # the genesis entry records, should it not be committed yet
        # (CLP-07-011).
        self._set_output(
            "create_case_activity_id",
            create_case_activity_id(self._proposal_id),
        )
        logger.info(
            "%s: Create(VulnerabilityCase) of case '%s' for proposal '%s' was"
            " already queued — not announcing the case again (CP-05-005)",
            self.name,
            case_id,
            self._proposal_id,
        )
        return Status.SUCCESS

    def _render_create(
        self, case: VulnerabilityCase, accept_activity_id: str
    ) -> dict[str, Any] | Status:
        """Return the Create's AS2 rendering, or FAILURE when the case names
        an active embargo (EMB-18-003) or a participant this store cannot
        read, so the Create cannot carry it inline (CP-09-004)."""
        assert self.actor_id is not None
        try:
            case_object = self._build_case_object(case)
        except (VultronNotFoundError, VultronValidationError) as exc:
            # Each refusal in _build_case_object names its own cause and
            # requirement, so the message cites only the one that fired.
            self.feedback_message = f"Invariant violation: {exc}"
            logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        # The report receiver (the Case Owner) is the only addressee
        # (CBT-01-010, CM-22-006): it introduces the CASE_MANAGER to the
        # reporter with its own Create(VulnerabilityCase) (CBT-01-001,
        # ADR-0132).  The reporter never addressed this actor, so a Create from
        # it would give the reporter nothing to check the sender against.
        # CP-05-003 / ADR-0045: context = case URI (deferral routing key);
        # in_reply_to = Accept URI (causal antecedent, AS2-correct field).
        create_activity = VultronCreateCaseActivity(
            id_=create_case_activity_id(self._proposal_id),
            actor=self.actor_id,
            object_=case_object,
            context=case.id_,
            in_reply_to=accept_activity_id,
            to=[self._owner_uri],
        )
        # ``create_activity`` is a core-branch object, so its wire shape comes
        # from the port (ARCH-20-001).
        return self._require_wire_render_port().render(create_activity)

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._case_id_bb
        if not isinstance(case_id, str):
            self.feedback_message = "case_id not found in blackboard"
            return Status.FAILURE
        if (announced := self._check_announced(case_id)) is not None:
            return announced

        accept_activity_id = self._accept_activity_id_bb
        if not isinstance(accept_activity_id, str):
            self.feedback_message = (
                "accept_activity_id not found in blackboard"
            )
            return Status.FAILURE

        # Regime 1 (ADR-0087, #3101): the CaseActor authored this case upstream
        # in the same tree, so an absent case is an anomaly, not a skip.
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure
        payload = self._render_create(case, accept_activity_id)
        if isinstance(payload, Status):
            return payload

        if (f := self._require_factory()) is not None:
            logger.error("%s: %s", self.name, self.feedback_message)
            return f
        assert self.trigger_activity_factory is not None

        # The adapter rebuilds the prepared activity, persists it under its
        # proposal-derived id, and seals the body the outbox will deliver
        # (VM-08-003).
        try:
            activity_id, _blob = (
                self.trigger_activity_factory.emit_prepared_create_case(
                    payload
                )
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Could not emit Create(VulnerabilityCase) for proposal"
                f" '{self._proposal_id}': {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        try:
            # Route through the shared emit seam (OX-14-001, ASK-04-008).
            # emit_prepared_create_case already sealed the body, so no
            # captured dict is passed here.
            self._emit_through_seam(activity_id, "")
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.feedback_message = (
                f"Failed to enqueue Create(VulnerabilityCase) to outbox: {exc}"
            )
            logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # The genesis entry records this same activity (CLP-07-011).
        self._set_output("create_case_activity_id", activity_id)
        logger.info(
            "%s: Queued Create(VulnerabilityCase) '%s' from proposal '%s'",
            self.name,
            activity_id,
            self._proposal_id,
        )
        return Status.SUCCESS
