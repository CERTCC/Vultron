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

"""Vultron protocol object-type enumerations — bottom-of-stack neutral layer.

``VultronObjectType`` and ``VultronActorType`` are cross-cutting primitives
used by both ``vultron/core/`` and ``vultron/wire/``.  They live here so
that wire-layer modules can import them without creating ``vultron.core.models``
imports (ARCH-22-001).

This module MUST NOT import from ``vultron.core``, ``vultron.config``,
``vultron.wire``, or ``vultron.adapters``.

Per ``docs/adr/0031-vultron-enums-neutral-layer.md``.
"""

from enum import StrEnum


class VultronObjectType(StrEnum):
    """Enumeration of Vultron-specific domain object types."""

    VULNERABILITY_CASE = "VulnerabilityCase"
    VULNERABILITY_REPORT = "VulnerabilityReport"
    VULNERABILITY_RECORD = "VulnerabilityRecord"
    CASE_REFERENCE = "CaseReference"
    EMBARGO_POLICY = "EmbargoPolicy"
    CASE_PARTICIPANT = "CaseParticipant"
    CASE_PARTICIPANT_ROLE = "CaseParticipantRole"
    CASE_STATUS = "CaseStatus"
    PARTICIPANT_STATUS = "ParticipantStatus"
    CASE_LEDGER_ENTRY = "CaseLedgerEntry"
    CASE_PROPOSAL = "CaseProposal"
    PROCESSING_FAULT = "ProcessingFault"


class VultronActorType(StrEnum):
    """Enumeration of supported ActivityStreams actor type values."""

    PERSON = "Person"
    ORGANIZATION = "Organization"
    SERVICE = "Service"
    APPLICATION = "Application"
    GROUP = "Group"


__all__ = ["VultronObjectType", "VultronActorType"]
