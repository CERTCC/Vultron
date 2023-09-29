#!/usr/bin/env python
"""file: publication
author: adh
created_at: 6/23/22 2:56 PM
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


from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.case_state.conditions import CSinStateVendorAwareAndFixReady
from vultron.bt.case_state.transitions import q_cs_to_P
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


class ReadyExploitForPublication(FallbackNode):
    _children = (AcquireExploit, PrepareExploit)


class EnsureExploitPublishedIfDesired(FallbackNode):
    _children = (
        NoPublishExploit,
        ExploitReady,
        ReadyExploitForPublication,
        ReprioritizeExploit,
    )


class ReadyFixForPublication(SequenceNode):
    _children = (DevelopFix, PrepareFix)


class EnsureFixIsDevelopedIfDesired(FallbackNode):
    _children = (
        NoPublishFix,
        CSinStateVendorAwareAndFixReady,
        ReadyFixForPublication,
        ReprioritizeFix,
    )


class EnsureReportIsPublishedIfDesired(FallbackNode):
    _children = (NoPublishReport, PrepareReport, ReprioritizeReport)


class PreparePublication(SequenceNode):
    _children = (
        EnsureExploitPublishedIfDesired,
        EnsureFixIsDevelopedIfDesired,
        EnsureReportIsPublishedIfDesired,
    )


class EnsurePublicationPriorityIsSet(FallbackNode):
    _children = (PublicationIntentsSet, PrioritizePublicationIntents)


class EnsureAllDesiredItemsArePublished(SequenceNode):
    _children = (EnsurePublicationPriorityIsSet, AllPublished)


class PublishWhenReady(SequenceNode):
    _children = (
        PreparePublication,
        EmbargoManagementBt,
        EMinStateNoneOrExited,
        Publish,
        q_cs_to_P,
        EmitCP,
    )


class Publication(FallbackNode):
    _children = (EnsureAllDesiredItemsArePublished, PublishWhenReady)


def main():
    pass


if __name__ == "__main__":
    main()
