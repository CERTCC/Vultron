#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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
Provides Vultron-specific Activity Streams 2.0 objects.
"""

import importlib
import pkgutil
import sys


def _discover_modules() -> None:
    """Import all modules in this package to ensure vocab classes are registered."""
    package = sys.modules[__name__]
    for _finder, name, _ispkg in pkgutil.iter_modules(
        package.__path__,  # type: ignore[attr-defined]
        package.__name__ + ".",
    ):
        if name not in sys.modules:
            importlib.import_module(name)


_discover_modules()

# ---------------------------------------------------------------------------
# Explicit re-exports of as_-prefixed wire vocabulary classes (ARCH-14-001)
# ---------------------------------------------------------------------------
from vultron.wire.as2.vocab.objects.case_actor import (  # noqa: E402
    as_CaseActor,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (  # noqa: E402
    as_CaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_participant import (  # noqa: E402
    as_CaseParticipant,
    as_CaseParticipantRef,
)
from vultron.wire.as2.vocab.objects.case_reference import (  # noqa: E402
    as_CaseReference,
    as_CaseReferenceRef,
)
from vultron.wire.as2.vocab.objects.case_status import (  # noqa: E402
    as_CaseStatus,
    as_CaseStatusRef,
    as_ParticipantStatus,
    as_ParticipantStatusRef,
)
from vultron.wire.as2.vocab.objects.embargo_event import (  # noqa: E402
    as_EmbargoEvent,
    as_EmbargoEventRef,
)
from vultron.wire.as2.vocab.objects.embargo_policy import (  # noqa: E402
    as_EmbargoPolicy,
    as_EmbargoPolicyRef,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: E402
    as_VulnerabilityCase,
    as_VulnerabilityCaseRef,
)
from vultron.wire.as2.vocab.objects.vulnerability_record import (  # noqa: E402
    as_VulnerabilityRecord,
    as_VulnerabilityRecordRef,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (  # noqa: E402
    as_VulnerabilityReport,
    as_VulnerabilityReportRef,
)
from vultron.wire.as2.vocab.objects.vultron_actor import (  # noqa: E402
    as_VultronApplication,
    as_VultronApplicationRef,
    as_VultronGroup,
    as_VultronGroupRef,
    as_VultronOrganization,
    as_VultronOrganizationRef,
    as_VultronPerson,
    as_VultronPersonRef,
    as_VultronService,
    as_VultronServiceRef,
)

# ---------------------------------------------------------------------------
# Backward-compatibility aliases — existing imports keep working unchanged.
# Callers should migrate to the as_-prefixed names (ARCH-14-001).
# ---------------------------------------------------------------------------
CaseActor = as_CaseActor
CaseLedgerEntry = as_CaseLedgerEntry
CaseParticipant = as_CaseParticipant
CaseParticipantRef = as_CaseParticipantRef
CaseReference = as_CaseReference
CaseReferenceRef = as_CaseReferenceRef
CaseStatus = as_CaseStatus
CaseStatusRef = as_CaseStatusRef
ParticipantStatus = as_ParticipantStatus
ParticipantStatusRef = as_ParticipantStatusRef
EmbargoEvent = as_EmbargoEvent
EmbargoEventRef = as_EmbargoEventRef
EmbargoPolicy = as_EmbargoPolicy
EmbargoPolicyRef = as_EmbargoPolicyRef
VulnerabilityCase = as_VulnerabilityCase
VulnerabilityCaseRef = as_VulnerabilityCaseRef
VulnerabilityRecord = as_VulnerabilityRecord
VulnerabilityRecordRef = as_VulnerabilityRecordRef
VulnerabilityReport = as_VulnerabilityReport
VulnerabilityReportRef = as_VulnerabilityReportRef
VultronApplication = as_VultronApplication
VultronApplicationRef = as_VultronApplicationRef
VultronGroup = as_VultronGroup
VultronGroupRef = as_VultronGroupRef
VultronOrganization = as_VultronOrganization
VultronOrganizationRef = as_VultronOrganizationRef
VultronPerson = as_VultronPerson
VultronPersonRef = as_VultronPersonRef
VultronService = as_VultronService
VultronServiceRef = as_VultronServiceRef
