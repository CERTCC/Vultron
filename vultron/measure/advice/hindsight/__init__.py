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
"""Hindsight marks: each step a case took, graded by the advice before it
(#6672).

:func:`hindsight_mark` reads the states the case had reached just before an
entry and just after it, finds the move of the advice open before the entry
that makes the same change, and grades that move by its band and layer:

* **best**: layer 1 of the first band, harm-free then trade-off, that holds
  any move, so a trade-off move is best when no harm-free move is open;
* **good**: harm-free, not best;
* **sub-optimal**: trade-off, not best, saying so when a harm-free move
  dominated it;
* **neutral**: unhelpful with every part of its shift zero, and a move that
  keeps every state, which is advice, not a step;
* **bad**: unhelpful with some vendor's part negative.

Two marks grade nothing.  **Chance** marks an event no participant chooses,
whatever the advice: an exploit made public or attacks observed (X, A), and
the public becoming aware of the vul, unless an embargo ended on its own
terms before it.  **Not a move** marks every other entry: one that changes no state the advice weighs, such as a
note or a consent answer (PEC moves are not advised yet), one whose change no
advised move makes, one whose move has no band, and an entry with no advice
before it.

The case public state P means the public is aware the vul exists, not that
anyone published: a public exploit forces it, and so may a leak.  The ledger
records only that the case became public, never whether a participant
published, so the vul becoming public is chance, with one exception: when the
case's embargo had ended on its own terms at or before it, the entry is
graded as the advice's public-awareness move, a participant's publication
(:data:`~vultron.measure.advice.shifts.CHANCE_EVENTS` holds publication
as a move).  Only the first
publication makes the case public; a later one changes no state and grades
nothing.  Telling a publication from a leak is #6732.

An entry is one step, so it gets one mark.  When it changes several machines,
the first machine in this order decides: the public state, a fix path, the
embargo, report management.  A case-state event drives the others, as a
publication ends an embargo, never the reverse.  Only a move of that machine
is the step: a change no single move makes, such as report management
passing two states in one entry, grades nothing, and is never passed over
for a later machine's change.

The package has one module per concern, and every name is imported from
here:

* :mod:`~vultron.measure.advice.hindsight.mark` — the marks, their notes,
  and :class:`NarrativeMark`.
* :mod:`~vultron.measure.advice.hindsight.taken` — which move of the advice
  an entry took (:func:`taken_move`).
* :mod:`~vultron.measure.advice.hindsight.chance` — when an entry's change
  is chance.
* :mod:`~vultron.measure.advice.hindsight.grade` — the mark itself
  (:func:`hindsight_mark`).
"""

from vultron.measure.advice.hindsight.chance import (
    embargo_ended_on_own_terms,
)
from vultron.measure.advice.hindsight.grade import hindsight_mark
from vultron.measure.advice.hindsight.mark import (
    ADVICE_GAP,
    DID_AS_WELL,
    FORCED_BY_EXPLOIT,
    GRADED,
    NO_ADVICE,
    NO_ADVISED_MOVE,
    NO_KNOWN_PUBLISHER,
    NO_STATE_CHANGE,
    REGISTER_PROBLEM,
    SHADED,
    UNLISTED_CHANCE,
    HindsightMark,
    NarrativeMark,
    no_band,
)
from vultron.measure.advice.hindsight.taken import (
    PUBLIC_EVENTS,
    owns_state,
    register_trigger,
    taken_move,
)

__all__ = [
    "ADVICE_GAP",
    "DID_AS_WELL",
    "FORCED_BY_EXPLOIT",
    "GRADED",
    "NO_ADVICE",
    "NO_ADVISED_MOVE",
    "NO_KNOWN_PUBLISHER",
    "NO_STATE_CHANGE",
    "PUBLIC_EVENTS",
    "REGISTER_PROBLEM",
    "SHADED",
    "UNLISTED_CHANCE",
    "HindsightMark",
    "NarrativeMark",
    "embargo_ended_on_own_terms",
    "hindsight_mark",
    "no_band",
    "owns_state",
    "register_trigger",
    "taken_move",
]
