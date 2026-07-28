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

The ``PrioritizePublicationIntents`` Evaluator is the surviving call-out point
for Production Collapse 2 (ADR-0028 / BT-20-002): it writes a structured
:class:`~vultron.core.behaviors.report.publication_tree.PublicationIntentDecision`
record that gates the three per-artifact arms of
``create_publication_tree``.  The ``PublicationIntentsSet`` flag check and the
``NoPublish*`` bypass leaves remain here as catalogued simulator stand-ins but
are no longer wired into the production tree (mirrors how the Production
Collapse 1 flag nodes remain in ``acquire_exploit.py``).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/publication.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005,
  BT-20-002
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
- ADR: ``docs/adr/0028-publication-intent-bt-collapse.md``
"""

from __future__ import annotations

from vultron.core.behaviors.report.publish_artifact_tree import (
    AdvisoryReviewDecision,
)
from vultron.core.behaviors.report.publication_tree import (
    PublicationIntentDecision,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    OftenSucceed,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    ComposerCallOutPoint,
    EvaluatorCallOutPoint,
)


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


class PrioritizePublicationIntents(EvaluatorCallOutPoint, AlwaysSucceed):
    """Establish and record publication intentions for the case.

    Semantic function:
        Action — establish and record publication intentions: which
        artifacts (exploit, fix, report) to publish, and why.  In
        production this involves structured editorial or policy decisions,
        potentially with human analyst input.  The fuzzer always succeeds
        to keep the workflow progressing.

    This is the surviving Evaluator for Production Collapse 2 (ADR-0028 /
    BT-20-002).  It writes a structured ``PublicationIntentDecision`` record
    whose boolean fields gate the three per-artifact arms of
    ``create_publication_tree``, replacing the ``PublicationIntentsSet`` flag
    check and the ``NoPublish*`` bypass leaves.  The fuzzer backend writes a
    default ``PublicationIntentDecision()`` (publish fix + report, withhold
    exploit); a real backend overrides per case policy.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: publication_intent_decision: PublicationIntentDecision
        (SUCCESS only; default instance written by fuzzer backend)

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — standard policy-driven publication
    priorities (e.g., always publish report and fix) can be automated;
    editorial or legal exceptions require human judgment.
    """

    output_keys = {"publication_intent_decision": PublicationIntentDecision}


class Publish(ActuatorCallOutPoint, AlmostAlwaysSucceed):
    """Execute the publication of a prepared artifact to the intended audience.

    Semantic function:
        Action — publish a prepared artifact (advisory, patch, bulletin,
        etc.) to the intended audience.  In production this could be an
        API call to an advisory publishing platform (NVD, CVE.org, CMS,
        package repository) or a prompt for a human to complete the
        publication step.  The fuzzer succeeds almost always, allowing
        the rest of the workflow to be exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; artifact context from construction time)
      Output keys: (none — side effect: publish artifact to intended audience)

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


