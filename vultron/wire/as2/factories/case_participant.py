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
``as_CaseParticipant`` objects. Internal activity subclasses are
imported here and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._context import (
    case_target_ref,
    with_case_context,
)
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
    _AddStatusToParticipantActivity,
    _CreateParticipantActivity,
    _RemoveParticipantFromCaseActivity,
    _UpdateParticipantActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
    as_Remove,
    as_Update,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
    as_CaseParticipantRef,
)
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseRef,
)


def create_participant_activity(
    participant: as_CaseParticipant,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Create:
    """Build a Create(CaseParticipant).

    The internal class automatically generates a descriptive ``name``
    field if one is not provided.

    Args:
        participant: The ``as_CaseParticipant`` being created.
        target: The ``VulnerabilityCase`` (or its URI) this participant
            is being created for.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Create`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "create_participant_activity",
        _CreateParticipantActivity,
        lambda: {
            "object_": participant,
            "target": case_target_ref(target),
            **kwargs,
        },
    )


def update_participant_activity(
    participant: as_CaseParticipant,
    **kwargs,
) -> as_Update:
    """Build an Update(CaseParticipant).

    The snapshot shape of a CASE_MANAGER-authored ledger entry recording a
    change to a participant record, carrying the record in full (CLP-07-021),
    labelled ``update_case_participant``; no received use case handles it
    (ADR-0140).

    Args:
        participant: The changed ``as_CaseParticipant``.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``context``, ``id_``).

    Returns:
        An ``as_Update`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "update_participant_activity",
        _UpdateParticipantActivity,
        lambda: {"object_": participant, **kwargs},
    )


def add_status_to_participant_activity(
    status: as_ParticipantStatus,
    target: as_CaseParticipantRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(ParticipantStatus)[target=CaseParticipant].

    Args:
        status: The ``as_ParticipantStatus`` to add.
        target: The ``as_CaseParticipant`` (or its URI) to which the
            status is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the status.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "add_status_to_participant_activity",
        _AddStatusToParticipantActivity,
        lambda: {
            "object_": status,
            "target": case_target_ref(target),
            **kwargs,
        },
    )


def add_participant_to_case_activity(
    participant: as_CaseParticipant,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Add:
    """Build an Add(CaseParticipant)[target=VulnerabilityCase].

    Args:
        participant: The ``as_CaseParticipant`` to add to the case.
        target: The ``VulnerabilityCase`` (or its URI) to which the
            participant is being added.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Add`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "add_participant_to_case_activity",
        _AddParticipantToCaseActivity,
        lambda: {
            "object_": participant,
            "target": case_target_ref(target),
            **with_case_context(kwargs, target),
        },
    )


def remove_participant_from_case_activity(
    participant: as_CaseParticipant,
    target: as_VulnerabilityCaseRef | None = None,
    **kwargs,
) -> as_Remove:
    """Build a Remove(CaseParticipant)[target=VulnerabilityCase].

    This MUST only be performed by the case owner.

    Args:
        participant: The ``as_CaseParticipant`` to remove from the case.
        target: The ``VulnerabilityCase`` (or its URI) from which the
            participant is being removed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``).

    Returns:
        An ``as_Remove`` whose ``object_`` is the participant.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "remove_participant_from_case_activity",
        _RemoveParticipantFromCaseActivity,
        lambda: {
            "object_": participant,
            "target": case_target_ref(target),
            **with_case_context(kwargs, target),
        },
    )
