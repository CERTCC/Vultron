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

"""The VINCE crosswalk rows the translation applies (CRD-03-001).

Every row id, caveat and unobservable fact here is copied from the VINCE
crosswalk page, ``docs/reference/vince_crosswalk.md``, which is where a
person decided each mapping (ADR-0197 point 2).  A test checks each row id
and caveat against that page, so the two cannot drift apart (CRD-03-005).
"""

from __future__ import annotations

from types import MappingProxyType

from vultron.core.models.case_reading import UnobservableFact

#: The rows whose result VINCE implies but does not state, each with the
#: caveat the crosswalk gives for it (CRD-02-002).
INFERRED_ROWS: MappingProxyType[str, str] = MappingProxyType(
    {
        "VINCE-CA-03": (
            "VINCE marks the case Inactive. The time is the case's last"
            " change, which may be later than the closure."
        ),
        "VINCE-PA-04": (
            "The reporter withheld their contact details. The identity is a"
            " placeholder."
        ),
        "VINCE-RM-02": (
            "VINCE opens a case when CERT/CC accepts the report. VINCE does"
            " not record the acceptance."
        ),
        "VINCE-RM-03": (
            "A reporter accepts its own report when it submits it."
        ),
        "VINCE-RM-04": (
            "VINCE lists the vendor on the case. The notification itself is"
            " not in the VINCE API."
        ),
        "VINCE-RM-05": (
            "The vendor marked a vul Affected. VINCE does not record that the"
            " vendor accepted the report."
        ),
        "VINCE-RM-06": "The vendor marked every vul Not Affected.",
        "VINCE-RM-07": (
            "Unknown can mean the vendor said Unknown or did not share its"
            " status. The VINCE API does not tell the two apart."
        ),
        "VINCE-EM-01": (
            "VINCE records a planned publication date. VINCE does not record"
            " when the date was set."
        ),
        "VINCE-EM-02": (
            "VINCE does not track embargo consent. Vultron infers the"
            " vendor's agreement from its place on the case."
        ),
    }
)

#: What the VINCE API never exposes, for any case (crosswalk
#: § Unobservable).  Every reading carries it (CRD-02-004).
VINCE_UNOBSERVABLE: tuple[UnobservableFact, ...] = (
    UnobservableFact(
        fact="Fix ready (F), fix deployed (D)",
        why="No VINCE field records them.",
    ),
    UnobservableFact(
        fact="A vendor was notified, a vendor viewed the case",
        why=(
            "VINCE records these in its case activity log, which only the"
            " coordinator web pages show."
        ),
    ),
    UnobservableFact(
        fact="CERT/CC's own RM steps after the case opens, other than closure",
        why="The case activity log holds them.",
    ),
    UnobservableFact(
        fact="A message, a task or a publish event in the case activity log",
        why="The case activity log holds them.",
    ),
    UnobservableFact(
        fact="When due_date was set or changed",
        why="VINCE stores only the case's last modified time.",
    ),
)

#: The case ``status`` values a row names: ``Active`` adds no entry and
#: ``Inactive`` closes CERT/CC's RM (VINCE-CA-03).
CASE_ACTIVE = "Active"
CASE_INACTIVE = "Inactive"

#: The per-vul vendor statuses a row names (VINCE-RM-05 to VINCE-RM-07).
AFFECTED = "Affected"
NOT_AFFECTED = "Not Affected"
UNKNOWN = "Unknown"
VENDOR_STATUSES = frozenset({AFFECTED, NOT_AFFECTED, UNKNOWN})

#: The organization name VINCE gives the coordinator on its posts.
COORDINATOR_ORG = "CERT/CC"


__all__ = [
    "AFFECTED",
    "CASE_ACTIVE",
    "CASE_INACTIVE",
    "COORDINATOR_ORG",
    "INFERRED_ROWS",
    "NOT_AFFECTED",
    "UNKNOWN",
    "VENDOR_STATUSES",
    "VINCE_UNOBSERVABLE",
]
