"""Use cases for vulnerability case activities."""

import logging

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant import (
    EnsureReporterParticipantAtAcceptedNode,
)
from vultron.core.models.events.case import CreateCaseReceivedEvent
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import CasePersistence

from vultron.core.use_cases._helpers import (
    _resolve_case_manager_id,
    resolve_receiving_actor_id,
)

from ._helpers import (
    _find_report_case_link,
    _store_embedded_embargo,
    _store_embedded_participants,
)

logger = logging.getLogger(__name__)


class CreateCaseReceivedUseCase:
    """Process a bootstrap ``Create(VulnerabilityCase)`` from a remote actor.

    Receiving this message means *someone else* created the case and is
    notifying us.  We do NOT create our own case infrastructure here.

    Bootstrap trust path (CBT-01-005 / CBT-01-006):
    1. Locate the ``VultronReportCaseLink`` for any report listed in the case.
    2. Validate that the sender matches ``link.trusted_case_creator_id``.
    3. Extract the ``CaseActor`` ID from the ``CASE_MANAGER`` participant.
    4. Seed a local replica of the case via the case-replica BT.
    5. Update the link with ``case_id`` and ``trusted_case_actor_id``.
    """

    def __init__(
        self, dl: CasePersistence, request: CreateCaseReceivedEvent
    ) -> None:
        self._dl = dl
        self._request: CreateCaseReceivedEvent = request

    def execute(self) -> None:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id

        if request.case is None:
            logger.warning(
                "create_case_received: no case domain object in event for "
                "case '%s'",
                case_id,
            )
            return

        if case_id is None:
            logger.warning(
                "create_case_received: case_id missing in event — skipping"
            )
            return

        case_obj_raw = request.case
        if not isinstance(case_obj_raw, VulnerabilityCase):
            logger.warning(
                "create_case_received: case object for case '%s' does not "
                "is not a VulnerabilityCase — skipping",
                case_id,
            )
            return
        case_obj: VulnerabilityCase = case_obj_raw
        link = _find_report_case_link(actor_id, self._dl)

        if link is not None:
            # Bootstrap trust path — CBT-01-005 / CBT-01-006
            self._handle_bootstrap(actor_id, case_id, case_obj, link)
        else:
            # Non-vendor participant path (ADR-0041 AC-5)
            self._handle_direct_participant_bootstrap(
                actor_id, case_id, case_obj
            )

    def _handle_direct_participant_bootstrap(
        self,
        actor_id: str,
        case_id: str,
        case_obj: VulnerabilityCase,
    ) -> None:
        """Seed the case replica when receiver is a non-vendor participant.

        Under ADR-0041 AC-5, CaseActor bootstraps reporters/finders directly by
        including them in the ``to`` field of ``Create(VulnerabilityCase)``.
        The reporter side has no ``VultronReportCaseLink``, so the standard
        trust path is unavailable.  We fall back to trusting the CaseActor
        identity embedded in the case snapshot: only accept when the sender's
        actor ID matches the CASE_MANAGER participant in the snapshot.
        """
        case_manager_id = _resolve_case_manager_id(case_obj, self._dl)
        if case_manager_id is not None and case_manager_id == actor_id:
            existing = self._dl.read(case_id)
            if not isinstance(existing, VulnerabilityCase):
                try:
                    self._dl.create(case_obj)
                    logger.info(
                        "create_case_received: stored case '%s' replica for "
                        "non-vendor participant from CaseActor '%s' (ADR-0041 AC-5)",
                        case_id,
                        actor_id,
                    )
                except ValueError:
                    logger.info(
                        "create_case_received: case '%s' persisted concurrently"
                        " — idempotent",
                        case_id,
                    )
            _store_embedded_participants(case_obj, self._dl, case_id)
            _store_embedded_embargo(case_obj, self._dl, case_id)
        else:
            logger.info(
                "create_case_received: no ReportCaseLink for case '%s' and "
                "sender '%s' is not the CaseActor — skipping",
                case_id,
                actor_id,
            )

    def _handle_bootstrap(
        self,
        actor_id: str,
        case_id: str,
        case_obj: VulnerabilityCase,
        link: VultronReportCaseLink,
    ) -> None:
        """Validate trust and seed the case replica."""
        # CBT-01-005: sender must match the actor we sent the report to
        if link.trusted_case_creator_id is not None:
            if actor_id != link.trusted_case_creator_id:
                logger.warning(
                    "create_case_received: bootstrap rejected for case '%s' — "
                    "sender does not match trusted case creator "
                    "(CBT-01-005)",
                    case_id,
                )
                return
        else:
            logger.warning(
                "create_case_received: no trusted_case_creator_id in link "
                "for case '%s'; accepting bootstrap unchecked",
                case_id,
            )

        # CBT-01-003: extract CaseActor from CASE_MANAGER participant
        case_actor_id = _resolve_case_manager_id(case_obj, self._dl)
        if case_actor_id is None:
            logger.warning(
                "create_case_received: no CASE_MANAGER participant found in "
                "bootstrap snapshot for case '%s'; Announce validation will "
                "be bypassed",
                case_id,
            )

        logger.info(
            "create_case_received: bootstrap accepted for case '%s' from "
            "'%s'; seeding replica (CBT-01-006)",
            case_id,
            actor_id,
        )

        # Seed the local case replica
        # Idempotency guard (CBT-01-006, ID-04-004)
        existing = self._dl.read(case_id)
        if isinstance(existing, VulnerabilityCase):
            logger.info(
                "create_case_received: case '%s' already exists as replica "
                "— skipping re-seed",
                case_id,
            )
        else:
            try:
                self._dl.create(case_obj)
                logger.info(
                    "create_case_received: replica case '%s' persisted",
                    case_id,
                )
            except ValueError:
                logger.info(
                    "create_case_received: case '%s' persisted concurrently "
                    "— idempotent",
                    case_id,
                )

        # CBT-01-006: persist trust anchors in the link
        link.case_id = case_id
        link.trusted_case_actor_id = case_actor_id
        self._dl.save(link)
        logger.info(
            "create_case_received: ReportCaseLink updated with case_id='%s' "
            "and trusted_case_actor_id='%s' (CBT-01-006)",
            case_id,
            case_actor_id,
        )

        # CBT-05-005: store any embedded participant objects so that BT nodes
        # (``CheckParticipantExists``, ``AppendParticipantStatusNode``) can
        # find them by UUID via ``datalayer.read(participant_id)``.
        # This must happen regardless of the idempotency guard above because
        # the inbox router may have already seeded the case before dispatch.
        _store_embedded_participants(case_obj, self._dl, case_id)
        _store_embedded_embargo(case_obj, self._dl, case_id)

        # #589: when participants arrive as bare string IDs (the common case),
        # _store_embedded_participants cannot create records for them.  Ensure
        # the reporter's own participant is seeded at RM.ACCEPTED — inferred
        # from the fact that they submitted a report.  This is a protocol-
        # significant RM state transition, so it runs via BTBridge (BT-15-001).
        # The *receiving* actor, not the sender (BT-17-005). `actor_id` here is
        # the case creator, deliberately so for `_find_report_case_link` above,
        # but the node seeds the reporter's participant into the receiver's own
        # replica — and under ADR-0073 the executing actor selects that store, so
        # passing the sender would look for the report in the creator's store and
        # find nothing.
        BTBridge(datalayer=self._dl).execute_with_setup(
            tree=EnsureReporterParticipantAtAcceptedNode(
                link=link,
                case_obj=case_obj,
                case_id=case_id,
            ),
            actor_id=resolve_receiving_actor_id(
                self._dl, self._request.receiving_actor_id
            ),
        )
