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
"""Publication workflow fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Report Management publication sub-workflow (``PublicationBt``).  Each node
represents an external-dependency touchpoint — a human decision, environmental
check, or system integration hook — that will eventually be replaced by
production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/publication.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    OftenSucceed,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import ComposerCallOutPoint


class AllPublished(AlmostAlwaysFail):
    """Check whether all intended publication artifacts have been published.

    Semantic function:
        Condition — check whether all intended publication artifacts
        (report, fix, exploit) for the vulnerability have been published.
        In production this would be a metadata check against a publication
        status field on the case record.  The fuzzer fails most of the
        time because publication is an active goal being worked toward.

    Input category: Environmental check.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — publication status flag on the case
    record; fully automatable as a metadata check.
    """


class PublicationIntentsSet(UsuallyFail):
    """Check whether publication intentions have been established for the case.

    Semantic function:
        Condition — check whether publication intentions (what to publish,
        when, and in what format) have been established for this case.
        In production this would be a check against case metadata or a
        structured publication-intent field.  The fuzzer fails most of
        the time because setting publication intents is an early workflow
        step being modeled.

    Input category: Environmental check.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **High** — publication intent flags on the case
    record; fully automatable as a metadata check.
    """


class PrioritizePublicationIntents(AlwaysSucceed):
    """Establish and record publication intentions for the case.

    Semantic function:
        Action — establish and record publication intentions: what
        artifacts to publish, their priority order, timing, and format.
        In production this involves structured editorial or policy
        decisions, potentially with human analyst input.  The fuzzer
        always succeeds to keep the workflow progressing.

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — standard policy-driven publication
    priorities (e.g., always publish report and fix) can be automated;
    editorial or legal exceptions require human judgment.
    """


class Publish(AlmostAlwaysSucceed):
    """Execute the publication of a prepared artifact to the intended audience.

    Semantic function:
        Action — publish a prepared artifact (advisory, patch, bulletin,
        etc.) to the intended audience.  In production this could be an
        API call to an advisory publishing platform (NVD, CVE.org, CMS,
        package repository) or a prompt for a human to complete the
        publication step.  The fuzzer succeeds almost always, allowing
        the rest of the workflow to be exercised.

    Input category: System integration.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — advisory platform APIs enable fully
    automated artifact publication.
    """


class NoPublishExploit(UsuallySucceed):
    """Check the publication intent flag for the exploit artifact.

    Semantic function:
        Condition — check the publication intent flag for the exploit
        artifact; ``SUCCESS`` means "do not publish exploit".  In
        production this is a read of the exploit publication intent flag
        set by ``PrioritizePublicationIntents``.  The fuzzer succeeds
        (i.e., no exploit publication) in most cases, reflecting that
        exploit publication is not always required or desired.

    Input category: Environmental check / policy.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — read the exploit publication intent
    flag from the case record; fully automatable.
    """


class ExploitReady(OftenSucceed):
    """Check whether the exploit artifact is ready for publication.

    Semantic function:
        Condition — check whether the exploit artifact is ready for
        publication (prepared, reviewed, and staged).  In production
        this is a metadata check against an artifact staging-status field
        in the publishing pipeline.  The fuzzer succeeds more often than
        not once preparation has started.

    Input category: Environmental check.

    Success probability: 0.70 (``OftenSucceed``).

    Automation potential: **High** — artifact staging-status check in the
    publishing pipeline; fully automatable.
    """


class PrepareExploit(AlmostAlwaysSucceed):
    """Create, document, and stage the exploit artifact for publication.

    Semantic function:
        Action — create, document, and stage the exploit artifact for
        publication (write-up, code packaging, filing in publishing
        system).  In production this would typically be a prompt for a
        human security researcher to package and document the
        proof-of-concept.  The fuzzer succeeds almost always.

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low** — write-up and proof-of-concept
    packaging require human security researcher expertise; not
    automatable in the general case.
    """


class ReprioritizeExploit(AlwaysSucceed):
    """Update the priority of the exploit artifact in the publication queue.

    Semantic function:
        Action — update the priority of the exploit artifact in the
        publication queue (e.g., in response to a changing threat
        landscape or embargo state change).  In production this is a
        human analyst decision or an automated policy trigger.  The
        fuzzer always succeeds.

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — embargo state changes and
    threat-level updates can trigger automated reprioritization rules;
    human override may be needed for unusual cases.
    """


class NoPublishFix(AlmostAlwaysFail):
    """Check the publication intent flag for the fix artifact.

    Semantic function:
        Condition — check the publication intent flag for the fix
        artifact; ``SUCCESS`` means "do not publish fix".  In production
        this is a read of the fix publication intent flag.  The fuzzer
        fails most of the time because fix publication is the standard
        expected outcome of CVD.

    Input category: Environmental check / policy.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — read the fix publication intent flag
    from the case record; fully automatable.
    """


class PrepareFix(AlmostAlwaysSucceed):
    """Create, document, and stage the fix artifact for publication.

    Semantic function:
        Action — create, document, and stage the fix artifact for
        publication (patch notes, release artifacts, advisory text).  In
        production this involves the engineering team's patch release
        pipeline and content-authoring workflow.  The fuzzer succeeds
        almost always, allowing the rest of the workflow to be exercised.

    Input category: System integration.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low–Medium** — CI/CD pipeline can automate
    patch build and packaging; advisory text and release notes typically
    require human authoring and review.
    """


class ReprioritizeFix(AlwaysSucceed):
    """Update the priority of the fix artifact in the publication queue.

    Semantic function:
        Action — update the priority of the fix artifact in the
        publication queue.  In production this is a human analyst
        decision or an automated policy trigger.  The fuzzer always
        succeeds.

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — embargo state changes and
    threat-level updates can trigger automated reprioritization rules;
    human override may be needed.
    """


class NoPublishReport(AlmostAlwaysFail):
    """Check the publication intent flag for the vulnerability report artifact.

    Semantic function:
        Condition — check the publication intent flag for the
        vulnerability report artifact; ``SUCCESS`` means "do not publish
        report".  In production this is a read of the report publication
        intent flag.  The fuzzer fails most of the time because report
        publication is the standard CVD outcome.

    Input category: Environmental check / policy.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **High** — read the report publication intent
    flag from the case record; fully automatable.
    """


class PrepareReport(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Create, review, and stage the vulnerability advisory for publication.

    Semantic function:
        Action — create, review, and stage the vulnerability advisory or
        report artifact for publication.  In production this involves
        human analyst authoring, editorial review, approval workflow, and
        staging in the advisory publishing pipeline.  The fuzzer succeeds
        almost always, allowing the rest of the workflow to be exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: prepared_report_artifact: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low** — advisory writing requires human
    expertise and editorial judgment; review and approval workflow also
    typically involves human stakeholders.
    """

    output_keys = {"prepared_report_artifact": str}


class ReprioritizeReport(AlwaysSucceed):
    """Update the priority of the report artifact in the publication queue.

    Semantic function:
        Action — update the priority of the report artifact in the
        publication queue.  In production this is a human analyst
        decision or an automated policy trigger (e.g., on embargo exit or
        threat escalation).  The fuzzer always succeeds.

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — policy-triggered reprioritization
    (e.g., on embargo exit or threat escalation) is automatable; complex
    editorial decisions require human oversight.
    """
