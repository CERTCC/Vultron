"""
Vultron API Object Examples
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

import random
from datetime import timedelta

from fastapi import APIRouter

from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.embargo_policy import as_EmbargoPolicy
from vultron.wire.as2.vocab.objects.vultron_actor import (
    as_VultronApplication,
    as_VultronGroup,
    as_VultronOrganization,
    as_VultronPerson,
    as_VultronService,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)
from vultron.wire.as2.vocab.examples import vocab_examples

_ACTORS_BASE = "https://example.org/actors"
_PREFERRED_DURATION = timedelta(days=90)


def _embargo_policy(actor_id: str) -> as_EmbargoPolicy:
    """Build a minimal as_EmbargoPolicy for the given actor ID."""
    return as_EmbargoPolicy(
        actor_id=actor_id,
        inbox=f"{actor_id}/inbox",
        preferred_duration=_PREFERRED_DURATION,
    )


router = APIRouter(
    prefix="/examples",
    tags=["Examples"],
)


@router.get(
    "/actors",
    response_model=as_Actor,
    description="Get an example Actor object.",
    operation_id="examples_get_actor",
)
def get_example_actor() -> AS2JSONResponse:
    """
    Get an example Actor object
    """
    options = [
        vocab_examples.finder,
        vocab_examples.vendor,
        vocab_examples.coordinator,
    ]
    func = random.choice(options)

    return AS2JSONResponse(func())


@router.post(
    "/actors",
    response_model=as_Actor,
    description="Validate an Actor object.",
    operation_id="examples_validate_actor",
)
def validate_actor(actor: as_Actor) -> AS2JSONResponse:
    """Validates an Actor object."""
    return AS2JSONResponse(actor)


@router.get(
    "/actors/person",
    response_model=as_VultronPerson,
    description="Get an example as_VultronPerson actor object.",
    operation_id="examples_get_actor_person",
)
def get_example_actor_person() -> AS2JSONResponse:
    """Returns an example as_VultronPerson actor with an inline as_EmbargoPolicy."""
    actor_id = f"{_ACTORS_BASE}/alice"
    return AS2JSONResponse(
        as_VultronPerson(
            id_=actor_id,
            name="Alice (Example Person)",
            embargo_policy=_embargo_policy(actor_id),
        )
    )


@router.get(
    "/actors/organization",
    response_model=as_VultronOrganization,
    description="Get an example as_VultronOrganization actor object.",
    operation_id="examples_get_actor_organization",
)
def get_example_actor_organization() -> AS2JSONResponse:
    """Returns an example as_VultronOrganization actor with an inline as_EmbargoPolicy."""
    actor_id = f"{_ACTORS_BASE}/acme-inc"
    return AS2JSONResponse(
        as_VultronOrganization(
            id_=actor_id,
            name="ACME Inc. (Example Organization)",
            embargo_policy=_embargo_policy(actor_id),
        )
    )


@router.get(
    "/actors/service",
    response_model=as_VultronService,
    description="Get an example as_VultronService actor object.",
    operation_id="examples_get_actor_service",
)
def get_example_actor_service() -> AS2JSONResponse:
    """Returns an example as_VultronService actor with an inline as_EmbargoPolicy."""
    actor_id = f"{_ACTORS_BASE}/vultron-bot"
    return AS2JSONResponse(
        as_VultronService(
            id_=actor_id,
            name="Vultron Bot (Example Service)",
            embargo_policy=_embargo_policy(actor_id),
        )
    )


@router.get(
    "/actors/application",
    response_model=as_VultronApplication,
    description="Get an example as_VultronApplication actor object.",
    operation_id="examples_get_actor_application",
)
def get_example_actor_application() -> AS2JSONResponse:
    """Returns an example as_VultronApplication actor with an inline as_EmbargoPolicy."""
    actor_id = f"{_ACTORS_BASE}/vultron-app"
    return AS2JSONResponse(
        as_VultronApplication(
            id_=actor_id,
            name="Vultron App (Example Application)",
            embargo_policy=_embargo_policy(actor_id),
        )
    )


@router.get(
    "/actors/group",
    response_model=as_VultronGroup,
    description="Get an example as_VultronGroup actor object.",
    operation_id="examples_get_actor_group",
)
def get_example_actor_group() -> AS2JSONResponse:
    """Returns an example as_VultronGroup actor with an inline as_EmbargoPolicy."""
    actor_id = f"{_ACTORS_BASE}/security-team"
    return AS2JSONResponse(
        as_VultronGroup(
            id_=actor_id,
            name="Security Team (Example Group)",
            embargo_policy=_embargo_policy(actor_id),
        )
    )


@router.get(
    "/reports",
    response_model=as_VulnerabilityReport,
    description="Get an example Vulnerability Report object.",
    operation_id="examples_get_report",
)
def get_example_report() -> AS2JSONResponse:
    """Returns an example as_VulnerabilityReport object."""
    return AS2JSONResponse(vocab_examples.gen_report())


@router.post(
    "/reports",
    response_model=as_VulnerabilityReport,
    summary="Validate Report object format",
    description="Validates a Vulnerability Report object.",
    operation_id="examples_validate_report",
)
def validate_report(report: as_VulnerabilityReport) -> AS2JSONResponse:
    """Validates a as_VulnerabilityReport object."""
    return AS2JSONResponse(report)


@router.get(
    "/cases",
    response_model=as_VulnerabilityCase,
    description="Get an example Vulnerability Case object.",
    operation_id="examples_get_case",
)
def get_example_case() -> AS2JSONResponse:
    """Returns an example as_VulnerabilityCase object."""
    return AS2JSONResponse(vocab_examples.case())


@router.post(
    "/cases",
    response_model=as_VulnerabilityCase,
    summary="Validate Case object format",
    description="Validates a Vulnerability Case object.",
    operation_id="examples_validate_case",
)
def validate_case(case: as_VulnerabilityCase) -> AS2JSONResponse:
    """Validates a as_VulnerabilityCase object."""
    return AS2JSONResponse(case)


@router.get(
    "/cases/statuses",
    response_model=as_CaseStatus,
    description="Get an example Case Status object.",
    operation_id="examples_get_case_status",
)
def get_example_case_status() -> AS2JSONResponse:
    """Returns an example as_CaseStatus object."""
    return AS2JSONResponse(vocab_examples.case_status())


@router.post(
    "/cases/statuses",
    response_model=as_CaseStatus,
    description="Validates a as_CaseStatus object.",
    operation_id="examples_validate_case_status",
)
def validate_case_status(case_status: as_CaseStatus) -> AS2JSONResponse:
    """Validates a as_CaseStatus object."""
    return AS2JSONResponse(case_status)


@router.get(
    "/cases/participants",
    response_model=as_CaseParticipant,
    description="Get an example Case Participant object.",
    operation_id="examples_get_participant",
)
def get_example_participant() -> AS2JSONResponse:
    """Returns an example as_CaseParticipant object."""
    return AS2JSONResponse(vocab_examples.case_participant())


@router.post(
    "/cases/participants",
    response_model=as_CaseParticipant,
    summary="Validate Case Participant object format",
    description="Validates a Case Participant object.",
    operation_id="examples_validate_participant",
)
def validate_participant(participant: as_CaseParticipant) -> AS2JSONResponse:
    """Validates a as_CaseParticipant object."""
    return AS2JSONResponse(participant)


@router.get(
    "/cases/participants/statuses",
    response_model=as_ParticipantStatus,
    description="Get an example Participant Status object.",
    operation_id="examples_get_participant_status",
)
def get_example_participant_status() -> AS2JSONResponse:
    """Returns an example as_ParticipantStatus object."""
    return AS2JSONResponse(vocab_examples.participant_status())


@router.post(
    "/cases/participants/statuses",
    response_model=as_ParticipantStatus,
    description="Validates a as_ParticipantStatus object.",
    operation_id="examples_validate_participant_status",
)
def validate_participant_status(
    status: as_ParticipantStatus,
) -> AS2JSONResponse:
    """Validates a as_ParticipantStatus object."""
    return AS2JSONResponse(status)


@router.get(
    "/cases/embargoes",
    response_model=as_EmbargoEvent,
    description="Get an example Embargo Event object.",
    operation_id="examples_get_embargo",
)
def get_example_embargo() -> AS2JSONResponse:
    """Returns an example as_EmbargoEvent object."""
    return AS2JSONResponse(vocab_examples.embargo_event())


@router.post(
    "/cases/embargoes",
    response_model=as_EmbargoEvent,
    summary="Validate Embargo Event object format",
    description="Validates an as_EmbargoEvent object.",
    operation_id="examples_validate_embargo",
)
def validate_embargo(embargo: as_EmbargoEvent) -> AS2JSONResponse:
    """Validates an as_EmbargoEvent object."""
    return AS2JSONResponse(embargo)


@router.get(
    "/notes",
    response_model=as_Note,
    description="Get an example Note object.",
    operation_id="examples_get_note",
)
def get_example_note() -> AS2JSONResponse:
    """
    Get an example Note object
    """
    return AS2JSONResponse(vocab_examples.note())


@router.post(
    "/notes",
    response_model=as_Note,
    summary="Validate Note object format",
    description="Validates a Note object.",
    operation_id="examples_validate_note",
)
def validate_note(note: as_Note) -> AS2JSONResponse:
    """Validates a Note object."""
    return AS2JSONResponse(note)
