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
import subprocess
import sys
from pathlib import Path

import pytest

import vultron.measure.sequences as sequences_package
from test.measure.history.builders import (
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
from vultron.core.states.cs_invariants import (
    CS_EVENTS,
    CSEvent,
    is_valid_cs_history,
    is_valid_cs_history_prefix,
)
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.history import CaseEventHistory, read_case_event_histories
from vultron.measure.sequences import (
    CaseStateSequence,
    CaseStateSequences,
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
        assert not sequence.awareness_placed_at_public_awareness
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
    assert sequence.awareness_placed_at_public_awareness
    assert [m.placed_at_public_awareness for m in sequence.events] == [
        False,
        True,
        False,
    ]
    # The placed event is the recorded one: same log index, same clocks.
    placed = sequence.events[1].event
    assert placed == recorded[2]
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
    assert not sequence.awareness_placed_at_public_awareness


def _exploit_first_ledger() -> Ledger:
    """The exploit is published while the public is unaware, a vendor
    becomes aware, then the public becomes aware.

    Every entry is admitted on its own, but ``X, V, P`` breaks the other
    transient state: an exploit public while the public is unaware obliges
    ``P`` next (CSB-17-003).  Placing awareness at public awareness does not
    reach it, because ``V`` is recorded before ``P``.
    """
    ledger = Ledger()
    ledger.standard_genesis()
    _publish(ledger, "pXa")
    _seat_vendor(ledger, VENDOR, "vf")
    ledger.add_status(VENDOR, status("v-V", VENDOR, "RECEIVED", vf="Vf"))
    _publish(ledger, "PXa")
    return ledger


@pytest.mark.spec("CEH-05-004")
@pytest.mark.spec("CEH-05-007")
def test_a_compound_that_does_not_replay_is_refused_with_its_reason():
    history, projected = _projected(_exploit_first_ledger())
    recorded = [e.kind for e in history.events if isinstance(e.kind, CSEvent)]
    assert recorded == [CSEvent.X, CSEvent.V, CSEvent.P]
    assert projected.sequences == []
    refused = _unprojectable(projected, VENDOR)
    assert refused.reason is UnprojectableReason.NOT_A_VALID_PREFIX
    assert refused.detail.startswith(
        "XVP is not a valid case-state history prefix"
    )
    assert "requires event(s) ['P'] next" in refused.detail


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
