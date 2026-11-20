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

"""The hindsight mark model: the marks, the notes a line that is not graded
gives, and :class:`NarrativeMark`, one narrative line's mark (#6672).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.measure.advice.bands import Band
from vultron.measure.advice.case import AllowedMove
from vultron.primitives import NonEmptyString


class HindsightMark(StrEnum):
    """How good the step an entry took was, by the advice open before it."""

    BEST = "best"
    GOOD = "good"
    SUB_OPTIMAL = "sub-optimal"
    NEUTRAL = "neutral"
    BAD = "bad"
    #: Not graded: an event no participant chooses.
    CHANCE = "chance"
    #: Not graded: an act that is not a move of the advice.
    NOT_A_MOVE = "not a move"


#: The marks that grade a move of the advice; the others grade nothing.
GRADED: frozenset[HindsightMark] = frozenset(
    {
        HindsightMark.BEST,
        HindsightMark.GOOD,
        HindsightMark.SUB_OPTIMAL,
        HindsightMark.NEUTRAL,
        HindsightMark.BAD,
    }
)

#: The marks of a move in a shaded band, which take the band's shade.
SHADED: frozenset[HindsightMark] = frozenset(
    {HindsightMark.BEST, HindsightMark.GOOD, HindsightMark.SUB_OPTIMAL}
)

DID_AS_WELL = "A harm-free move did as well."
"""What a sub-optimal mark adds when a harm-free move dominated its move."""

NO_ADVICE = "No move advice is open before the case's first entry."
"""Why the first entry grades nothing."""

ADVICE_GAP = (
    "The ledger before this entry has a hole, so no move advice is open."
)
"""Why an entry after a hole grades nothing."""

NO_STATE_CHANGE = "The entry changes no state the move advice weighs."
"""Why a note, an invitation or a consent answer grades nothing."""

NO_ADVISED_MOVE = (
    "No move the advice before this entry lists makes its change."
)
"""Why an entry whose change no single advised move makes grades nothing."""

FORCED_BY_EXPLOIT = (
    "The exploit was already public, which makes the public aware of the"
    " vul: no participant chose this."
)
"""Why public awareness that follows a public exploit grades nothing."""

NO_KNOWN_PUBLISHER = (
    "Neither a public exploit nor an embargo that ended on its own terms"
    " comes before the vul became public, so the ledger cannot tell a"
    " publication from a leak (#6732)."
)
"""Why the public becoming aware of the vul is chance unless an embargo
ended on its own terms at or before it."""

UNLISTED_CHANCE = "No participant chooses this event."
"""Why an X or A change the advice lists no move for grades nothing."""

REGISTER_PROBLEM = (
    "The embargo register this entry leaves gives no EM state, so no EM move"
    " makes its change."
)
"""Why an entry that breaks the embargo register grades nothing."""


def no_band(reason: str) -> str:
    """Why an entry whose move has no band grades nothing."""
    return f"The move has no band: {reason}"


class NarrativeMark(BaseModel):
    """The hindsight mark of one case narrative line.

    Fields:
        log_index: The line's entry's log index.
        mark: The mark.
        move: The move of the advice before the entry that the entry made;
            ``None`` when it made none.
        band: The move's band, for a move that has one.
        layer: The move's layer, in a harm-free or trade-off band.
        deepest_layer: The deepest layer of the advice the move was graded
            by, so a page shades the mark as that advice's band legend
            shades the layer.
        note: What the mark adds: that a harm-free move did as well, for a
            sub-optimal move a harm-free move dominated, or why a line is
            not graded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_index: int = Field(ge=0)
    mark: HindsightMark
    move: AllowedMove | None = None
    band: Band | None = None
    layer: int | None = Field(default=None, ge=1)
    deepest_layer: int | None = Field(default=None, ge=1)
    note: NonEmptyString | None = None

    @model_validator(mode="after")
    def _fits_its_mark(self) -> NarrativeMark:
        problems: list[str] = []
        shaded = self.mark in SHADED
        if self.mark in GRADED and self.move is None:
            problems.append(f"a {self.mark} mark grades a move")
        if shaded != (self.layer is not None):
            problems.append(
                "only a best, good or sub-optimal mark has a layer"
            )
        if (self.layer is None) != (self.deepest_layer is None):
            problems.append("a layer comes with its advice's deepest layer")
        if (
            self.layer is not None
            and self.deepest_layer is not None
            and self.layer > self.deepest_layer
        ):
            problems.append("the layer is deeper than its advice's deepest")
        if shaded and self.band not in (Band.HARM_FREE, Band.TRADE_OFF):
            problems.append(
                "a best, good or sub-optimal mark is in the harm-free or"
                " trade-off band"
            )
        if self.mark not in GRADED and self.note is None:
            problems.append("a line that is not graded says why")
        if problems:
            raise ValueError("; ".join(problems))
        return self


__all__ = [
    "ADVICE_GAP",
    "DID_AS_WELL",
    "FORCED_BY_EXPLOIT",
    "GRADED",
    "NO_ADVICE",
    "NO_ADVISED_MOVE",
    "NO_KNOWN_PUBLISHER",
    "NO_STATE_CHANGE",
    "REGISTER_PROBLEM",
    "SHADED",
    "UNLISTED_CHANCE",
    "HindsightMark",
    "NarrativeMark",
    "no_band",
]
