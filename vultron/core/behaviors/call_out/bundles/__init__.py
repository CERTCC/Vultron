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
"""Core-owned call-out backend bundles and DETERMINISTIC singletons (BT-23).

Re-exports the per-domain bundle dataclasses and their pre-built
``<DOMAIN>_DETERMINISTIC`` singletons.  These are the core, production-usable
happy-path defaults injected into every BT tree builder when no explicit
``call_out`` bundle is supplied (ADR-0025).

The matching ``<DOMAIN>_STOCHASTIC`` singletons live in the simulation layer
(``vultron.demo.fuzzer.bundles``); core never imports them.
"""

from vultron.core.behaviors.call_out.bundles.actor_discovery import (
    ACTOR_DISCOVERY_DETERMINISTIC,
    ActorDiscoveryCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.acquire_exploit import (
    ACQUIRE_EXPLOIT_DETERMINISTIC,
    AcquireExploitCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.assign_cve_id import (
    ASSIGN_CVE_ID_DETERMINISTIC,
    AssignCveIdCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.assign_vul_id import (
    ASSIGN_VUL_ID_DETERMINISTIC,
    AssignVulIdCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.close_report import (
    CLOSE_REPORT_DETERMINISTIC,
    CloseReportCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.deploy_fix import (
    DEPLOY_FIX_DETERMINISTIC,
    DeployFixCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
    DEPLOY_MITIGATION_DETERMINISTIC,
    DeployMitigationCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.deploy_monitoring import (
    DeploymentMonitoringBundle,
)
from vultron.core.behaviors.call_out.bundles.develop_fix import (
    DEVELOP_FIX_DETERMINISTIC,
    DevelopFixCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.embargo import (
    EMBARGO_DETERMINISTIC,
    EmbargoCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.prioritization import (
    PRIORITIZATION_DETERMINISTIC,
    PrioritizationCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.publication import (
    PUBLICATION_DETERMINISTIC,
    PublicationCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.report_to_others import (
    REPORT_TO_OTHERS_DETERMINISTIC,
    ReportToOthersCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.call_out.bundles.validation import (
    VALIDATION_DETERMINISTIC,
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
    "DeploymentMonitoringBundle",
    "EmbargoCallOutBundle",
    "PrioritizationCallOutBundle",
    "PublicationCallOutBundle",
    "ReportToOthersCallOutBundle",
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
    "DEPLOY_MITIGATION_DETERMINISTIC",
    "EMBARGO_DETERMINISTIC",
    "PRIORITIZATION_DETERMINISTIC",
    "PUBLICATION_DETERMINISTIC",
    "REPORT_TO_OTHERS_DETERMINISTIC",
    "STATUS_AUTHORIZATION_DETERMINISTIC",
    "VALIDATION_DETERMINISTIC",
]
