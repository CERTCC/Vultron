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
"""Blackboard contract between the publication tree and its call-out backends.

The ``PrioritizePublicationIntents`` call-out point (ADR-0028, BT-18-001)
writes a :class:`PublicationIntentDecision` record under
:data:`INTENT_DECISION_KEY`; the ``ShouldPublish*`` gates in
:mod:`vultron.core.behaviors.report.publication_tree` read it.  Both the tree
and every backend that implements the call-out point — the core DETERMINISTIC
bundle in :mod:`vultron.core.behaviors.call_out.bundles.publication` and the
simulation-layer fuzzer — depend on this contract, so it lives in a module that
imports neither of them (CS-05-003).
"""

from pydantic import BaseModel

#: Blackboard key under which the ``PrioritizePublicationIntents`` Evaluator
#: writes its :class:`PublicationIntentDecision` record and from which the
#: ``ShouldPublish*`` gate nodes read it (BT-18-001).
INTENT_DECISION_KEY = "publication_intent_decision"


class PublicationIntentDecision(BaseModel):
    """Structured output record for the PrioritizePublicationIntents call-out point.

    Written to the blackboard key :data:`INTENT_DECISION_KEY` by the
    ``PrioritizePublicationIntents`` Evaluator node on SUCCESS (BT-18-001).
    The three boolean fields directly gate the three named per-artifact
    publication arms (ADR-0028); the removed ``NoPublish*`` bypass leaves are
    replaced by ``ShouldPublish*`` reads on these fields.

    Field defaults encode the standard CVD outcome — publish the fix and the
    vulnerability report, withhold the exploit — matching the simulator's
    ``NoPublishFix`` / ``NoPublishReport`` (``AlmostAlwaysFail``) and
    ``NoPublishExploit`` (``UsuallySucceed``) probabilities.  A real Evaluator
    backend overrides these per case policy.

    Attributes:
        publish_exploit: Whether the exploit artifact should be published.
        publish_fix: Whether the fix artifact should be published.
        publish_report: Whether the vulnerability report/advisory should be
            published.
        rationale: Human-readable or machine-generated explanation of the
            publication-intent decision.
    """

    publish_exploit: bool = False
    publish_fix: bool = True
    publish_report: bool = True
    rationale: str = ""
