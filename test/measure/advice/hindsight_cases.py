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

"""What the hindsight-mark tests share: the moves, advice and states each
test grades an entry by (#6672).

Each test builds the advice open before one entry by hand, with the states
the case reached just before and just after it, so each mark of the table
and each edge-case rule is pinned to the band and layer that sets it.
"""

from collections.abc import Callable, Sequence
from fractions import Fraction

from vultron.core.states.cs import CS, CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.rm import RM
from vultron.measure.advice import (
    BAND_ORDER,
    DOMINATED_BY_HARM_FREE,
    AdvisedMove,
    BandAdvice,
    CaseAdvice,
    NarrativeMark,
    ScopeParts,
    VendorHarm,
    VendorShift,
    band,
    harms,
    hindsight_mark,
)
from vultron.measure.advice.case import AllowedMove, UnbandedMove
from vultron.measure.history import (
    ReachedParticipant,
    ReachedState,
)
from vultron.measure.standing import (
    CSMove,
    EMMove,
    RMMove,
)

_VENDOR = "https://example.org/actors/vendor"
_VENDOR_2 = "https://example.org/actors/vendor-2"
_OWNER = "https://example.org/actors/owner"
_EMBARGO = "urn:uuid:embargo-1"
_EMBARGO_2 = "urn:uuid:embargo-2"

_ACCEPT = RMMove(participant=_VENDOR, source=RM.VALID, destination=RM.ACCEPTED)
_FIX = CSMove(
    participant=_VENDOR,
    event=CSEvent.F,
    source=CS.Vfdpxa,
    destination=CS.VFdpxa,
)
_PUBLISH = CSMove(
    participant=_VENDOR,
    event=CSEvent.P,
    source=CS.Vfdpxa,
    destination=CS.VfdPxa,
)
_EXPLOIT = CSMove(
    participant=_VENDOR,
    event=CSEvent.X,
    source=CS.Vfdpxa,
    destination=CS.VfdpXa,
)
_START = EMMove(
    participant=_OWNER,
    trigger=EM_Trigger.ACCEPT,
    source=EM.PROPOSED,
    destination=EM.ACTIVE,
)
_PROPOSE_AGAIN = EMMove(
    participant=_VENDOR,
    trigger=EM_Trigger.PROPOSE,
    source=EM.PROPOSED,
    destination=EM.PROPOSED,
)

_Parts = tuple[int, int]


def _advised(
    move: AllowedMove,
    parts: Sequence[_Parts],
    layer: int | None,
    top: bool = False,
    dominated: bool = False,
) -> AdvisedMove:
    """*move*, with each vendor's (end, embargo) part, in the band its
    parts set."""
    shift = tuple(ScopeParts(Fraction(e), Fraction(m)) for e, m in parts)
    vendors = (_VENDOR, _VENDOR_2)
    return AdvisedMove(
        move=move,
        shift=tuple(
            VendorShift(vendor=v, end=p.end, embargo=p.embargo)
            for v, p in zip(vendors, shift, strict=True)
        ),
        band=band(shift),
        layer=layer,
        top=top,
        leading_among_yours=False,
        harms=tuple(
            VendorHarm(vendor=vendors[h.vendor - 1], part=h.part, size=h.size)
            for h in harms(shift)
        ),
        dominated_by_harm_free=DOMINATED_BY_HARM_FREE if dominated else None,
    )


def _advice(
    *moves: AdvisedMove, unbanded: Sequence[UnbandedMove] = ()
) -> CaseAdvice:
    return CaseAdvice(
        case_id="urn:uuid:case-1",
        end_confirmed=False,
        vendors=(_VENDOR, _VENDOR_2),
        bands=tuple(BandAdvice.of(b, moves) for b in BAND_ORDER),
        unbanded=tuple(unbanded),
    )


def _state(
    rm: RM = RM.VALID,
    vf: CS_vf = CS_vf.Vf,
    pxa: CS_pxa = CS_pxa.pxa,
    register: dict[str, EmbargoRegisterStatus] | None = None,
) -> ReachedState:
    return ReachedState(
        participants=[
            ReachedParticipant(participant=_VENDOR, rm=rm, vf=vf, d=CS_d.d),
            ReachedParticipant(participant=_OWNER),
        ],
        pxa=pxa,
        embargo_register=register
        or {_EMBARGO: EmbargoRegisterStatus.PROPOSED},
    )


_BEFORE = _state()
_ACCEPTED = _state(rm=RM.ACCEPTED)
_FIXED = _state(vf=CS_vf.VF)
_PUBLIC = _state(pxa=CS_pxa.Pxa)


def _mark(
    after: ReachedState,
    advice: CaseAdvice | None,
    before: ReachedState = _BEFORE,
    actor: str | None = _VENDOR,
    *,
    ended_on_own_terms: bool = False,
) -> NarrativeMark:
    return hindsight_mark(
        7,
        before,
        after,
        lambda: advice,
        actor,
        ended_on_own_terms=ended_on_own_terms,
    )


#: A harm-free move in layer 1, so harm-free is the first band with moves.
_TOP_HARM_FREE = _advised(_FIX, [(1, 0), (0, 0)], layer=1, top=True)


def _no_advice_wanted(why: str) -> Callable[[], CaseAdvice]:
    """An advice reader that fails the test when it is read: *why* the
    entry should read no advice."""

    def read() -> CaseAdvice:
        raise AssertionError(why)

    return read
