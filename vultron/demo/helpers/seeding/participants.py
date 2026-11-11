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

"""Seeding a demo case's participants and embargo directly in a store.

Stands in for the ``CaseProposal`` round-trip the single-server demo mode
cannot run (ADR-0041): :func:`seed_case_participants_for_demo` writes the
vendor, reporter and CaseActor participants and the default embargo the
case-creation tree would have.
"""

import logging

from vultron.config.app import get_config
from vultron.core.behaviors.case.nodes.embargo import creation_time_embargo_id
from vultron.core.behaviors.store_scope import store_for_actor
from vultron.core.models._helpers import (
    authored_times,
    embargo_authored_times,
)
from vultron.core.models.activity_ids import derived_object_id
from vultron.core.models.actor import VultronService, hosted_endpoints
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_duration import (
    actor_default_duration,
    resolve_initial_embargo_duration,
    stored_actor_profile,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.rm import RM
from vultron.demo import wall_clock
from vultron.demo.utils import configured_case_actor_id
from vultron.demo.wall_clock import from_now
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


def _attach(
    case_obj: VulnerabilityCase,
    participant: CaseParticipant,
    dl: CasePersistence,
) -> None:
    """Attach *participant* to *case_obj* and store it, if not stored yet.

    Attached first: attaching writes its consent rows (ADR-0122).
    """
    case_obj.add_participant(participant)
    try:
        dl.create(participant)
    except ValueError:
        pass


def _seed_vendor_participant(case_obj, vendor_actor_id: str, dl) -> None:
    at = wall_clock.now()  # one read for this step (ADR-0176)
    case_id = case_obj.id_
    if vendor_actor_id in case_obj.actor_participant_index:
        return
    # Seed vendor at RM.RECEIVED — the minimum state needed so that the
    # validate-report trigger can advance RECEIVED → VALID and emit the
    # validate_report semanticType to the case-actor ledger.
    #
    # In a multi-server deployment the CaseProposal acceptance round-trip would
    # drive this transition automatically (SubmitReportReceivedUseCase creates
    # the participant at RM.RECEIVED).  In single-server demo mode that
    # round-trip is blocked, so we seed it here as the protocol would have.
    # RM.VALID must NOT be pre-seeded — validate-report must drive that
    # transition so the semanticType appears in the case-actor ledger (issue #2273).
    vendor_p = CaseParticipant(
        attributed_to=vendor_actor_id,
        context=case_id,
        name=f"Vendor participant for {case_id}",
        case_roles=[CVDRole.CASE_OWNER, CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                rm=RmDimension(state=RM.RECEIVED),
                context=case_id,
                attributed_to=vendor_actor_id,
                **authored_times(at),
            ),
        ],
        **authored_times(at),
    )
    _attach(case_obj, vendor_p, dl)
    logger.debug(
        "seed_case_participants_for_demo: added vendor '%s' at RM.RECEIVED",
        vendor_actor_id,
    )


def _seed_reporter_participant(
    case_obj, reporter_actor_id: str | None, dl
) -> None:
    case_id = case_obj.id_
    if not reporter_actor_id:
        return
    if reporter_actor_id in case_obj.actor_participant_index:
        return
    reporter_p = CaseParticipant(
        attributed_to=reporter_actor_id,
        context=case_id,
        name=f"Reporter participant for {case_id}",
        case_roles=[CVDRole.REPORTER],
        **authored_times(wall_clock.now()),
    )
    _attach(case_obj, reporter_p, dl)
    logger.debug(
        "seed_case_participants_for_demo: added reporter '%s'",
        reporter_actor_id,
    )


def _seed_case_actor_participant(case_obj, case_actor_id: str, dl) -> None:
    at = wall_clock.now()  # one read for this step (ADR-0176)
    case_id = case_obj.id_
    if case_actor_id in case_obj.actor_participant_index:
        return

    # Create the CaseActor Service object so that inbox delivery to the
    # CaseActor succeeds.  The record goes in the CaseActor's *own* store,
    # because that is what makes it a hosted actor: the inbox route computes the
    # canonical URI from the path segment and resolves the actor from the store
    # that URI names (ADR-0073), so a copy sitting in the seeding actor's store
    # leaves `POST /actors/case-actor/inbox/` answering `404 Actor not found`
    # and the CaseProposal round-trip never starts.  (Pre-ADR-0073 this wrote to
    # the one shared store, where "some row exists" and "this actor is hosted"
    # were the same thing.)
    #
    # `store_for_actor` rather than a local clone helper: it is the one place
    # that answers "which store belongs to this actor?" (DL-07-005), and the
    # demo seeders drifting from the bridge on that answer is what made the
    # three earlier copies disagree about test doubles.  The seeding actor and
    # the CaseActor are on this container here: the configured CaseActor
    # service URL names this container's own API base (CP-08-009), so the
    # same-authority guard does not fire.
    # One actor per container, not per case (ADR-0088): no `context` naming a
    # case and no `attributed_to`.
    actor_obj = VultronService(
        id_=case_actor_id,
        name="CaseActor",
        **hosted_endpoints(case_actor_id),
        **authored_times(at),
    )
    own_store = store_for_actor(dl, case_actor_id)
    try:
        own_store.create(actor_obj)
    except ValueError:
        pass

    # CaseParticipant needs a distinct ID from the Service object —
    # matching production where RegisterCaseActorParticipantNode creates
    # the participant with a separate UUID attributed to case_actor_id.
    participant_id = derived_object_id(case_actor_id)
    manager_p = CaseParticipant(
        id_=participant_id,
        attributed_to=case_actor_id,
        context=case_id,
        name=f"CaseActor participant for {case_id}",
        case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
        **authored_times(at),
    )
    _attach(case_obj, manager_p, dl)
    logger.debug(
        "seed_case_participants_for_demo: added CaseActor '%s'",
        case_actor_id,
    )


