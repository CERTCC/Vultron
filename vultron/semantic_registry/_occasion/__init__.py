"""Occasions: the situations a sender conveys with one registry entry.

An **occasion** is a situation in a case that a sender conveys by sending a
particular wire activity, sometimes narrowed by a distinguishing field value,
state context or sender standing (glossary, ADR-0128).  One ``SemanticEntry``
carries one or more occasions: three situations — vendor awareness, fix ready,
fix deployed — share ``Add(ParticipantStatus)``, told apart by its ``vf`` and
``d`` dimensions.

This module holds the value objects only.  An occasion records what only a
human can supply; everything derivable from it (the mapping status, the
"Sent by" and "Send to" wording) is derived by ``vultron.metadata.msm``
(MSM-08-005, MSM-08-006, MSM-08-009).

Spec: MSM-08-001, MSM-08-002, MSM-08-005, MSM-08-007, MSM-08-009,
MSM-08-011.
"""

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

from vultron.semantic_registry._occasion.annotations import wire_spelling
from vultron.semantic_registry._occasion.distinguisher import (
    Distinguisher,
    FieldValue,
    SenderStanding,
    StateContext,
)
from vultron.semantic_registry._occasion.occasion import (
    ANCHOR_PATTERN,
    Occasion,
)
from vultron.semantic_registry._occasion.vocabulary import (
    HowToGuide,
    MessagePage,
    ProtocolShorthand,
)

__all__ = [
    "ANCHOR_PATTERN",
    "Distinguisher",
    "FieldValue",
    "HowToGuide",
    "MessagePage",
    "Occasion",
    "ProtocolShorthand",
    "SenderStanding",
    "StateContext",
    "wire_spelling",
]
