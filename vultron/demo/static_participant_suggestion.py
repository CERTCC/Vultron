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

"""The demos' participant-suggestion adapter: a declared table (BT-24-007).

Demo scenarios and tests answer the
:class:`~vultron.core.ports.participant_suggestion.ParticipantSuggestionPort`
from a candidate table the scenario declares, never from a directory or a
recommender service (ADR-0186).  :class:`StaticParticipantSuggester` is that
adapter: it holds the table's rows as
:class:`~vultron.core.models.participant_suggestion.ParticipantSuggestion`\\ s
and answers with them.

It knows nothing about stories or casts.  A scenario declares its table by
cast name, and
:func:`~vultron.demo.helpers.participant_suggestion.ask_who_else_belongs`
resolves each name to its actor id before it builds this adapter.
"""

from collections.abc import Iterable

from vultron.core.models.participant_suggestion import (
    ParticipantSuggestion,
    SuggestionContext,
)


class StaticParticipantSuggester:
    """Answer the participant-suggestion port from a declared table.

    Each row is one suggestion: an actor, the role it is suggested in, and
    why.  An actor suggested in two roles is two rows, because a suggestion
    carries one role (BT-24-004).

    The answer is the table, in its order, less every row whose actor the
    context already lists as a participant: the port lets an adapter leave
    out a party already in the case, and a demo that asked twice would
    otherwise suggest a party that has joined.  An empty table answers with
    no suggestions, which is a valid answer (BT-24-004).

    Implements
    :class:`~vultron.core.ports.participant_suggestion.ParticipantSuggestionPort`
    structurally.  It reads nothing outside its table and does no I/O, so it
    answers within any call-out time budget (BT-18-015).
    """

    def __init__(self, table: Iterable[ParticipantSuggestion]) -> None:
        """Hold *table* as this adapter's whole answer.

        Raises:
            TypeError: A row is not a :class:`ParticipantSuggestion`.  A
                demo's table is code, so a wrong row is a wiring error that
                fails at construction rather than on the first ask.
        """
        rows = tuple(table)
        wrong = sorted(
            {
                type(row).__name__
                for row in rows
                if not isinstance(row, ParticipantSuggestion)
            }
        )
        if wrong:
            raise TypeError(
                f"a candidate table holds ParticipantSuggestion rows, not "
                f"{wrong} (BT-24-004)"
            )
        self._table = rows

    @property
    def table(self) -> tuple[ParticipantSuggestion, ...]:
        """The declared rows, in their order."""
        return self._table

    def suggest_participants(
        self, context: SuggestionContext
    ) -> tuple[ParticipantSuggestion, ...]:
        """The table's rows whose actor *context*'s case does not hold yet."""
        present = {p.attributed_to for p in context.case_participants}
        return tuple(row for row in self._table if row.actor_id not in present)


__all__ = ["StaticParticipantSuggester"]
