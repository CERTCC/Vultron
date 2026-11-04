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

"""Use case for received Create(ProcessingFault) NACK messages.

A sender receives this when a receiver could not process its activity
(ADR-0080, ASK-07-001).  The response depends on the fault's failure class:
a replica's case-diverged fault makes the CASE_MANAGER re-seed it
(SYNC-16-003, ADR-0142); a replica's hash-mismatch fault is logged at ERROR
beside a re-check of the CASE_MANAGER's own copy (SYNC-03-010); every other
class is archived and skipped until the
outstanding-request register correlates it to its ask (#2883).
"""

from vultron.core.use_cases.received.fault.processing_fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.core.use_cases.received.fault.refusal_notice import (
    RefusalNoticeReceivedUseCase,
)
from vultron.core.use_cases.received.fault.responses import (
    ARCHIVE_ONLY,
    FaultResponse,
    FaultTreeBuilder,
    FaultVerdictReader,
)

__all__ = [
    "ARCHIVE_ONLY",
    "CreateProcessingFaultReceivedUseCase",
    "FaultResponse",
    "FaultTreeBuilder",
    "FaultVerdictReader",
    "RefusalNoticeReceivedUseCase",
]
