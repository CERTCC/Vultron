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
"""Call-out point domain bundle package (BT-23-003, BT-23-005).

Re-exports all bundle classes and pre-built DETERMINISTIC / STOCHASTIC
singletons from the sub-modules.  Import from this package rather than the
individual modules for stable import paths::

    from vultron.demo.fuzzer.bundles import (
        ValidationCallOutBundle,
        VALIDATION_DETERMINISTIC,
        VALIDATION_STOCHASTIC,
        EmbargoCallOutBundle,
        EMBARGO_STOCHASTIC,
        ...
    )
"""

from vultron.demo.fuzzer.bundles.acquire_exploit import (
    ACQUIRE_EXPLOIT_DETERMINISTIC,
    ACQUIRE_EXPLOIT_STOCHASTIC,
    AcquireExploitCallOutBundle,
)
from vultron.demo.fuzzer.bundles.assign_vul_id import (
    ASSIGN_VUL_ID_DETERMINISTIC,
    ASSIGN_VUL_ID_STOCHASTIC,
    AssignVulIdCallOutBundle,
)
from vultron.demo.fuzzer.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
    CLOSE_REPORT_STOCHASTIC,
    CloseReportCallOutBundle,
)
from vultron.demo.fuzzer.bundles.deploy_fix import (
    DEPLOY_FIX_DETERMINISTIC,
    DEPLOY_FIX_STOCHASTIC,
    DeployFixCallOutBundle,
)
from vultron.demo.fuzzer.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EMBARGO_STOCHASTIC,
    EmbargoCallOutBundle,
)
from vultron.demo.fuzzer.bundles.prioritization import (
    PRIORITIZATION_DETERMINISTIC,
    PRIORITIZATION_STOCHASTIC,
    PrioritizationCallOutBundle,
)
from vultron.demo.fuzzer.bundles.publication import (
    PUBLICATION_DETERMINISTIC,
    PUBLICATION_STOCHASTIC,
    PublicationCallOutBundle,
)
from vultron.demo.fuzzer.bundles.report_to_others import (
    REPORT_TO_OTHERS_DETERMINISTIC,
    REPORT_TO_OTHERS_STOCHASTIC,
    ReportToOthersCallOutBundle,
)
from vultron.demo.fuzzer.bundles.validation import (
    VALIDATION_DETERMINISTIC,
    VALIDATION_STOCHASTIC,
    ValidationCallOutBundle,
)

__all__ = [
    # Bundle classes
    "AcquireExploitCallOutBundle",
    "AssignVulIdCallOutBundle",
    "CloseReportCallOutBundle",
    "DeployFixCallOutBundle",
    "EmbargoCallOutBundle",
    "PrioritizationCallOutBundle",
    "PublicationCallOutBundle",
    "ReportToOthersCallOutBundle",
    "ValidationCallOutBundle",
    # Deterministic singletons
    "ACQUIRE_EXPLOIT_DETERMINISTIC",
    "ASSIGN_VUL_ID_DETERMINISTIC",
    "CLOSE_REPORT_DETERMINISTIC",
    "DEPLOY_FIX_DETERMINISTIC",
    "EMBARGO_DETERMINISTIC",
    "PRIORITIZATION_DETERMINISTIC",
    "PUBLICATION_DETERMINISTIC",
    "REPORT_TO_OTHERS_DETERMINISTIC",
    "VALIDATION_DETERMINISTIC",
    # Stochastic singletons
    "ACQUIRE_EXPLOIT_STOCHASTIC",
    "ASSIGN_VUL_ID_STOCHASTIC",
    "CLOSE_REPORT_STOCHASTIC",
    "DEPLOY_FIX_STOCHASTIC",
    "EMBARGO_STOCHASTIC",
    "PRIORITIZATION_STOCHASTIC",
    "PUBLICATION_STOCHASTIC",
    "REPORT_TO_OTHERS_STOCHASTIC",
    "VALIDATION_STOCHASTIC",
]
