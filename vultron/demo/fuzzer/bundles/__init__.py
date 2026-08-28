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

from vultron.demo.fuzzer.bundles.actor_discovery import (
    ACTOR_DISCOVERY_DETERMINISTIC,
    ACTOR_DISCOVERY_STOCHASTIC,
    ActorDiscoveryCallOutBundle,
)
from vultron.demo.fuzzer.bundles.acquire_exploit import (
    ACQUIRE_EXPLOIT_DETERMINISTIC,
    ACQUIRE_EXPLOIT_STOCHASTIC,
    AcquireExploitCallOutBundle,
)
from vultron.demo.fuzzer.bundles.assign_cve_id import (
    ASSIGN_CVE_ID_DETERMINISTIC,
    ASSIGN_CVE_ID_STOCHASTIC,
    AssignCveIdCallOutBundle,
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
from vultron.demo.fuzzer.bundles.deploy_mitigation import (
    DEPLOY_MITIGATION_DETERMINISTIC,
    DEPLOY_MITIGATION_STOCHASTIC,
    DeployMitigationCallOutBundle,
)
from vultron.demo.fuzzer.bundles.develop_fix import (
    DEVELOP_FIX_DETERMINISTIC,
    DEVELOP_FIX_STOCHASTIC,
    DevelopFixCallOutBundle,
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
from vultron.demo.fuzzer.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    STATUS_AUTHORIZATION_PERMISSIVE,
    STATUS_AUTHORIZATION_STOCHASTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.demo.fuzzer.bundles.validation import (
    VALIDATION_DETERMINISTIC,
    VALIDATION_STOCHASTIC,
    ValidationCallOutBundle,
)

__all__ = [
    # Bundle classes
    "ActorDiscoveryCallOutBundle",
    "AcquireExploitCallOutBundle",
    "AssignCveIdCallOutBundle",
    "DevelopFixCallOutBundle",
    "AssignVulIdCallOutBundle",
    "CloseReportCallOutBundle",
    "DeployFixCallOutBundle",
    "DeployMitigationCallOutBundle",
    "EmbargoCallOutBundle",
    "PrioritizationCallOutBundle",
    "PublicationCallOutBundle",
    "StatusAuthorizationCallOutBundle",
    "ValidationCallOutBundle",
    # Deterministic singletons
    "ACTOR_DISCOVERY_DETERMINISTIC",
    "ACQUIRE_EXPLOIT_DETERMINISTIC",
    "ASSIGN_CVE_ID_DETERMINISTIC",
    "DEVELOP_FIX_DETERMINISTIC",
    "ASSIGN_VUL_ID_DETERMINISTIC",
    "CLOSE_REPORT_DETERMINISTIC",
    "DEPLOY_FIX_DETERMINISTIC",
    "EMBARGO_DETERMINISTIC",
    "PRIORITIZATION_DETERMINISTIC",
    "PUBLICATION_DETERMINISTIC",
    "STATUS_AUTHORIZATION_DETERMINISTIC",
    "STATUS_AUTHORIZATION_PERMISSIVE",
    "VALIDATION_DETERMINISTIC",
    # Stochastic singletons
    "ACTOR_DISCOVERY_STOCHASTIC",
    "ACQUIRE_EXPLOIT_STOCHASTIC",
    "ASSIGN_CVE_ID_STOCHASTIC",
    "DEVELOP_FIX_STOCHASTIC",
    "ASSIGN_VUL_ID_STOCHASTIC",
    "CLOSE_REPORT_STOCHASTIC",
    "DEPLOY_FIX_STOCHASTIC",
    "DEPLOY_MITIGATION_DETERMINISTIC",
    "DEPLOY_MITIGATION_STOCHASTIC",
    "EMBARGO_STOCHASTIC",
    "PRIORITIZATION_STOCHASTIC",
    "PUBLICATION_STOCHASTIC",
    "STATUS_AUTHORIZATION_STOCHASTIC",
    "VALIDATION_STOCHASTIC",
]
