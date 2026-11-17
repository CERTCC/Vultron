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

"""The advice record over real case ledgers (ADR-0200, #6369)."""

import copy
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from test.measure.history.builders import (
    EMBARGO_2,
    OWNER,
    REPORTER,
    VENDOR,
    VENDOR_2,
    Ledger,
    embargo,
    participant,
    publish,
    seat_unnotified_vendor,
    seat_vendor,
    status,
)
from vultron.core.states.em import EM, EM_Trigger
from vultron.measure.advice import (
    BAND_ORDER,
    CHANCE_EVENT,
    DOMINATED_BY_HARM_FREE,
    HARM_NOTE,
    HELP_TEXT,
    KEEPS_EVERY_STATE,
    AdvisedMove,
    Band,
    BandAdvice,
    CaseAdvice,
    ColourMap,
    Part,
    ScopeParts,
    ScopeShift,
    VendorHarm,
    VendorShift,
    case_advice,
    dominates,
)
from vultron.measure.ledger import read_case_ledgers
from vultron.measure.standing import EMMove, StandingGap, case_standing

#: matplotlib's perceptually uniform sequential maps; ``cividis`` is also
#: tuned for colour-vision deficiency, and ``viridis`` reads under the
#: common ones.
_UNIFORM_COLOUR_BLIND_SAFE = {"viridis", "cividis"}


def _one_vendor() -> Ledger:
    """The standard genesis, and a vendor aware at RM Received."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    return ledger


def _two_vendors() -> Ledger:
    """No embargo; a vendor with its fix ready and the report accepted, and
    a second vendor aware at RM Received with no fix."""
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                OWNER,
                [status("owner-r", OWNER, "RECEIVED")],
                roles=("CASE_OWNER",),
            )
        ],
        with_embargo=False,
    )
    seat_vendor(ledger, VENDOR, "VF")
    ledger.add_status(VENDOR, status("vendor-a", VENDOR, "ACCEPTED", vf="VF"))
    seat_vendor(ledger, VENDOR_2, "Vf")
    return ledger


@pytest.fixture(scope="module")
def two_vendors() -> CaseAdvice:
    return case_advice(case_standing(_two_vendors().case_ledger()))


def _move(advice: CaseAdvice, participant: str, name: str) -> AdvisedMove:
    (move,) = [
        m
        for m in advice.moves
        if m.move.participant == participant and m.move.name == name
    ]
    return move


def _parts(move: AdvisedMove, vendor: str) -> VendorShift:
    (parts,) = [s for s in move.shift if s.vendor == vendor]
    return parts


@pytest.mark.spec("SHD-03-001")
def test_one_end_part_matches_a_hand_sum():
    """Publication from Vfdpxa: the vendor's end part, by hand.

    Each term is the change in one end desideratum's expected outcome times
    its weight ``1 − f_d`` (ADR-0200).  ``F ≺ P`` falls from 1/3 to
    0 (``test/measure/standing/test_advice.py``); the weights are one minus
    each desideratum's chance frequency on the Measuring CVD pages.  Every
    other end desideratum of the scope keeps its expected outcome.
    """
    terms = [
        (Fraction(-1, 9), Fraction(26, 27)),  # D ≺ P
        (Fraction(-1, 3), Fraction(8, 9)),  # F ≺ P
        (Fraction(1, 2), Fraction(1, 2)),  # P ≺ X
        (Fraction(1, 3), Fraction(1, 3)),  # P ≺ A
        (Fraction(-5, 64), Fraction(91, 96)),  # Ac_i ≺ P
        (Fraction(-1, 4), Fraction(5, 6)),  # Va_i ≺ P
    ]
    advice = case_advice(case_standing(_one_vendor().case_ledger()))
    publication = _move(advice, VENDOR, "cs.public_becomes_aware")
    assert advice.vendors == (VENDOR,)
    assert _parts(publication, VENDOR).end == sum(c * w for c, w in terms)


def test_every_open_move_has_a_shift_for_each_vendor(two_vendors):
    assert two_vendors.vendors == (VENDOR, VENDOR_2)
    assert two_vendors.moves
    for move in two_vendors.moves:
        assert [s.vendor for s in move.shift] == [VENDOR, VENDOR_2]


def test_the_case_has_a_move_in_each_band(two_vendors):
    """Each band is set by the move's own shift (ADR-0200)."""
    fix = _move(two_vendors, VENDOR, "cs.fix_is_deployed")
    publication = _move(two_vendors, VENDOR, "cs.public_becomes_aware")
    validation = _move(two_vendors, VENDOR_2, "rm.validate")
    assert fix.band is Band.HARM_FREE
    assert fix.shift[0].end > 0 and fix.shift[1] == VendorShift(
        vendor=VENDOR_2, end=Fraction(0), embargo=Fraction(0)
    )
    assert publication.band is Band.TRADE_OFF
    assert publication.shift[0].end > 0 > publication.shift[1].end
    assert validation.band is Band.UNHELPFUL
    assert validation.shift[1].end < 0
    for band in BAND_ORDER:
        assert two_vendors.band(band).moves