class PrepareExploit(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Create, document, and stage the exploit artifact for publication.

    Semantic function:
        Action — create, document, and stage the exploit artifact for
        publication (write-up, code packaging, filing in publishing
        system).  In production this would typically be a prompt for a
        human security researcher to package and document the
        proof-of-concept.  The fuzzer succeeds almost always.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: prepared_exploit_artifact: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low** — write-up and proof-of-concept
    packaging require human security researcher expertise; not
    automatable in the general case.
    """

    output_keys = {"prepared_exploit_artifact": str}


class ReprioritizeExploit(EvaluatorCallOutPoint, AlwaysSucceed):
    """Update the priority of the exploit artifact in the publication queue.

    Semantic function:
        Action — update the priority of the exploit artifact in the
        publication queue (e.g., in response to a changing threat
        landscape or embargo state change).  In production this is a
        human analyst decision or an automated policy trigger.  The
        fuzzer always succeeds.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates exploit publication context from caller's DataLayer)
      Output keys: reprioritize_exploit_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — embargo state changes and
    threat-level updates can trigger automated reprioritization rules;
    human override may be needed for unusual cases.
    """

    output_keys = {"reprioritize_exploit_verdict": str}


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


class PrepareFix(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Create, document, and stage the fix artifact for publication.

    Semantic function:
        Action — create, document, and stage the fix artifact for
        publication (patch notes, release artifacts, advisory text).  In
        production this involves the engineering team's patch release
        pipeline and content-authoring workflow.  The fuzzer succeeds
        almost always, allowing the rest of the workflow to be exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: prepared_fix_artifact: str  (SUCCESS only)

    Input category: System integration.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low–Medium** — CI/CD pipeline can automate
    patch build and packaging; advisory text and release notes typically
    require human authoring and review.
    """

    output_keys = {"prepared_fix_artifact": str}


class ReprioritizeFix(EvaluatorCallOutPoint, AlwaysSucceed):
    """Update the priority of the fix artifact in the publication queue.

    Semantic function:
        Action — update the priority of the fix artifact in the
        publication queue.  In production this is a human analyst
        decision or an automated policy trigger.  The fuzzer always
        succeeds.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates fix publication context from caller's DataLayer)
      Output keys: reprioritize_fix_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — embargo state changes and
    threat-level updates can trigger automated reprioritization rules;
    human override may be needed.
    """

    output_keys = {"reprioritize_fix_verdict": str}


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


class ReprioritizeReport(EvaluatorCallOutPoint, AlwaysSucceed):
    """Update the priority of the report artifact in the publication queue.

    Semantic function:
        Action — update the priority of the report artifact in the
        publication queue.  In production this is a human analyst
        decision or an automated policy trigger (e.g., on embargo exit or
        threat escalation).  The fuzzer always succeeds.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates report publication context from caller's DataLayer)
      Output keys: reprioritize_report_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — policy-triggered reprioritization
    (e.g., on embargo exit or threat escalation) is automatable; complex
    editorial decisions require human oversight.
    """

    output_keys = {"reprioritize_report_verdict": str}


# ---------------------------------------------------------------------------
# Production Collapse 4 (ADR-0030 / BT-20-004): Publish leaf pipeline nodes
# ---------------------------------------------------------------------------


class DraftAdvisoryArtifact(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Draft the advisory artifact from case data.

    Semantic function:
        Action — generate a draft advisory artifact (CSAF JSON, CVE record,
        advisory text, or equivalent) from case data.  In production this
        would involve a templating engine or LLM-driven composition step
        that pulls vulnerability details, fix information, and affected
        product data from the case record.  The fuzzer succeeds almost
        always, allowing the rest of the pipeline to be exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — reads case context from caller's DataLayer)
      Output keys: draft_advisory_artifact: str  (SUCCESS only)

    Input category: System integration / Composer.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium–High** — structured artifact generation
    from well-formed case data (CSAF templates, CVE JSON schema) is
    automatable; narrative advisory text may benefit from human review.
    """

    output_keys = {"draft_advisory_artifact": str}


class ReviewAdvisoryDraft(EvaluatorCallOutPoint, AlwaysSucceed):
    """Review and approve the advisory draft.

    Semantic function:
        Action — review the drafted advisory artifact and produce an
        :class:`~vultron.core.behaviors.report.publish_artifact_tree.
        AdvisoryReviewDecision` record indicating approval status and
        whether revision is required.  The default fuzzer implementation
        always approves (``needs_revision=False``) so the pipeline
        functions end-to-end before a real review agent is available
        (AC-3, ADR-0030).  A real backend may involve human editorial
        review, automated QA checks, or both.

    Blackboard contract (BT-18-001):
      Input keys:  draft_advisory_artifact: str  (reads the Composer output)
      Output keys: advisory_review_decision: AdvisoryReviewDecision
        (SUCCESS only; default instance written by fuzzer backend)

    Input category: Human decision / QA integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **Medium** — automated schema validation and
    completeness checks are feasible; editorial approval and legal review
    typically require human judgment.
    """

    output_keys = {"advisory_review_decision": AdvisoryReviewDecision}


class ReviseAdvisoryDraft(ComposerCallOutPoint, AlmostAlwaysSucceed):
    """Revise the advisory draft based on review feedback.

    Semantic function:
        Action — incorporate feedback from ``ReviewAdvisoryDraft`` and
        produce a revised advisory artifact.  This node runs only when the
        Evaluator sets ``needs_revision=True``; when the Evaluator approves
        without requesting changes the revision arm is a graceful no-op.
        The fuzzer succeeds almost always.

    Blackboard contract (BT-18-001):
      Input keys:  advisory_review_decision: AdvisoryReviewDecision
        (reads the Evaluator output for feedback guidance)
      Output keys: draft_advisory_artifact: str  (overwrites on SUCCESS)

    Input category: Human decision / Composer.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Low–Medium** — structured revision based on
    machine-readable feedback is partially automatable; editorial revisions
    typically require human involvement.
    """

    output_keys = {"draft_advisory_artifact": str}


class SubmitAdvisoryArtifact(ActuatorCallOutPoint, AlmostAlwaysSucceed):
    """Submit the finalized advisory artifact to the external advisory platform.

    Semantic function:
        Action — submit the reviewed (and optionally revised) advisory
        artifact to the target advisory platform (NVD, CVE.org, CMS,
        package repository, or equivalent) via an API call.  In production
        this is the final side-effecting step; the fuzzer succeeds almost
        always, matching the original ``Publish`` Actuator probability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — artifact context from construction time)
      Output keys: (none — side effect: publish artifact to advisory platform)

    Input category: System integration / Actuator.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** — advisory platform APIs (NVD, CVE.org,
    CMS, package repository) enable fully automated artifact submission.
    """
