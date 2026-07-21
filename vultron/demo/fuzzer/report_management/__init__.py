#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""Report management fuzzer nodes for the Vultron demo layer.

This sub-package provides probabilistic py_trees behaviour nodes for the
Report Management (RM) workflow, grouped by sub-topic:

- ``validate`` — report validation nodes (5 nodes)
- ``prioritize`` — report prioritization nodes (5 nodes)
- ``assign_vul_id`` — VUL ID assignment nodes (6 nodes)
- ``develop_fix`` — fix development nodes (1 node)
- ``deploy_fix`` — fix deployment nodes (8 nodes)
- ``monitor_threats`` — threat monitoring nodes (4 nodes)
- ``acquire_exploit`` — exploit acquisition nodes (8 nodes)
- ``close_report`` — report closure nodes (2 nodes)
- ``other_work`` — miscellaneous work placeholder (1 node)
- ``report_to_others`` — report-to-others workflow nodes (21 nodes)
- ``publication`` — publication workflow nodes (14 nodes)
"""

from vultron.demo.fuzzer.report_management.prioritize import (
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
    NoNewPrioritizationInfo,
    OnAccept,
    OnDefer,
)
from vultron.demo.fuzzer.report_management.validate import (
    EnoughValidationInfo,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    GatherValidationInfo,
    NoNewValidationInfo,
)
from vultron.demo.fuzzer.report_management.assign_vul_id import (
    AssignId,
    IdAssignable,
    IdAssigned,
    InScope,
    IsIDAssignmentAuthority,
    RequestId,
)
from vultron.demo.fuzzer.report_management.close_report import (
    OtherCloseCriteriaMet,
    PreCloseAction,
)
from vultron.demo.fuzzer.report_management.develop_fix import CreateFix
from vultron.demo.fuzzer.report_management.deploy_fix import (
    DeployFix,
    DeployMitigation,
    MitigationAvailable,
    MitigationDeployed,
    MonitorDeployment,
    MonitoringRequirement,
    NoNewDeploymentInfo,
    PrioritizeDeployment,
)
from vultron.demo.fuzzer.report_management.monitor_threats import (
    MonitorAttacks,
    MonitorExploits,
    MonitorPublicReports,
    NoThreatsFound,
)
from vultron.demo.fuzzer.report_management.acquire_exploit import (
    DevelopExploit,
    EvaluateExploitPriority,
    EvaluateExploitStrategy,
    ExploitDeferred,
    ExploitDesired,
    ExploitPrioritySet,
    FindExploit,
    HaveExploit,
    PurchaseExploit,
)
from vultron.demo.fuzzer.report_management.other_work import OtherWork
from vultron.demo.fuzzer.report_management.report_to_others import (
    AllPartiesKnown,
    ChooseRecipient,
    HaveReportToOthersCapability,
    IdentifyCoordinators,
    IdentifyOthers,
    IdentifyVendors,
    InjectCoordinator,
    InjectOther,
    InjectParticipant,
    InjectVendor,
    MoreCoordinators,
    MoreOthers,
    MoreVendors,
    NotificationsComplete,
    PolicyCompatible,
    RcptNotInQrmS,
    RecipientEffortExceeded,
    RemoveRecipient,
    SetRcptQrmR,
    TotalEffortLimitMet,
)
from vultron.demo.fuzzer.report_management.publication import (
    AllPublished,
    ExploitReady,
    NoPublishExploit,
    NoPublishFix,
    NoPublishReport,
    PrepareFix,
    PrepareExploit,
    PrepareReport,
    PrioritizePublicationIntents,
    Publish,
    PublicationIntentsSet,
    ReprioritizeExploit,
    ReprioritizeFix,
    ReprioritizeReport,
)

__all__ = [
    # validation nodes
    "NoNewValidationInfo",
    "EvaluateReportCredibility",
    "EvaluateReportValidity",
    "EnoughValidationInfo",
    "GatherValidationInfo",
    # prioritization nodes
    "NoNewPrioritizationInfo",
    "EnoughPrioritizationInfo",
    "GatherPrioritizationInfo",
    "OnAccept",
    "OnDefer",
    # VUL ID assignment
    "IdAssigned",
    "IdAssignable",
    "IsIDAssignmentAuthority",
    "RequestId",
    "AssignId",
    "InScope",
    # fix development
    "CreateFix",
    # fix deployment
    "NoNewDeploymentInfo",
    "PrioritizeDeployment",
    "MitigationDeployed",
    "MitigationAvailable",
    "DeployMitigation",
    "MonitoringRequirement",
    "MonitorDeployment",
    "DeployFix",
    # threat monitoring
    "MonitorAttacks",
    "MonitorExploits",
    "MonitorPublicReports",
    "NoThreatsFound",
    # exploit acquisition (simulator nodes)
    "HaveExploit",
    "ExploitDeferred",
    "ExploitPrioritySet",
    "EvaluateExploitPriority",
    "ExploitDesired",
    "FindExploit",
    "DevelopExploit",
    "PurchaseExploit",
    # exploit acquisition (production collapse 1 — ADR-0027)
    "EvaluateExploitStrategy",
    # report closure
    "OtherCloseCriteriaMet",
    "PreCloseAction",
    # other work
    "OtherWork",
    # report-to-others workflow
    "HaveReportToOthersCapability",
    "AllPartiesKnown",
    "IdentifyVendors",
    "IdentifyCoordinators",
    "IdentifyOthers",
    "NotificationsComplete",
    "ChooseRecipient",
    "RemoveRecipient",
    "RecipientEffortExceeded",
    "PolicyCompatible",
    "RcptNotInQrmS",
    "SetRcptQrmR",
    "TotalEffortLimitMet",
    "MoreVendors",
    "MoreCoordinators",
    "MoreOthers",
    "InjectParticipant",
    "InjectVendor",
    "InjectCoordinator",
    "InjectOther",
    # publication workflow
    "AllPublished",
    "PublicationIntentsSet",
    "PrioritizePublicationIntents",
    "Publish",
    "NoPublishExploit",
    "ExploitReady",
    "PrepareExploit",
    "ReprioritizeExploit",
    "NoPublishFix",
    "PrepareFix",
    "ReprioritizeFix",
    "NoPublishReport",
    "PrepareReport",
    "ReprioritizeReport",
]
