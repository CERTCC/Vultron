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

"""Score a case-state sequence through its valid completions (ADR-0182).

A real case's sequence is almost always incomplete, and an incomplete
sequence is incomplete only because its events have not happened yet: the
event-history layer refuses a ledger with holes (ADR-0174).  So the sequence
is scored by what it can still become.  :func:`score_prefix` lists every
valid completion of an accepted prefix (CSB-17-011), weights each by the
indifference walk's probability of it from where the prefix stands
(:func:`vultron.measure.baselines.completion_probabilities`, the one walk the
baselines use too), and scores each complete history
(:func:`~vultron.measure.scoring.complete.history_score`).

A sequence that is not an accepted prefix is refused with its reason
(:class:`NotAHistoryPrefixError`), never scored.
"""

from collections.abc import Iterable

from vultron.core.states.cs_invariants import CSEvent, replay_cs_history
from vultron.errors import (
    VultronInvalidStateTransitionError,
    VultronValidationError,
)
from vultron.measure.baselines import completion_probabilities
from vultron.measure.scoring.model import (
    Completion,
    SequenceScore,
    VendorScore,
)
from vultron.measure.sequences import CaseStateSequence


class NotAHistoryPrefixError(ValueError):
    """A sequence is not an accepted case-state history prefix, so it has no score.

    Attributes:
        events: The sequence as given.
        reason: Why the prefix check refused it.
    """

    def __init__(self, events: Iterable[object], reason: str) -> None:
        self.events = tuple(events)
        self.reason = reason
        super().__init__(
            f"{self.events!r} is not a valid case-state history prefix:"
            f" {reason}"
        )


def _accepted_prefix(
    prefix: Iterable[CSEvent | str],
) -> tuple[CSEvent, ...]:
    """*prefix* as case-state events, once the prefix check accepts it.

    Raises:
        NotAHistoryPrefixError: the check refuses *prefix* (CSB-17-005).
    """
    given = tuple(prefix)
    try:
        replay_cs_history(given)
    except (
        VultronValidationError,
        VultronInvalidStateTransitionError,
    ) as exc:
        raise NotAHistoryPrefixError(given, str(exc)) from exc
    return tuple(CSEvent(event) for event in given)


def score_prefix(prefix: Iterable[CSEvent | str]) -> SequenceScore:
    """Score *prefix* through every valid completion of it.

    A complete history is its own only completion, so its expected, best and
    worst scores all equal its :func:`.history_score`.

    Raises:
        NotAHistoryPrefixError: *prefix* is not an accepted case-state
            history prefix.
    """
    events = _accepted_prefix(prefix)
    weights = completion_probabilities(events)
    return SequenceScore(
        prefix=events,
        completions=tuple(
            Completion(history=history, probability=probability)
            for history, probability in sorted(weights.items())
        ),
    )


def score_sequence(sequence: CaseStateSequence) -> VendorScore:
    """Score one vendor's projected sequence through its completions.

    The sequence's moved and implied events (CEH-05-009) are scored where
    the projection placed them: the model's transient states force them.
    """
    return VendorScore(
        participant=sequence.participant, score=score_prefix(sequence.kinds)
    )