def _scope_shift(move: AdvisedMove) -> ScopeShift:
    return tuple(ScopeParts(s.end, s.embargo) for s in move.shift)


def test_layers_follow_dominance(two_vendors):
    """The fix dominates the owner's proposal; the proposal and publication
    trade off; the fix dominates publication, a trade-off move that is then
    not top (ADR-0200)."""
    fix = _move(two_vendors, VENDOR, "cs.fix_is_deployed")
    proposal = _move(two_vendors, OWNER, "em.propose")
    publication = _move(two_vendors, VENDOR, "cs.public_becomes_aware")
    assert (fix.layer, fix.top) == (1, True)
    assert dominates(_scope_shift(fix), _scope_shift(proposal))
    assert proposal.band is Band.HARM_FREE
    assert (proposal.layer, proposal.top) == (2, False)
    assert not dominates(_scope_shift(proposal), _scope_shift(publication))
    assert not dominates(_scope_shift(publication), _scope_shift(proposal))
    assert dominates(_scope_shift(fix), _scope_shift(publication))
    assert publication.band is Band.TRADE_OFF
    assert (publication.layer, publication.top) == (2, False)
    for move in two_vendors.band(Band.UNHELPFUL).moves:
        assert (move.layer, move.top) == (None, False)


def test_closing_a_report_gains_nothing_from_the_scopes_it_closes():
    """Closing from RM Received takes the acceptance-scoped desiderata out
    of reach, so they add no shift; what is left is ``Ac_i ≺ F_i`` breaking,
    a harm, so the closure is unhelpful, not top."""
    record = case_standing(_one_vendor().case_ledger())
    (scored,) = [
        m
        for m in record.moves
        if m.move.participant == VENDOR and m.move.name == "rm.close"
    ]
    assert scored.changes is not None
    changes = {c.notation: c.change for c in scored.changes}
    for notation in (
        r"$\evAc_i \prec \evP$",
        r"$\evAc_i \prec \evX$",
        r"$\evAc_i \prec \evA$",
    ):
        assert changes[notation] == 0
    close = _move(case_advice(record), VENDOR, "rm.close")
    assert close.band is Band.UNHELPFUL and not close.top
    assert _parts(close, VENDOR).end < 0


def test_a_trade_off_move_a_harm_free_move_dominates_says_so(two_vendors):
    publication = _move(two_vendors, VENDOR, "cs.public_becomes_aware")
    assert publication.dominated_by_harm_free == DOMINATED_BY_HARM_FREE
    assert DOMINATED_BY_HARM_FREE == (
        "A harm-free move does at least as well on every vendor's end"
        " desiderata."
    )
    for move in two_vendors.moves:
        if move is not publication and move.band is not Band.TRADE_OFF:
            assert move.dominated_by_harm_free is None