def _seed_active_embargo(case_obj, dl) -> None:
    """Seed the active embargo ``InitializeDefaultEmbargoNode`` would have made.

    The duration is resolved the way the case-creation tree resolves it
    (EP-04-005 through EP-04-007): the ``embargo_policy`` on the owner's
    profile if it has published one, else the protocol default.  The tree
    reads that profile from the ``Create(CaseProposal)`` it received
    (CP-01-010); a seeded case had no such Create, so the owner's own record
    in *dl* stands in for it — the seeder is run on the owner's store.  A
    seeded case carries no sender proposal.  ``EmbargoEvent`` has no default
    duration (EP-04-010, #3404), so this is stated here rather than inherited.

    Raises:
        VultronNotFoundError: when *dl* holds no actor record for the owner.
    """
    at = wall_clock.now()  # one read for this step (ADR-0176)
    case_id = case_obj.id_
    if case_obj.active_embargo:
        return
    owner_id = case_obj.attributed_to
    resolved = resolve_initial_embargo_duration(
        sender_proposal=None,
        actor_default=actor_default_duration(
            stored_actor_profile(dl, owner_id)
        ),
        protocol_default=get_config().actor.protocol_default_embargo_duration,
    )
    embargo = EmbargoEvent(
        id_=creation_time_embargo_id(case_id),
        context=case_id,
        end_time=from_now(resolved.duration),
        **embargo_authored_times(at),
    )
    # The EM write goes through the lifecycle service like the tree's own
    # (EMB-18-001): one save at EM.ACTIVE, with the owner's consent recorded
    # and the owner's consent row seeded AGREED as the creation arm does (CM-14-005).
    EmbargoLifecycle(persistence=dl).initialize_creation_embargo(
        case_id=case_id, embargo=embargo, actor_id=owner_id
    )
    logger.debug(
        "seed_case_participants_for_demo: seeded active embargo for '%s'",
        case_id,
    )


def seed_case_participants_for_demo(
    case_id: str,
    vendor_actor_id: str,
    reporter_actor_id: str | None,
    report_id: str | None,
    dl: CasePersistence,
) -> None:
    """Seed vendor, reporter, and CaseActor participants on an ADR-0041 case.

    Under ADR-0041, the CaseActor normally creates participants via
    ``case_proposal_received_tree`` when it accepts a ``CaseProposal``.
    This helper compensates by seeding participants directly in the DataLayer
    and setting ``EM.ACTIVE`` so the demo milestone checks pass.

    It is safe to call this multiple times for the same case — idempotency
    guards on ``actor_participant_index`` prevent duplicate records.

    Args:
        case_id: Full URI of the ``VulnerabilityCase``.
        vendor_actor_id: Full URI of the vendor actor (seeded as CASE_OWNER + VENDOR).
        reporter_actor_id: Full URI of the reporter actor, or ``None`` to skip.
        report_id: Report URI. Unused: the CaseActor identity does not vary
            by report (#1872); it comes from configuration only (CP-08-009).
        dl: The store to seed — required, and specifically the store of the
            actor whose replica of the case is being set up.  There is no
            default: it used to fall back to ``get_shared_dl()``, which ADR-0073
            deletes, and no defensible default replaced it.  "Which actor's
            replica?" is exactly the question a shared DataLayer let callers skip,
            and the participants seeded here are per-replica state.

    Raises:
        DemoCaseActorUnconfiguredError: No CaseActor service URL is
            configured. Raised before any write, so the store is unchanged.
    """
    del report_id  # the CaseActor identity does not vary by report (#1872)
    # Resolve the CaseActor first: an unconfigured URL must fail before the
    # vendor and reporter records are written (CP-08-009).
    case_actor_id = configured_case_actor_id()
    case_obj = dl.read(case_id)
    if not isinstance(case_obj, VulnerabilityCase):
        logger.warning(
            "seed_case_participants_for_demo: case '%s' not found", case_id
        )
        return

    _seed_vendor_participant(case_obj, vendor_actor_id, dl)
    _seed_reporter_participant(case_obj, reporter_actor_id, dl)
    _seed_case_actor_participant(case_obj, case_actor_id, dl)
    # Participants first: the embargo write reads the case from the store
    # and records consent on the participants it indexes.
    dl.save(case_obj)
    _seed_active_embargo(case_obj, dl)
