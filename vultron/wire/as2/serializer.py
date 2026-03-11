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

"""Outbound serializer: converts core domain types to AS2 wire format.

This module is the single seam between the core domain layer and the AS2
wire layer for outbound (locally-originated) activities.  Adapter-layer
code (handlers, trigger services) SHOULD use these helpers rather than
importing core domain types alongside wire types in the same module.

Core BT nodes in ``vultron/core/behaviors/`` MUST NOT import from this
module — they work exclusively with domain types from
``vultron/core/models/vultron_types.py``.

Per ``notes/domain-model-separation.md`` (Outbound Event Design Questions)
and the P65-6b task in ``plan/IMPLEMENTATION_PLAN.md``.
"""

from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronCreateCaseActivity,
    VultronParticipant,
    VultronParticipantStatus,
    VultronReport,
)
from vultron.wire.as2.vocab.activities.case import CreateCase as as_CreateCase
from vultron.wire.as2.vocab.objects.case_actor import CaseActor
from vultron.wire.as2.vocab.objects.case_participant import VendorParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


def domain_case_to_wire(domain: VultronCase) -> VulnerabilityCase:
    """Convert a ``VultronCase`` domain object to a ``VulnerabilityCase`` wire object."""
    return VulnerabilityCase(
        as_id=domain.as_id,
        name=domain.name,
        attributed_to=domain.attributed_to,
        context=domain.context,
        vulnerability_reports=domain.vulnerability_reports,
        case_participants=domain.case_participants,
        actor_participant_index=domain.actor_participant_index,
        notes=domain.notes,
        active_embargo=domain.active_embargo,
        proposed_embargoes=domain.proposed_embargoes,
    )


def domain_case_actor_to_wire(domain: VultronCaseActor) -> CaseActor:
    """Convert a ``VultronCaseActor`` domain object to a ``CaseActor`` wire object."""
    return CaseActor(
        as_id=domain.as_id,
        name=domain.name,
        attributed_to=domain.attributed_to,
        context=domain.context,
    )


def domain_participant_to_wire(
    domain: VultronParticipant,
) -> VendorParticipant:
    """Convert a ``VultronParticipant`` domain object to a ``VendorParticipant`` wire object."""
    return VendorParticipant(
        as_id=domain.as_id,
        name=domain.name,
        attributed_to=domain.attributed_to,
        context=domain.context,
        case_roles=domain.case_roles,
        accepted_embargo_ids=domain.accepted_embargo_ids,
        participant_case_name=domain.participant_case_name,
    )


def domain_create_case_activity_to_wire(
    domain: VultronCreateCaseActivity,
) -> as_CreateCase:
    """Convert a ``VultronCreateCaseActivity`` domain object to a ``CreateCase`` wire activity."""
    return as_CreateCase(
        as_id=domain.as_id,
        actor=domain.actor,
        object=domain.object,
    )


def domain_participant_status_to_wire(
    domain: VultronParticipantStatus,
) -> ParticipantStatus:
    """Convert a ``VultronParticipantStatus`` domain object to a ``ParticipantStatus`` wire object."""
    return ParticipantStatus(
        as_id=domain.as_id,
        attributed_to=domain.attributed_to,
        context=domain.context,
        rm_state=domain.rm_state,
        vfd_state=domain.vfd_state,
        case_engagement=domain.case_engagement,
        embargo_adherence=domain.embargo_adherence,
        tracking_id=domain.tracking_id,
    )


def domain_report_to_wire(domain: VultronReport) -> VulnerabilityReport:
    """Convert a ``VultronReport`` domain object to a ``VulnerabilityReport`` wire object."""
    return VulnerabilityReport(
        as_id=domain.as_id,
        name=domain.name,
        content=domain.content,
        attributed_to=domain.attributed_to,
        context=domain.context,
    )


__all__ = [
    "domain_case_to_wire",
    "domain_case_actor_to_wire",
    "domain_participant_to_wire",
    "domain_create_case_activity_to_wire",
    "domain_participant_status_to_wire",
    "domain_report_to_wire",
]