def test_an_undominated_trade_off_move_says_nothing_of_harm_free_moves():
    """Under an embargo, with the first vendor's fix ready but the report
    not yet accepted, publication trades off and no harm-free move
    dominates it."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "VF")
    seat_vendor(ledger, VENDOR_2, "Vf")
    advice = case_advice(case_standing(ledger.case_ledger()))
    (publication,) = [
        m
        for m in advice.band(Band.TRADE_OFF).moves
        if m.move.name == "cs.public_becomes_aware"
    ]
    assert publication.top
    assert publication.dominated_by_harm_free is None


def test_the_coordinators_undominated_move_is_leading_among_yours(
    two_vendors,
):
    """The owner's proposal is not top, since the fix dominates it, but no
    other move of the coordinator's does (ADR-0200)."""
    proposal = _move(two_vendors, OWNER, "em.propose")
    assert proposal.leading_among_yours and not proposal.top
    leading = [m for m in two_vendors.moves if m.leading_among_yours]
    assert leading == [proposal]


def test_each_negative_part_is_a_harm_by_vendor_with_its_size(two_vendors):
    publication = _move(two_vendors, VENDOR, "cs.public_becomes_aware")
    expected = []
    for parts in publication.shift:
        if parts.end < 0:
            expected.append((parts.vendor, Part.END, parts.end))
        if parts.embargo < 0:
            expected.append((parts.vendor, Part.EMBARGO, parts.embargo))
    assert [(h.vendor, h.part, h.size) for h in publication.harms] == expected
    assert (VENDOR_2, Part.END) in [(v, part) for v, part, _ in expected]
    assert two_vendors.harm_note == HARM_NOTE
    assert "worse than the chance value" in HARM_NOTE
    assert "not a broken desideratum" in HARM_NOTE


def test_the_record_says_how_to_show_each_band(two_vendors):
    assert [b.band for b in two_vendors.bands] == list(BAND_ORDER)
    harm_free, trade_off, unhelpful = two_vendors.bands
    assert {harm_free.colour_map, trade_off.colour_map} <= set(ColourMap)
    assert harm_free.colour_map != trade_off.colour_map
    assert {m.value for m in ColourMap} <= _UNIFORM_COLOUR_BLIND_SAFE
    assert not harm_free.collapsed and not trade_off.collapsed
    assert unhelpful.collapsed and unhelpful.colour_map is None
    assert two_vendors.help_text == HELP_TEXT
    assert HELP_TEXT == (
        "Choose the darkest move in the highest band that has one."
    )


def test_the_record_dumps_to_json_for_the_page(two_vendors):
    dumped = json.loads(two_vendors.model_dump_json())
    assert dumped["help_text"] == HELP_TEXT
    assert dumped["harm_note"] == HARM_NOTE
    assert [b["band"] for b in dumped["bands"]] == [
        b.value for b in BAND_ORDER
    ]


def test_moves_that_are_not_steps_are_listed_with_why(two_vendors):
    reasons = {
        (u.move.participant, u.move.name): u for u in two_vendors.unbanded
    }
    attacks = reasons[(VENDOR_2, "cs.attacks_are_observed")]
    assert attacks.reason == CHANCE_EVENT
    owner = reasons[(OWNER, "rm.validate")]
    assert "moves no vendor's state" in owner.reason
    banded = {(m.move.participant, m.move.name) for m in two_vendors.moves}
    assert not banded & set(reasons)


def test_a_move_that_keeps_every_state_has_no_band():
    """A second proposal while one is open keeps EM at PROPOSED."""
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                OWNER,
                [status("owner-r", OWNER, "RECEIVED")],
                roles=("CASE_OWNER",),
            )
        ],
        with_embargo=False,
    )
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add(
        "invite_to_embargo_on_case", "Invite", REPORTER, embargo(EMBARGO_2)
    )
    record = case_standing(ledger.case_ledger())
    advice = case_advice(record)
    kept = [
        u
        for u in advice.unbanded
        if isinstance(u.move, EMMove)
        and u.move.source is u.move.destination is EM.PROPOSED
    ]
    assert kept and all(u.reason == KEEPS_EVERY_STATE for u in kept)
    assert not [
        m
        for m in advice.moves
        if isinstance(m.move, EMMove)
        and m.move.trigger is EM_Trigger.PROPOSE
        and m.move.source is EM.PROPOSED
    ]


