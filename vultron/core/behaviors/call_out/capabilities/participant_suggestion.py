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
"""Core capability declaration for ``participant_suggestion`` (ADR-0186).

:class:`SuggestParticipantsCapability` is the thin Retriever call-out that
puts the participant-suggestion port inside a tree.  Its core backend,
:class:`~vultron.core.behaviors.call_out.bundles.participant_suggestion.SuggestParticipantsRetriever`,
asks the port through the one core service, which projects the case first
(BT-24-008).  Its simulation node, in
``vultron.demo.fuzzer.participant_suggestion``, subclasses the declaration
rather than restating it (BT-18-021).
"""

from __future__ import annotations

from typing import Final

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import RetrieverCapability
from vultron.core.models.participant_suggestion import ParticipantSuggestions

#: Input port: the id of the case the suggestions are for.
SUGGESTION_CASE_ID_KEY: Final[str] = "case_id"

#: Output port: the suggestions, one ``ParticipantSuggestions``.
PARTICIPANT_SUGGESTIONS_KEY: Final[str] = "participant_suggestions"


class SuggestParticipantsCapability(RetrieverCapability):
    """Suggest the parties a case is missing, each with a role and a reason.

    The output is one
    :class:`~vultron.core.models.participant_suggestion.ParticipantSuggestions`,
    so the seam's type check covers each suggestion it holds (BTND-03-021);
    an answer naming nobody is valid (BT-24-004).  A tree that places this
    Retriever pairs it with one ``suggest-actor-to-case`` Actuator per
    suggestion it acts on (BT-20-013).

    Blackboard contract (BT-18-001):
      Input keys:  case_id: str  (the case the suggestions are for)
      Output keys: participant_suggestions: ParticipantSuggestions  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — the case file lists who is
    in the case, not who is missing from it, and the participants it lists
    already reach the suggester in the suggestion context, so no read-first
    guard precedes this Retriever.
    """

    INPUT_PORTS = {
        SUGGESTION_CASE_ID_KEY: PortInformation(data_type=str, required=True),
    }
    OUTPUT_PORTS = {
        PARTICIPANT_SUGGESTIONS_KEY: PortInformation(
            data_type=ParticipantSuggestions, required=True
        ),
    }


__all__ = [
    "PARTICIPANT_SUGGESTIONS_KEY",
    "SUGGESTION_CASE_ID_KEY",
    "SuggestParticipantsCapability",
]
