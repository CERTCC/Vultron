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
Thin adapter delegates for report-level trigger service functions.

Each function keeps the same external signature used by the HTTP router, builds
a domain request model (adding ``actor_id``), instantiates the core use-case
class, and delegates to ``execute()``.

Domain logic must not be added here.  See
``vultron/core/use_cases/triggers/report.py`` for implementation.
"""

from vultron.api.v2.backend.trigger_services._helpers import (
    domain_error_translation,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases.triggers.report import (
    SvcCloseReportUseCase,
    SvcInvalidateReportUseCase,
    SvcRejectReportUseCase,
    SvcValidateReportUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    CloseReportTriggerRequest,
    InvalidateReportTriggerRequest,
    RejectReportTriggerRequest,
    ValidateReportTriggerRequest,
)


def validate_report_trigger(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = ValidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcValidateReportUseCase(dl, request).execute()


def invalidate_report_trigger(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = InvalidateReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcInvalidateReportUseCase(dl, request).execute()


def reject_report_trigger(
    actor_id: str, offer_id: str, note: str, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = RejectReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note or None
        )
        return SvcRejectReportUseCase(dl, request).execute()


def close_report_trigger(
    actor_id: str, offer_id: str, note: str | None, dl: DataLayer
) -> dict:
    with domain_error_translation():
        request = CloseReportTriggerRequest(
            actor_id=actor_id, offer_id=offer_id, note=note
        )
        return SvcCloseReportUseCase(dl, request).execute()
