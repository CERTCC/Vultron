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

"""Driven port: who else should take part in a case, and why (ADR-0186).

An actor asks "given this case, who would you suggest?" through this one
port, whether a call-out inside a tree or a Sentinel outside core asks
(BT-24-001).  Neither calls the port directly: both go through the core
service
:func:`~vultron.core.services.participant_suggestion.suggest_case_participants`,
which projects the case to a
:class:`~vultron.core.models.participant_suggestion.SuggestionContext` first
(BT-24-008).  How an adapter finds its answer (a declared table, a
directory, a search and a winnowing step, a memory of past cases) is its own
choice and not part of this contract.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from vultron.core.models.participant_suggestion import (
    ParticipantSuggestion,
    SuggestionContext,
)


@runtime_checkable
class ParticipantSuggestionPort(Protocol):
    """Port: suggest the parties a case is missing.

    An adapter implements one method, :meth:`suggest_participants`.  It
    receives only the suggestion context, never the case, so it cannot pass
    on what it was never given (BT-24-002).

    **Prefer over-suggesting.**  An adapter should rather suggest a party
    that turns out not to be needed than leave out one that is: a needless
    suggestion costs a decline, while a missed party may never hear of the
    vulnerability (BT-24-005).

    **Pointing the port at a third-party service is a disclosure.**  An
    adapter that calls an outside service hands that service the whole
    suggestion context, report content included, and the case may be under
    embargo.  Choosing such an adapter is the deployment's trust decision;
    the port cannot make it.

    An adapter reached from a tree answers within the call-out time budget
    (BT-18-015) and does no unbounded blocking I/O (BT-18-025).  One too slow
    for that is reachable only from a Sentinel, which no tick bounds.
    """

    def suggest_participants(
        self, context: SuggestionContext
    ) -> Sequence[ParticipantSuggestion]:
        """Suggest the parties *context*'s case is missing.

        Synchronous.  An answer with no suggestions is valid (BT-24-004).
        An adapter may leave out a party the context already lists as a
        participant, and the caller decides what to do with each suggestion,
        including when to invite (BT-24-006).

        Raises:
            VultronError: The adapter could not answer, for example because
                the service it calls is unreachable.
        """
        ...  # pragma: no cover


__all__ = ["ParticipantSuggestionPort"]