def test_a_case_with_no_vendor_bands_nothing():
    ledger = Ledger()
    ledger.standard_genesis()
    advice = case_advice(case_standing(ledger.case_ledger()))
    assert advice.vendors == ()
    assert [b.band for b in advice.bands] == list(BAND_ORDER)
    assert advice.moves == ()
    assert advice.unbanded


def test_a_ledger_with_a_gap_yields_only_the_gap(tmp_path):
    ledger = _one_vendor()
    publish(ledger, "Pxa")
    rows = ledger.entries[:1] + ledger.entries[2:]
    path: Path = tmp_path / "holed.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    (holed,) = read_case_ledgers([path]).cases.values()
    advice = case_advice(case_standing(holed))
    assert advice.gap is not None
    assert (advice.bands, advice.unbanded, advice.vendors) == ((), (), ())
    with pytest.raises(KeyError, match="holds no harm-free band"):
        advice.band(Band.HARM_FREE)


def test_the_advice_writes_no_move_to_the_ledger():
    """AC-8: weighing every move leaves the ledger as it was.  That nothing
    under ``vultron/measure/`` writes to a store is CEH-01-002's test."""
    ledger = _one_vendor()
    before = copy.deepcopy(ledger.entries)
    case_ledger = ledger.case_ledger()
    dumped = case_ledger.model_dump()
    advice = case_advice(case_standing(case_ledger))
    assert advice.moves
    assert ledger.entries == before
    assert case_ledger.model_dump() == dumped


def _fields(model: BaseModel) -> dict[str, Any]:
    """*model*'s fields as objects, to build a changed copy that validates."""
    return {name: getattr(model, name) for name in type(model).model_fields}


def _publication(two_vendors: CaseAdvice) -> AdvisedMove:
    return _move(two_vendors, VENDOR, "cs.public_becomes_aware")


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"layer": None}, "has a layer of 1 up"),
        ({"layer": 0}, "has a layer of 1 up"),
        ({"band": Band.UNHELPFUL}, "an unhelpful move has no layer"),
        ({"top": True}, "a top move is a shaded move in layer 1"),
        (
            {
                "band": Band.UNHELPFUL,
                "layer": None,
                "leading_among_yours": True,
            },
            "never leading among yours",
        ),
        (
            {"band": Band.HARM_FREE},
            "only a trade-off move that is not top",
        ),
        (
            {"layer": 1, "top": True},
            "only a trade-off move that is not top",
        ),
        (
            {"band": Band.HARM_FREE, "dominated_by_harm_free": None},
            "its shift puts it in the trade-off band",
        ),
        ({"harms": ()}, "its harms are not its shift's negative parts"),
    ],
    ids=[
        "no layer",
        "layer 0",
        "unhelpful with a layer",
        "top outside layer 1",
        "unhelpful and leading",
        "message on a harm-free move",
        "message on a top move",
        "band its shift does not set",
        "harms its shift does not hold",
    ],
)
def test_an_advised_move_refuses_marks_its_band_cannot_hold(
    two_vendors, update, message
):
    with pytest.raises(ValidationError, match=message):
        AdvisedMove(**(_fields(_publication(two_vendors)) | update))


def test_a_harm_is_a_negative_part():
    with pytest.raises(ValidationError, match="a harm is a negative part"):
        VendorHarm(vendor=VENDOR, part=Part.END, size=Fraction(0))


def test_a_band_refuses_another_bands_move(two_vendors):
    with pytest.raises(ValidationError, match="is a trade-off move"):
        BandAdvice(
            band=Band.HARM_FREE,
            colour_map=ColourMap.VIRIDIS,
            collapsed=False,
            moves=(_publication(two_vendors),),
        )
    with pytest.raises(ValidationError, match="has no colour map"):
        BandAdvice(
            band=Band.UNHELPFUL, colour_map=ColourMap.VIRIDIS, collapsed=True
        )
    with pytest.raises(ValidationError, match="unhelpful band is collapsed"):
        BandAdvice(band=Band.UNHELPFUL, colour_map=None, collapsed=False)


