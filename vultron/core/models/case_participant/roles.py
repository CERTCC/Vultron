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

"""Role subclasses of :class:`CaseParticipant` that auto-set ``case_roles``."""

from __future__ import annotations

from typing import Any

from pydantic import (
    model_validator,
)

from vultron.core.models._helpers import new_object_id
from vultron.core.models.case_participant.participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole


def _seed_accepted_status(data: Any) -> Any:
    """Seed ``participant_statuses`` with a single ``RM.ACCEPTED`` rung.

    A reporter has, by definition, accepted the report, so its first ladder
    rung is ``RM.ACCEPTED``.  Used by :class:`ReporterParticipant`.
    """
    if not isinstance(data, dict):
        return data
    data = dict(data)
    if not data.get("id") and not data.get("id_"):
        data["id"] = new_object_id()
    id_val = data.get("id") or data.get("id_")
    data["participant_statuses"] = [
        ParticipantStatus(
            context=data.get("context") or id_val,
            attributed_to=data.get("attributed_to"),
            rm=RmDimension(state=RM.ACCEPTED),
            cvd_role=coerce_cvd_roles(data.get("case_roles") or []),
        )
    ]
    return data


class ReporterParticipant(CaseParticipant):
    """A CaseParticipant that holds the REPORTER role.

    Also initialises ``participant_statuses`` to ``[ACCEPTED]`` because a
    reporter has by definition accepted the report.
    """

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.REPORTER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data

    @model_validator(mode="before")
    @classmethod
    def _set_accepted_status(cls, data: Any) -> Any:
        return _seed_accepted_status(data)


class VendorParticipant(CaseParticipant):
    """A CaseParticipant that holds the VENDOR role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.VENDOR]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class DeployerParticipant(CaseParticipant):
    """A CaseParticipant that holds the DEPLOYER role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.DEPLOYER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class CoordinatorParticipant(CaseParticipant):
    """A CaseParticipant that holds the COORDINATOR role."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.COORDINATOR]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class ObserverParticipant(CaseParticipant):
    """A CaseParticipant that holds the OBSERVER role (ADR-0057)."""

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.OBSERVER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data


class CaseActorParticipant(CaseParticipant):
    """A participant that acts as the CaseActor service for a VulnerabilityCase.

    Holds both ``COORDINATOR`` and ``CASE_MANAGER`` roles (CBT-01-014,
    CBT-01-015).
    The ``attributed_to`` field identifies the ActivityStreams Service URI
    that will send ``Announce(VulnerabilityCase)`` updates on behalf of the
    case owner.  Receivers use this participant to establish trusted CaseActor
    identity during bootstrap.
    """

    @model_validator(mode="before")
    @classmethod
    def _set_role(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        roles = [CVDRole.COORDINATOR, CVDRole.CASE_MANAGER]
        data["case_roles"] = roles
        ps_list = data.get("participant_statuses")
        if ps_list:
            latest = ps_list[-1]
            if isinstance(latest, ParticipantStatus):
                latest.cvd_role = coerce_cvd_roles(roles)
        return data
