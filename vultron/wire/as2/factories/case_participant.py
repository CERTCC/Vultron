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
"""
Factory functions for outbound Vultron case-participant activities.

These are the sole public construction API for activities involving
``CaseParticipant`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

import logging

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _AddStatusToParticipantActivity,
    _CreateParticipantActivity,
    _CreateStatusForParticipantActivity,
    _RemoveParticipantFromCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    CaseParticipant,
    CaseParticipantRef,
)
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCaseRef,
)

logger = logging.getLogger(__name__)


def create_participant_activity(
    participant: CaseParticipant,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Create:
    """Build a Create(CaseParticipant).

    The internal class automatically generates a descriptive ``name``
    field if one is not provided.

    Args:
        participant: The ``CaseParticipant`` being created.
        target: The ``VulnerabilityCase`` (or its URI) this participant
            is being created for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Create`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _CreateParticipantActivity(
            object_=participant, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "create_participant_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "create_participant_activity: invalid arguments"
        ) from exc


def create_status_for_participant_activity(
    status: ParticipantStatus,
    target: CaseParticipantRef | None = None,
    **kwargs,
) -> as_Create:
    """Build a Create(ParticipantStatus, target=CaseParticipant).

    Args:
        status: The ``ParticipantStatus`` being created.
        target: The ``CaseParticipant`` (or its URI) for whom the
            status is being created.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Create`` whose ``object_`` is the status.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _CreateStatusForParticipantActivity(
            object_=status, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "create_status_for_participant_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "create_status_for_participant_activity: invalid arguments"
        ) from exc


def add_status_to_participant_activity(
    status: ParticipantStatus,
    target: CaseParticipantRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(ParticipantStatus, target=CaseParticipant).

    Args:
        status: The ``ParticipantStatus`` to add.
        target: The ``CaseParticipant`` (or its URI) to which the
            status is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the status.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddStatusToParticipantActivity(
            object_=status, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_status_to_participant_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_status_to_participant_activity: invalid arguments"
        ) from exc


def add_participant_to_case_activity(
    participant: CaseParticipant,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(CaseParticipant, target=VulnerabilityCase).

    Args:
        participant: The ``CaseParticipant`` to add to the case.
        target: The ``VulnerabilityCase`` (or its URI) to which the
            participant is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AddParticipantToCaseActivity(
            object_=participant, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "add_participant_to_case_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "add_participant_to_case_activity: invalid arguments"
        ) from exc


def remove_participant_from_case_activity(
    participant: CaseParticipant,
    target: VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Remove:
    """Build a Remove(CaseParticipant, target=VulnerabilityCase).

    This MUST only be performed by the case owner.

    Args:
        participant: The ``CaseParticipant`` to remove from the case.
        target: The ``VulnerabilityCase`` (or its URI) from which the
            participant is being removed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Remove`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RemoveParticipantFromCaseActivity(
            object_=participant, target=target, **kwargs
        )
    except ValidationError as exc:
        logger.warning(
            "remove_participant_from_case_activity: invalid arguments: %s",
            exc,
        )
        raise VultronActivityConstructionError(
            "remove_participant_from_case_activity: invalid arguments"
        ) from exc
