#!/usr/bin/env python
"""
This module provides fuzzer leaf nodes in support of the process of publishing the vulnerability and its artifacts
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


from vultron.bt.base import fuzzer as btz


class AllPublished(btz.AlmostAlwaysFail):
    """This condition is used to check if all of the artifacts for the vulnerability have been published. In a real
    implementation, this would be a simple check to see if all of the intended artifacts for the vulnerability have
    been published. In our stub implementation, this condition fails in 9 out of 10 attempts because we are assuming
    that the publishing process is part of the workflow we are modeling.
    """

    # check if all of the artifacts for the vulnerability have been published


class PublicationIntentsSet(btz.UsuallyFail):
    """This condition is used to check if the publication intents for the vulnerability have been set. Publication
    intents are used to indicate what artifacts about the vulnerability should be published. In a real
    implementation, this would be a simple check to see if the publication intents have been set. In our stub
    implementation, this condition fails in 3 out of 4 attempts because we are assuming that the publication intent
    setting process is part of the workflow we are modeling.
    """

    # check if the publication intents for the vulnerability have been set


class Publish(btz.AlmostAlwaysSucceed):
    """This node represents the process of publishing the artifacts for the vulnerability. In a real implementation,
    this could be automatable as an API call to a publishing system, such as a content management system, or it could
    be a prompt for a human to publish the artifacts. In our stub implementation, this node succeeds in 9 out of 10
    attempts, allowing us to exercise the rest of the workflow.
    """

    # publish the artifacts for the vulnerability or prompt a human to do so


class PrioritizePublicationIntents(btz.AlwaysSucceed):
    """This node represents the process of prioritizing the artifacts to be published for the vulnerability.
    In a real implementation, this would be a prompt for a human to prioritize the artifacts to be published, or
    it could be automated based on the organization's publication priorities and policies.
    In our stub implementation, this node always succeeds.
    """

    # prioritize the artifacts to be published for the vulnerability or prompt a human to do so


class NoPublishExploit(btz.UsuallySucceed):
    """This condition is used to check if the exploit for the vulnerability should be published.
    In a real implementation, this would be a simple check to see if the exploit should be published.
    In our stub implementation, this condition succeeds in 3 out of 4 attempts so we can
    model the concept that exploit publication is not always required.
    """

    # check if the exploit for the vulnerability should be published


class ExploitReady(btz.OftenSucceed):
    """This condition is used to check if the exploit for the vulnerability is ready to be published.
    In a real implementation, this would be a simple check to see if the exploit is available to be published.
    In our stub implementation, this condition succeeds in 7 out of 10 attempts so we can
    exercise the rest of the workflow.
    """

    # check if the exploit for the vulnerability is ready to be published


class PrepareExploit(btz.AlmostAlwaysSucceed):
    """This node represents the process of preparing the exploit for the vulnerability to be published. In a real
    implementation, this would probably be a prompt for a human to prepare the exploit for publication, for example
    by creating the exploit artifact, preparing a description of the exploit, and staging the exploit and associated
    files in a publishing system.
    """

    # prompt a human to prepare the exploit for publication


class ReprioritizeExploit(btz.AlwaysSucceed):
    """This node represents the process of reprioritizing the exploit for the vulnerability.
    The priority of the exploit may change as the vulnerability is analyzed and the exploit is prepared for publication.
    In a real implementation, this would be a prompt for a human to reprioritize the production of the exploit.
    In our stub implementation, this node always succeeds.
    """

    # reprioritize the production of the exploit or prompt a human to do so


class NoPublishFix(btz.AlmostAlwaysFail):
    """This condition is used to check if the fix for the vulnerability should be published. In a real implementation,
    this would be a simple check to see if the fix should be published based on the publication intents set elsewhere
    in the workflow. In most cases the fix should be published, so this condition fails in 9 out of 10 attempts in
    our stub implementation.
    """

    # check if the fix for the vulnerability should be published


class PrepareFix(btz.AlmostAlwaysSucceed):
    """This node represents the process of preparing the fix for the vulnerability to be published. In a real
    implementation, this would probably be a prompt for a human to prepare the fix for publication, for example by
    creating the fix artifact, preparing a description of the fix, and staging the fix and associated files in a
    publishing system. In our stub implementation, this node succeeds in 9 out of 10 attempts, allowing us to
    exercise the rest of the workflow.
    """

    # prompt a human to prepare the fix for publication


class ReprioritizeFix(btz.AlwaysSucceed):
    """This node represents the process of reprioritizing the fix for the vulnerability.
    The priority of the fix may change as the vulnerability is analyzed and the fix is prepared for publication.
    In a real implementation, this would be a prompt for a human to reprioritize the production of the fix.
    In our stub implementation, this node always succeeds.
    """

    # reprioritize the production of the fix or prompt a human to do so


class NoPublishReport(btz.AlmostAlwaysFail):
    """This condition is used to check if the report for the vulnerability should be published. In a real
    implementation, this would be a simple check to see if the report should be published based on the publication
    intents. In most cases the report should be published, so this condition fails in 9 out of 10 attempts in our
    stub implementation.
    """

    # check if the report for the vulnerability should be published


class PrepareReport(btz.AlmostAlwaysSucceed):
    """This node represents the process of preparing the report for the vulnerability to be published. In a real
    implementation, this would probably be a prompt for a human to prepare the report for publication, for example by
    creating the report artifact, preparing a description of the report, and staging the report and associated files
    in a publishing system. In our stub implementation, this node succeeds in 9 out of 10 attempts, allowing us to
    exercise the rest of the workflow.
    """

    # prompt a human to prepare the report for publication


class ReprioritizeReport(btz.AlwaysSucceed):
    """This node represents the process of reprioritizing the report for the vulnerability.
    The priority of the report may change as the vulnerability is analyzed and the report is prepared for publication.
    In a real implementation, this would be a prompt for a human to reprioritize the production of the report.
    In our stub implementation, this node always succeeds.
    """

    # reprioritize the production of the report or prompt a human to do so
