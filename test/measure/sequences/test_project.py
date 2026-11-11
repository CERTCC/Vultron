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

"""Projecting per-vendor case-state sequences (CEH-05, CEH-06-002, CEH-06-006).

The hand-built ledgers hold the shapes no committed recording does: two
vendors with and without the Deployer role, a case with no public exploit, a
Deployer holding no Vendor role, and a vendor that becomes aware only after
the exploit is public.
"""

import ast
import itertools
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

import vultron.measure.sequences as sequences_package
from test.measure.history.builders import (
    CASE,
    CM,
    DEPLOYER,
    OWNER,
    REPORTER,
    VENDOR,
    VENDOR_2,
    Ledger,
    case_status,
    participant,
    status,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs.states import CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import (
    CS_EVENTS,
    CSEvent,
    is_valid_cs_history,
    is_valid_cs_history_prefix,
)
from vultron.core.states.participant_transitions import (
    participant_transition_violations,
)
from vultron.core.states.rm import RM
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.enums.roles import CVDRole
from vultron.measure.history import (
    CaseEvent,
    CaseEventHistory,
    EventScope,
    read_case_event_histories,
    scope_of,
)
from vultron.measure.ledger import LedgerSource
from vultron.measure.sequences import (
    CaseStateSequence,
    CaseStateSequences,
    Placement,
    UnprojectableParticipant,
    UnprojectableReason,
    case_state_sequences,
    model as sequences_model,
    project as sequences_project,
)

_RECORDINGS = sorted(RECORDINGS_DIR.glob("*/case-actor.jsonl"))


def _seat_vendor(
    ledger: Ledger, actor: str, vf: str, *, deployer: bool = False
) -> int:
    roles = ("VENDOR", "DEPLOYER") if deployer else ("VENDOR",)
    return ledger.seat(
        participant(
            actor,
            [
                status(
                    f"{actor}-r",
                    actor,
                    "RECEIVED",
                    vf=vf,
                    d="d" if deployer else None,
                    roles=roles,
                )
            ],
            roles=roles,
        )
    )


def _publish(ledger: Ledger, pxa: str) -> int:
    """The CASE_MANAGER adopts public state *pxa*."""
    return ledger.add(
        "add_case_status_to_case", "Add", CM, case_status(f"cs-{pxa}", pxa)
    )


def _two_vendor_ledger() -> Ledger:
    """A vendor that also deploys, then a second vendor holding no Deployer
    role, then the case goes public; no exploit is ever published."""
    ledger = Ledger()
    ledger.standard_genesis()
    ledger.add_status(OWNER, status("owner-v", OWNER, "VALID"))
    _seat_vendor(ledger, VENDOR, "vf", deployer=True)
    ledger.add_status(
        VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf", d="d")
    )
    _seat_vendor(ledger, VENDOR_2, "Vf")
    ledger.add_status(
        VENDOR, status("v-F", VENDOR, "RECEIVED", vf="VF", d="d")
    )
    ledger.add_status(
        VENDOR, status("v-D", VENDOR, "RECEIVED", vf="VF", d="D")
    )
    _publish(ledger, "Pxa")
    return ledger


def _vendorless_deployer_ledger() -> Ledger:
    ledger = _two_vendor_ledger()
    ledger.add_status(
        DEPLOYER,
        status("dep-r", DEPLOYER, "RECEIVED", d="d", roles=("DEPLOYER",)),
    )
    ledger.add_status(
        DEPLOYER,
        status("dep-d", DEPLOYER, "RECEIVED", d="D", roles=("DEPLOYER",)),
    )
    return ledger


def _projected(ledger: Ledger) -> tuple[CaseEventHistory, CaseStateSequences]:
    history = ledger.history()
    return history, case_state_sequences(history)


def _kinds(sequence: CaseStateSequence | None) -> str:
    assert sequence is not None
    return "".join(sequence.kinds)


def _unprojectable(
    projected: CaseStateSequences, actor: str
) -> UnprojectableParticipant:
    (found,) = [u for u in projected.unprojectable if u.participant == actor]
    return found


# ---------------------------------------------------------------------------
# One sequence per vendor, keyed on vendor awareness (CEH-05-001 to -003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-05-001")
def test_one_sequence_per_vendor_in_log_order():
    history, projected = _projected(_two_vendor_ledger())
    assert [s.participant for s in projected.sequences] == [VENDOR, VENDOR_2]
    for sequence in projected.sequences:
        indices = [e.log_index for e in sequence.events]
        assert indices == sorted(indices)
        assert all(m.event in history.events for m in sequence.events)
        assert sequence.placed == ()
    assert _kinds(projected.for_participant(VENDOR)) == "VFDP"
    assert _kinds(projected.for_participant(VENDOR_2)) == "VP"


@pytest.mark.spec("CEH-05-001")
def test_sequences_are_ordered_by_vendor_awareness_not_first_event():
    """The vendor seated first becomes aware second."""
    ledger = Ledger()
    ledger.standard_genesis()
    _seat_vendor(ledger, VENDOR, "vf")
    _seat_vendor(ledger, VENDOR_2, "Vf")
    ledger.add_status(VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf"))
    history, projected = _projected(ledger)
    first_events = [
        p for p in dict.fromkeys(e.participant for e in history.events) if p
    ]
    assert first_events.index(VENDOR) < first_events.index(VENDOR_2)
    assert [s.participant for s in projected.sequences] == [VENDOR_2, VENDOR]


@pytest.mark.spec("CEH-05-001")
@pytest.mark.spec("CEH-05-007")
@pytest.mark.spec("CEH-06-006")
def test_a_deployer_without_the_vendor_role_is_unprojectable_with_a_reason():
    history, projected = _projected(_vendorless_deployer_ledger())
    assert projected.for_participant(DEPLOYER) is None
    unprojectable = _unprojectable(projected, DEPLOYER)
    assert unprojectable.reason is UnprojectableReason.NO_VENDOR_AWARENESS
    assert "D at log index" in unprojectable.detail
    assert "CSB-15-004" in unprojectable.detail
    # Its fix-deployed event stays in the event history.
    assert [e.kind for e in history.for_participant(DEPLOYER)][-1] is CSEvent.D
    # The vendors' sequences are unaffected.
    assert [s.participant for s in projected.sequences] == [VENDOR, VENDOR_2]


@pytest.mark.spec("CEH-05-007")
def test_every_participant_with_no_sequence_is_reported_once():
    _, projected = _projected(_vendorless_deployer_ledger())
    reported = [u.participant for u in projected.unprojectable]
    assert reported == [CM, OWNER, REPORTER, DEPLOYER]
    for actor in (CM, OWNER, REPORTER):
        assert (
            _unprojectable(projected, actor).reason
            is UnprojectableReason.NO_CASE_STATE_EVENTS
        )


@pytest.mark.spec("CEH-05-002")
def test_a_sequence_holds_only_case_state_events():
    history, projected = _projected(_vendorless_deployer_ledger())
    assert any(not isinstance(e.kind, CSEvent) for e in history.events)
    for sequence in projected.sequences:
        assert sequence.events
        for event in sequence.events:
            assert event.kind in CS_EVENTS
        assert is_valid_cs_history_prefix(sequence.kinds)


@pytest.mark.spec("CEH-05-003")
def test_a_sequence_combines_the_vendors_own_events_with_the_cases():
    _, projected = _projected(_two_vendor_ledger())
    deploying = projected.for_participant(VENDOR)
    assert deploying is not None
    by_kind = {m.kind: m.event for m in deploying.events}
    assert by_kind[CSEvent.P].participant is None
    assert {
        by_kind[k].participant for k in (CSEvent.V, CSEvent.F, CSEvent.D)
    } == {VENDOR}
    # A vendor holding no Deployer role has no deployment event, and its
    # sequence is still a valid prefix.
    plain = projected.for_participant(VENDOR_2)
    assert plain is not None
    assert CSEvent.D not in plain.kinds
    assert CSEvent.P in plain.kinds
    assert is_valid_cs_history_prefix(plain.kinds)


# ---------------------------------------------------------------------------
# Every sequence is a valid prefix; only a trailing event may be missing
# (CEH-05-004, CEH-05-005)
# ---------------------------------------------------------------------------


def _late_vendor_ledger() -> Ledger:
    """The case goes public, then the exploit is published, then a vendor
    becomes aware.

    The CASE_MANAGER admits every entry: the public state moves forward in
    its own machine, and the vendor's first fix-path status has no earlier
    one to compare a compound against (ADR-0075).  As recorded, the compound
    ``P, X, V`` does not replay, because public awareness without vendor
    awareness obliges ``V`` next (CSB-17-003).
    """
    ledger = Ledger()
    ledger.standard_genesis()
    _publish(ledger, "Pxa")
    _publish(ledger, "PXa")
    _seat_vendor(ledger, VENDOR, "vf")
    ledger.add_status(VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf"))
    return ledger


def _placements(sequence: CaseStateSequence | None) -> list[Placement]:
    assert sequence is not None
    return [member.placement for member in sequence.events]


_R, _AT_X, _AT_P = (
    Placement.RECORDED,
    Placement.AT_EXPLOIT_PUBLICATION,
    Placement.AT_PUBLIC_AWARENESS,
)


@pytest.mark.spec("CEH-05-009")
@pytest.mark.spec("CEH-05-004")
def test_awareness_recorded_after_publication_is_placed_at_public_awareness():
    history, projected = _projected(_late_vendor_ledger())
    recorded = [e for e in history.events if isinstance(e.kind, CSEvent)]
    assert [e.kind for e in recorded] == [CSEvent.P, CSEvent.X, CSEvent.V]
    assert not is_valid_cs_history_prefix([e.kind for e in recorded])

    sequence = projected.for_participant(VENDOR)
    assert sequence is not None
    assert _kinds(sequence) == "PVX"
    assert is_valid_cs_history_prefix(sequence.kinds)
    assert _placements(sequence) == [_R, _AT_P, _R]
    # The placed event is the recorded one: same log index, same clocks.
    (placed,) = sequence.placed
    assert placed.event == recorded[2]
    assert placed.log_index > recorded[1].log_index
    # The history itself is unchanged.
    assert history.events[-1].kind is CSEvent.V
    assert VENDOR not in {u.participant for u in projected.unprojectable}


@pytest.mark.spec("CEH-05-009")
def test_awareness_right_after_publication_is_not_marked_placed():
    ledger = Ledger()
    ledger.standard_genesis()
    _publish(ledger, "Pxa")
    _seat_vendor(ledger, VENDOR, "vf")
    ledger.add_status(VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf"))
    _publish(ledger, "PXa")
    _, projected = _projected(ledger)
    sequence = projected.for_participant(VENDOR)
    assert _kinds(sequence) == "PVX"
    assert sequence is not None
    assert sequence.placed == ()


def _exploit_first_ledger() -> Ledger:
    """The exploit is published while the public is unaware, a vendor
    becomes aware, then the public becomes aware: recorded ``X, V, P``.

    Every entry is admitted on its own, but as recorded the compound breaks
    the other transient state: an exploit public while the public is unaware
    obliges ``P`` next (CSB-17-003).
    """
    ledger = Ledger()
    ledger.standard_genesis()
    _publish(ledger, "pXa")
    _seat_vendor(ledger, VENDOR, "vf")
    ledger.add_status(VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf"))
    _publish(ledger, "PXa")
    return ledger


@pytest.mark.spec("CEH-05-009")
def test_public_awareness_recorded_after_publication_is_placed_at_the_exploit():
    history, projected = _projected(_exploit_first_ledger())
    recorded = [e for e in history.events if isinstance(e.kind, CSEvent)]
    assert [e.kind for e in recorded] == [CSEvent.X, CSEvent.V, CSEvent.P]
    assert not is_valid_cs_history_prefix([e.kind for e in recorded])

    sequence = projected.for_participant(VENDOR)
    assert _kinds(sequence) == "XPV"
    assert sequence is not None
    assert is_valid_cs_history_prefix(sequence.kinds)
    # P moved; V now directly follows it, so V is in place and unmarked.
    assert _placements(sequence) == [_R, _AT_X, _R]
    (placed,) = sequence.placed
    assert placed.event == recorded[2]
    assert history.events[-1].kind is CSEvent.P


@pytest.mark.spec("CEH-05-009")
@pytest.mark.parametrize(
    ("steps", "expected", "placements"),
    [
        # X, A, P, V: both late; P goes after X, then V after P.
        (["pXa", "pXA", "PXA", "V"], "XPVA", [_R, _AT_X, _AT_P, _R]),
        # X, A, V, P: P goes after X, leaving A between P and V.
        (["pXa", "pXA", "V", "PXA"], "XPVA", [_R, _AT_X, _AT_P, _R]),
    ],
    ids=["XAPV", "XAVP"],
)
def test_both_placements_compose(steps, expected, placements):
    ledger = Ledger()
    ledger.standard_genesis()
    _seat_vendor(ledger, VENDOR, "vf")
    for step in steps:
        if step == "V":
            ledger.add_status(
                VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf")
            )
        else:
            _publish(ledger, step)
    _, projected = _projected(ledger)
    sequence = projected.for_participant(VENDOR)
    assert _kinds(sequence) == expected
    assert _placements(sequence) == placements
    assert sequence is not None
    assert is_valid_cs_history_prefix(sequence.kinds)


def _deployed_before_ready_ledger() -> Ledger:
    """A vendor that also deploys is seated aware with the fix deployed but
    not ready, then reports the fix ready: recorded ``V, D, F``.

    The CASE_MANAGER would refuse the seat (a deployed fix entails a ready
    one, CSB-17-001), but the layer reads archived and foreign ledgers it
    never validated, and the derivation passes the entry through.
    """
    ledger = Ledger()
    ledger.standard_genesis()
    roles = ("VENDOR", "DEPLOYER")
    ledger.seat(
        participant(
            VENDOR,
            [status("v-r", VENDOR, "RECEIVED", vf="Vf", d="D", roles=roles)],
            roles=roles,
        )
    )
    ledger.add_status(
        VENDOR, status("v-F", VENDOR, "RECEIVED", vf="VF", d="D")
    )
    return ledger


@pytest.mark.spec("CEH-05-004")
@pytest.mark.spec("CEH-05-007")
def test_a_compound_that_does_not_replay_is_refused_with_its_reason():
    violations = participant_transition_violations(
        current_rm=RM.START,
        current_vf=None,
        current_d=None,
        current_pxa=CS_pxa.pxa,
        requested_rm=RM.ACCEPTED,
        requested_vf=CS_vf.Vf,
        requested_d=CS_d.D,
        actor_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        validate_rm_transition=False,
    )
    assert any("CSB-17-001" in v.message for v in violations)

    history, projected = _projected(_deployed_before_ready_ledger())
    recorded = [e.kind for e in history.events if isinstance(e.kind, CSEvent)]
    assert recorded == [CSEvent.V, CSEvent.D, CSEvent.F]
    assert projected.sequences == []
    refused = _unprojectable(projected, VENDOR)
    assert refused.reason is UnprojectableReason.NOT_A_VALID_PREFIX
    assert refused.detail.startswith(
        "VDF is not a valid case-state history prefix"
    )


def _attacks_before_public_awareness_ledger() -> Ledger:
    """A vendor becomes aware, the exploit is published, and attacks are
    observed while the public is still unaware: recorded ``V, X, A``.

    Each case status is a forward move in the public-state machine on its
    own, but ``pX`` obliges ``P`` next (CSB-17-003) and no ``P`` is recorded,
    so there is nothing to place.
    """
    ledger = Ledger()
    ledger.standard_genesis()
    _seat_vendor(ledger, VENDOR, "Vf")
    _publish(ledger, "pXa")
    _publish(ledger, "pXA")
    return ledger


@pytest.mark.spec("CEH-05-004")
@pytest.mark.spec("CEH-05-007")
def test_an_exploit_with_no_public_awareness_and_a_later_event_is_refused():
    history, projected = _projected(_attacks_before_public_awareness_ledger())
    recorded = [e.kind for e in history.events if isinstance(e.kind, CSEvent)]
    assert recorded == [CSEvent.V, CSEvent.X, CSEvent.A]
    assert projected.sequences == []
    refused = _unprojectable(projected, VENDOR)
    assert refused.reason is UnprojectableReason.NOT_A_VALID_PREFIX
    assert refused.detail.startswith(
        "VXA is not a valid case-state history prefix"
    )
    assert "requires event(s) ['P'] next" in refused.detail


def _recordable_orders() -> list[tuple[CSEvent, ...]]:
    """Every order one vendor's and the case's events can be recorded in.

    The vendor's own events keep ``V, F, D`` order, which the derivation's
    forward-only reading and CSB-17-001 guarantee; the case's public-state
    events are each a forward move in their own machine, so any order of any
    subset.  It is a superset of what a CASE_MANAGER admits.
    """
    orders: set[tuple[CSEvent, ...]] = set()
    vendor_chains = [(CSEvent.V,), (CSEvent.V, CSEvent.F), tuple("VFD")]
    public = (CSEvent.P, CSEvent.X, CSEvent.A)
    for chain in vendor_chains:
        for size in range(len(public) + 1):
            for case in itertools.permutations(public, size):
                total = len(chain) + len(case)
                for slots in itertools.combinations(range(total), len(chain)):
                    order: list[CSEvent] = []
                    own, shared = iter(chain), iter(case)
                    for i in range(total):
                        order.append(
                            CSEvent(next(own) if i in slots else next(shared))
                        )
                    orders.add(tuple(order))
    return sorted(orders)


def _history_of(order: tuple[CSEvent, ...]) -> CaseEventHistory:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        CaseEvent(
            kind=kind,
            participant=None if scope_of(kind) is EventScope.CASE else VENDOR,
            semantic_type=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
            log_index=index,
            committed_at=at,
        )
        for index, kind in enumerate(order)
    ]
    return CaseEventHistory(
        case_id=CASE,
        source=LedgerSource.COMPLETE_COPY,
        end_confirmed=False,
        events=events,
    )


def _exploit_without_public_awareness(order: tuple[CSEvent, ...]) -> bool:
    """Whether *order* records ``X``, never ``P``, and something after ``X``.

    No recorded ``P`` exists to place, and ``pX`` obliges ``P`` next
    (CSB-17-003), so nothing the layer may move makes it replay.
    """
    return (
        CSEvent.X in order
        and CSEvent.P not in order
        and order[-1] is not CSEvent.X
    )


@pytest.mark.spec("CEH-05-009")
@pytest.mark.spec("CEH-05-004")
@pytest.mark.spec("CEH-05-007")
def test_every_recorded_order_projects_unless_an_exploit_has_no_public_awareness():
    """Over every order one vendor's and the case's events can be recorded
    in, the two placements leave exactly one shape unprojectable: an exploit
    published with no public awareness recorded and some event after it."""
    orders = _recordable_orders()
    assert len(orders) > 100
    unreplayable = [o for o in orders if not is_valid_cs_history_prefix(o)]
    assert unreplayable, "the placements must have work to do"
    refused = 0
    for order in orders:
        projected = case_state_sequences(_history_of(order))
        if _exploit_without_public_awareness(order):
            refused += 1
            assert projected.sequences == [], "".join(order)
            (unprojectable,) = projected.unprojectable
            assert (
                unprojectable.reason is UnprojectableReason.NOT_A_VALID_PREFIX
            )
            assert "requires event(s) ['P'] next" in unprojectable.detail
            continue
        assert projected.unprojectable == [], "".join(order)
        (sequence,) = projected.sequences
        assert is_valid_cs_history_prefix(sequence.kinds)
        assert sorted(sequence.kinds) == sorted(order)
    assert refused


@pytest.mark.spec("CEH-05-005")
def test_a_sequence_missing_trailing_events_is_an_incomplete_prefix():
    _, projected = _projected(_two_vendor_ledger())
    for sequence in projected.sequences:
        assert CSEvent.X not in sequence.kinds
        assert not is_valid_cs_history(sequence.kinds)
        assert is_valid_cs_history_prefix(sequence.kinds)


# ---------------------------------------------------------------------------
# No case-wide sequence and no score (CEH-05-006, CEH-05-008)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-05-006")
def test_two_vendors_expose_two_sequences_and_no_case_wide_one():
    _, projected = _projected(_two_vendor_ledger())
    assert len(projected.sequences) == 2
    assert set(CaseStateSequences.model_fields) == {
        "case_id",
        "sequences",
        "unprojectable",
    }
    for sequence in projected.sequences:
        own = {m.event.participant for m in sequence.events} - {None}
        assert own == {sequence.participant}


def _imported_modules(module) -> set[str]:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


@pytest.mark.spec("CEH-05-008")
@pytest.mark.parametrize(
    "module",
    [sequences_package, sequences_model, sequences_project],
    ids=lambda m: m.__name__,
)
def test_the_layer_imports_no_scoring_entry_point(module):
    imported = _imported_modules(module)
    for scoring in ("vultron.core.case_states", "vultron.measure.baselines"):
        assert not any(
            name == scoring or name.startswith(f"{scoring}.")
            for name in imported
        ), scoring
    assert not any("score" in name.lower() for name in imported)


#: The scoring entry points: the legacy desiderata scorer
#: (``CVDmodel.score_hist``) and the chance baselines #6068 scores through.
_SCORING_PACKAGES = (
    "vultron.core.case_states.hypercube",
    "vultron.measure.baselines",
)


@pytest.mark.spec("CEH-05-008")
def test_importing_the_layer_loads_no_scoring_entry_point():
    """Indirect imports count too, so ask a fresh interpreter."""
    probe = (
        "import sys, vultron.measure.sequences\n"
        f"print([m for m in sys.modules if m.startswith({_SCORING_PACKAGES!r})])"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert loaded == "[]"


@pytest.mark.spec("CEH-05-008")
@pytest.mark.parametrize(
    "model",
    [CaseStateSequence, CaseStateSequences, UnprojectableParticipant],
)
def test_no_projected_model_exposes_a_score(model):
    public = {name for name in dir(model) if not name.startswith("_")}
    assert not any("score" in name.lower() for name in public)
    assert not any("score" in name.lower() for name in model.model_fields)


# ---------------------------------------------------------------------------
# Every committed recording projects valid prefixes (CEH-06-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-06-002")
@pytest.mark.spec("CEH-05-004")
@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.parent.name)
def test_every_sequence_from_a_recording_is_a_valid_prefix(path):
    (history,) = read_case_event_histories([path]).histories.values()
    projected = case_state_sequences(history)
    aware = {e.participant for e in history.of_kind(CSEvent.V)}
    assert {s.participant for s in projected.sequences} == aware
    for sequence in projected.sequences:
        assert is_valid_cs_history_prefix(sequence.kinds)
        assert sequence.kinds[0] is CSEvent.V
    assert all(
        u.reason is UnprojectableReason.NO_CASE_STATE_EVENTS
        for u in projected.unprojectable
    )


def test_the_corpus_is_not_empty():
    assert len(_RECORDINGS) >= 2
