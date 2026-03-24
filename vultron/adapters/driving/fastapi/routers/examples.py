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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import random

from fastapi import APIRouter

from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.wire.as2.vocab.examples import vocab_examples

router = APIRouter(
    prefix="/examples",
    tags=["Examples"],
)


@router.get(
    "/actors",
    response_model=as_Actor,
    response_model_exclude_none=True,
    description="Get an example Actor object.",
    operation_id="examples_get_actor",
)
def get_example_actor() -> as_Actor:
    """
    Get an example Actor object
    """
    options = [
        vocab_examples.finder,
        vocab_examples.vendor,
        vocab_examples.coordinator,
    ]
    func = random.choice(options)

    return func()


@router.post(
    "/actors",
    response_model=as_Actor,
    description="Validate an Actor object.",
    operation_id="examples_validate_actor",
)
def validate_actor(actor: as_Actor) -> as_Actor:
    """Validates an Actor object."""
    return actor


@router.get(
    "/reports",
    response_model=VulnerabilityReport,
    response_model_exclude_none=True,
    description="Get an example Vulnerability Report object.",
    operation_id="examples_get_report",
)
def get_example_report() -> VulnerabilityReport:
    """Returns an example VulnerabilityReport object."""
    return vocab_examples.gen_report()


@router.post(
    "/reports",
    response_model=VulnerabilityReport,
    response_model_exclude_none=True,
    summary="Validate Report object format",
    description="Validates a Vulnerability Report object.",
    operation_id="examples_validate_report",
)
def validate_report(report: VulnerabilityReport) -> VulnerabilityReport:
    """Validates a VulnerabilityReport object."""
    return report


@router.get(
    "/cases",
    response_model=VulnerabilityCase,
    response_model_exclude_none=True,
    description="Get an example Vulnerability Case object.",
    operation_id="examples_get_case",
)
def get_example_case() -> VulnerabilityCase:
    """Returns an example VulnerabilityCase object."""
    return vocab_examples.case()


@router.post(
    "/cases",
    response_model=VulnerabilityCase,
    response_model_exclude_none=True,
    summary="Validate Case object format",
    description="Validates a Vulnerability Case object.",
    operation_id="examples_validate_case",
)
def validate_case(case: VulnerabilityCase) -> VulnerabilityCase:
    """Validates a VulnerabilityCase object."""
    return case


@router.get(
    "/cases/statuses",
    response_model=CaseStatus,
    response_model_exclude_none=True,
    description="Get an example Case Status object.",
    operation_id="examples_get_case_status",
)
def get_example_case_status() -> CaseStatus:
    """Returns an example CaseStatus object."""
    return vocab_examples.case_status()


@router.post(
    "/cases/statuses",
    response_model=CaseStatus,
    response_model_exclude_none=True,
    description="Validates a CaseStatus object.",
    operation_id="examples_validate_case_status",
)
def validate_case_status(case_status: CaseStatus) -> CaseStatus:
    """Validates a CaseStatus object."""
    return case_status


@router.get(
    "/cases/participants",
    response_model=CaseParticipant,
    response_model_exclude_none=True,
    description="Get an example Case Participant object.",
    operation_id="examples_get_participant",
)
def get_example_participant() -> CaseParticipant:
    """Returns an example CaseParticipant object."""
    return vocab_examples.case_participant()


@router.post(
    "/cases/participants",
    response_model=CaseParticipant,
    response_model_exclude_none=True,
    summary="Validate Case Participant object format",
    description="Validates a Case Participant object.",
    operation_id="examples_validate_participant",
)
def validate_participant(participant: CaseParticipant) -> CaseParticipant:
    """Validates a CaseParticipant object."""
    return participant


@router.get(
    "/cases/participants/statuses",
    response_model=ParticipantStatus,
    response_model_exclude_none=True,
    description="Get an example Participant Status object.",
    operation_id="examples_get_participant_status",
)
def get_example_participant_status() -> ParticipantStatus:
    """Returns an example ParticipantStatus object."""
    return vocab_examples.participant_status()


@router.post(
    "/cases/participants/statuses",
    response_model=ParticipantStatus,
    response_model_exclude_none=True,
    description="Validates a ParticipantStatus object.",
    operation_id="examples_validate_participant_status",
)
def validate_participant_status(
    status: ParticipantStatus,
) -> ParticipantStatus:
    """Validates a ParticipantStatus object."""
    return status


@router.get(
    "/cases/embargoes",
    response_model=EmbargoEvent,
    response_model_exclude_none=True,
    description="Get an example Embargo Event object.",
    operation_id="examples_get_embargo",
)
def get_example_embargo() -> EmbargoEvent:
    """Returns an example EmbargoEvent object."""
    return vocab_examples.embargo_event()


@router.post(
    "/cases/embargoes",
    response_model=EmbargoEvent,
    response_model_exclude_none=True,
    summary="Validate Embargo Event object format",
    description="Validates an EmbargoEvent object.",
    operation_id="examples_validate_embargo",
)
def validate_embargo(embargo: EmbargoEvent) -> EmbargoEvent:
    """Validates an EmbargoEvent object."""
    return embargo


@router.get(
    "/notes",
    response_model=as_Note,
    response_model_exclude_none=True,
    description="Get an example Note object.",
    operation_id="examples_get_note",
)
def get_example_note() -> as_Note:
    """
    Get an example Note object
    """
    return vocab_examples.note()


@router.post(
    "/notes",
    response_model=as_Note,
    response_model_exclude_none=True,
    summary="Validate Note object format",
    description="Validates a Note object.",
    operation_id="examples_validate_note",
)
def validate_note(note: as_Note) -> as_Note:
    """Validates a Note object."""
    return note
