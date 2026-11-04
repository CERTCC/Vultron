"""Publication workflow fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Report Management publication sub-workflow (``PublicationBt``).  Each node
represents an external-dependency touchpoint — a human decision, environmental
check, or system integration hook — that will eventually be replaced by
production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 and BT-16-007 (named
integration-point nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

The ``PrioritizePublicationIntents`` Evaluator is the surviving call-out point
for Production Collapse 2 (ADR-0028 / BT-20-002): it writes a structured
:class:`~vultron.core.behaviors.report.publication_intent.PublicationIntentDecision`
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
- Catalog: ``docs/developer/reference/bt-fuzzer/rm-publication.md``
- ADR: ``docs/adr/0028-publication-intent-bt-collapse.md``
"""

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

from vultron.demo.fuzzer.report_management.publication.advisory import (
    DraftAdvisoryArtifact,
    ReviewAdvisoryDraft,
    ReviseAdvisoryDraft,
    SubmitAdvisoryArtifact,
)
from vultron.demo.fuzzer.report_management.publication.intents import (
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

__all__ = [
    "AllPublished",
    "DraftAdvisoryArtifact",
    "ExploitReady",
    "NoPublishExploit",
    "NoPublishFix",
    "NoPublishReport",
    "PrepareExploit",
    "PrepareFix",
    "PrepareReport",
    "PrioritizePublicationIntents",
    "PublicationIntentsSet",
    "Publish",
    "ReprioritizeExploit",
    "ReprioritizeFix",
    "ReprioritizeReport",
    "ReviewAdvisoryDraft",
    "ReviseAdvisoryDraft",
    "SubmitAdvisoryArtifact",
]
