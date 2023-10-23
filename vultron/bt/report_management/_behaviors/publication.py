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


class _ReadyExploitForPublication(FallbackNode):
    _children = (AcquireExploit, PrepareExploit)


class _EnsureExploitPublishedIfDesired(FallbackNode):
    _children = (
        NoPublishExploit,
        ExploitReady,
        _ReadyExploitForPublication,
        ReprioritizeExploit,
    )


class _ReadyFixForPublication(SequenceNode):
    _children = (DevelopFix, PrepareFix)


class _EnsureFixIsDevelopedIfDesired(FallbackNode):
    _children = (
        NoPublishFix,
        CSinStateVendorAwareAndFixReady,
        _ReadyFixForPublication,
        ReprioritizeFix,
    )


class _EnsureReportIsPublishedIfDesired(FallbackNode):
    _children = (NoPublishReport, PrepareReport, ReprioritizeReport)


class _PreparePublication(SequenceNode):
    _children = (
        _EnsureExploitPublishedIfDesired,
        _EnsureFixIsDevelopedIfDesired,
        _EnsureReportIsPublishedIfDesired,
    )


class _EnsurePublicationPriorityIsSet(FallbackNode):
    _children = (PublicationIntentsSet, PrioritizePublicationIntents)


class _EnsureAllDesiredItemsArePublished(SequenceNode):
    _children = (_EnsurePublicationPriorityIsSet, AllPublished)


class _PublishWhenReady(SequenceNode):
    _children = (
        _PreparePublication,
        EmbargoManagementBt,
        EMinStateNoneOrExited,
        Publish,
        q_cs_to_P,
        EmitCP,
    )


class Publication(FallbackNode):
    _children = (_EnsureAllDesiredItemsArePublished, _PublishWhenReady)


def main():
    pass


if __name__ == "__main__":
    main()
