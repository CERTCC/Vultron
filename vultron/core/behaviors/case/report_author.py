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

"""The reporter of a stored report: its ``attributed_to`` (CP-01-004).

The case-proposal tree derives the reporter from the report the proposal
carried inline in three places — the reporter participant, its SIGNATORY seed,
and the creation-time revision's relay (EP-04-011).  Each decides for itself
what a missing reporter costs; the lookup is shared.
"""

from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import BtNodePreconditionError, VultronNotFoundError


def report_author_id(dl: CasePersistence, report_id: str) -> str:
    """Return the actor id the stored report *report_id* is attributed to.

    Raises:
        VultronNotFoundError: If no ``VulnerabilityReport`` is stored under
            *report_id*.
        BtNodePreconditionError: If the report names no ``attributed_to``.
    """
    report = dl.read(report_id)
    if not isinstance(report, VulnerabilityReport):
        raise VultronNotFoundError("VulnerabilityReport", report_id)
    author = report.attributed_to
    if not isinstance(author, str) or not author:
        raise BtNodePreconditionError(
            f"report '{report_id}' has no attributed_to"
        )
    return author


__all__ = ["report_author_id"]
