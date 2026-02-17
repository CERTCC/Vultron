#!/usr/bin/env python
"""
Provides publication behaviors.
"""

#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from vultron.bt.base.factory import fallback_node, sequence_node

#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


from vultron.bt.case_state.conditions import CSinStateVendorAwareAndFixReady
from vultron.bt.case_state.transitions import q_cs_to_P
from vultron.bt.common import show_graph
from vultron.bt.embargo_management.behaviors import EmbargoManagementBt
from vultron.bt.embargo_management.conditions import EMinStateNoneOrExited
from vultron.bt.messaging.outbound.behaviors import EmitCP
from vultron.bt.report_management._behaviors.acquire_exploit import (
    AcquireExploit,
)
from vultron.bt.report_management._behaviors.develop_fix import DevelopFix
from vultron.bt.report_management.fuzzer.publication import (
    AllPublished,
    ExploitReady,
    NoPublishExploit,
    NoPublishFix,
    NoPublishReport,
    PrepareExploit,
    PrepareFix,
    PrepareReport,
    PrioritizePublicationIntents,
    PublicationIntentsSet,
    Publish,
    ReprioritizeExploit,
    ReprioritizeFix,
    ReprioritizeReport,
)

_ReadyExploitForPublication = fallback_node(
    "_ReadyExploitForPublication",
    """
    This node represents the process of preparing an exploit for publication.
    Either the exploit has to be acquired or prepared for publication.
    """,
    AcquireExploit,
    PrepareExploit,
)


_MaybePrepareExploitForPublication = fallback_node(
    "_MaybePrepareExploitForPublication",
    """This node represents the process of ensuring that the exploit is published if it is desired.""",
    NoPublishExploit,
    ExploitReady,
    _ReadyExploitForPublication,
    ReprioritizeExploit,
)


_ReadyFixForPublication = sequence_node(
    "_ReadyFixForPublication",
    "Develop a fix then prepare it for publication.",
    DevelopFix,
    PrepareFix,
)


_MaybePrepareFixForPublication = fallback_node(
    "_MaybePrepareFixForPublication",
    """Develop a fix if is desired and ready """,
    NoPublishFix,
    CSinStateVendorAwareAndFixReady,
    _ReadyFixForPublication,
    ReprioritizeFix,
)


_MaybePrepareReportForPublication = fallback_node(
    "_MaybePrepareReportForPublication",
    "Prepare a report for publication if it is desired.",
    NoPublishReport,
    PrepareReport,
    ReprioritizeReport,
)


_PreparePublication = sequence_node(
    "_PreparePublication",
    "Prepare Report, Fix, and Exploit for publication.",
    _MaybePrepareExploitForPublication,
    _MaybePrepareFixForPublication,
    _MaybePrepareReportForPublication,
)


_EnsurePublicationPriorityIsSet = fallback_node(
    "_EnsurePublicationPriorityIsSet",
    """Ensure that the publication priorities are set.""",
    PublicationIntentsSet,
    PrioritizePublicationIntents,
)


_EnsureAllDesiredItemsArePublished = sequence_node(
    "_EnsureAllDesiredItemsArePublished",
    """Ensure that all desired items are published.""",
    _EnsurePublicationPriorityIsSet,
    AllPublished,
)


_PublishWhenReady = sequence_node(
    "_PublishWhenReady",
    """Publish the report, fix, and exploit when they are ready. Check that the embargo is not active first.""",
    _PreparePublication,
    EmbargoManagementBt,
    EMinStateNoneOrExited,
    Publish,
    q_cs_to_P,
    EmitCP,
)


Publication = fallback_node(
    "Publication",
    """This node represents the process of publishing a report, fix, and exploit.""",
    _EnsureAllDesiredItemsArePublished,
    _PublishWhenReady,
)


def main():
    show_graph(Publication)


if __name__ == "__main__":
    main()