def test_case_advice_refuses_bands_out_of_order_or_a_reading_with_a_gap(
    two_vendors,
):
    fields = _fields(two_vendors)
    with pytest.raises(ValidationError, match="in order"):
        CaseAdvice.model_validate(
            fields | {"bands": tuple(reversed(fields["bands"]))}
        )
    with pytest.raises(ValidationError, match="another set of vendors"):
        CaseAdvice.model_validate(fields | {"vendors": (VENDOR,)})
    with pytest.raises(ValidationError, match="listed more than once"):
        CaseAdvice.model_validate(fields | {"vendors": (VENDOR, VENDOR)})
    gap = StandingGap(missing_log_indices=[1])
    with pytest.raises(ValidationError, match="holds no reading"):
        CaseAdvice.model_validate(fields | {"gap": gap})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"notation": "not a desideratum"}, "no desideratum prints as"),
        ({"vendor": OWNER}, "is not a vendor of the case"),
        ({"other_vendor": OWNER}, "is not a vendor of the case"),
    ],
)
def test_a_change_the_case_cannot_hold_is_refused(change, message):
    record = case_standing(_one_vendor().case_ledger())
    scored = next(m for m in record.moves if m.changes)
    assert scored.changes is not None
    bad = scored.changes[0].model_copy(update=change)
    broken = scored.model_copy(update={"changes": (bad,)})
    with pytest.raises(ValueError, match=message):
        case_advice(record.model_copy(update={"moves": [broken]}))


@pytest.mark.spec("SHD-03-001")
def test_a_vendor_not_yet_notified_is_a_scope_and_its_notice_helps():
    """A notice raises only the notified vendor's end part, so it is never
    unhelpful (ADR-0200, P1 of #6450)."""
    ledger = _one_vendor()
    seat_unnotified_vendor(ledger, VENDOR_2)
    advice = case_advice(case_standing(ledger.case_ledger()))
    assert advice.vendors == (VENDOR, VENDOR_2)
    for move in advice.moves:
        assert [s.vendor for s in move.shift] == [VENDOR, VENDOR_2]
    notice = _move(advice, VENDOR_2, "rm.receive")
    assert notice.band is Band.HARM_FREE
    assert _parts(notice, VENDOR_2).end > 0
    assert _parts(notice, VENDOR) == VendorShift(
        vendor=VENDOR, end=Fraction(0), embargo=Fraction(0)
    )


def test_a_case_manager_is_a_coordinator_and_its_moves_pool_with_the_owners():
    """The vendor is also the case's CASE_MANAGER.  Its deployed fix
    dominates the owner's proposal, so the proposal is not leading among
    yours, and the fix is (ADR-0200)."""
    ledger = Ledger()
    ledger.genesis(
        [
            participant(
                OWNER,
                [status("owner-r", OWNER, "RECEIVED")],
                roles=("CASE_OWNER",),
            )
        ],
        with_embargo=False,
    )
    ledger.seat(
        participant(
            VENDOR,
            [status("vendor-r", VENDOR, "RECEIVED", vf="VF")],
            roles=("VENDOR", "CASE_MANAGER"),
        )
    )
    ledger.add_status(VENDOR, status("vendor-a", VENDOR, "ACCEPTED", vf="VF"))
    seat_vendor(ledger, VENDOR_2, "Vf")
    advice = case_advice(case_standing(ledger.case_ledger()))
    fix = _move(advice, VENDOR, "cs.fix_is_deployed")
    proposal = _move(advice, OWNER, "em.propose")
    assert proposal.band is Band.HARM_FREE
    assert fix.leading_among_yours
    assert not proposal.leading_among_yours


def test_two_desiderata_that_print_alike_are_refused(monkeypatch):
    from vultron.measure.advice import case as module

    module._desiderata_by_notation.cache_clear()
    monkeypatch.setattr(module, "EXTENDED", (module.ORIGINAL[0],))
    try:
        with pytest.raises(ValueError, match="two desiderata print as"):
            module._desiderata_by_notation()
    finally:
        module._desiderata_by_notation.cache_clear()
