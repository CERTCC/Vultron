"""The case's standing as badges, rows and lines (#6366): the public
state's badges, a row per participant, and a gap as lines.

Spec: CRD-02-005, DRPT-03-009.
"""

import pytest

from test.adapters.connectors.vince._support import ACTIVE, translate
from test.shadow.dashboard._support import recording_analysis
from test.shadow.dashboard.view._support import NAMES, VENDOR
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    derive_em,
)
from vultron.core.states.rm import RM
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.baselines import scope_desiderata
from vultron.measure.history import UnreadableEntry
from vultron.measure.ledger import UNNAMED_ACTOR, UnusableRow
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
)
from vultron.measure.standing import (
    CaseStanding,
    ParticipantStanding,
    StandingGap,
)
from vultron.shadow.analysis import analyse
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.case_state import VFD_BADGES


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_public_event_reads_as_unknown_never_as_false():
    assert view.public_badges(CS_pxa.pxa, {CSEvent.A}) == (
        "🤫 Not public",
        "🛡️ No public exploit",
        "❔ Attacks Observed unknown",
    )


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_public_event_the_reading_says_happened_stays_happened():
    assert view.public_badges(CS_pxa.PXa, {CSEvent.P}) == (
        "📢 Public aware",
        "💥 Exploit public",
        "🛡️ No attacks observed",
    )


def test_the_public_state_reads_as_three_badges():
    assert view.public_badges(CS_pxa.pxa) == (
        "🤫 Not public",
        "🛡️ No public exploit",
        "🛡️ No attacks observed",
    )
    assert view.public_badges(CS_pxa.PXA) == (
        "📢 Public aware",
        "💥 Exploit public",
        "🎯 Attacks observed",
    )


def test_participant_rows_show_report_state_fix_path_and_tally():
    analysis = recording_analysis()
    assert analysis.standing is not None
    rows = view.participant_rows(
        analysis.standing.participants, analysis.actor_names
    )
    vendor = next(r for r in rows if r["Participant"] == "Vendor")
    assert vendor["Report"] == view.RM_BADGES[RM.CLOSED]
    assert vendor["Fix path"] == VFD_BADGES[(CS_vf.VF, CS_d.d)]
    assert str(vendor["Desiderata"]).startswith("✅ ")
    assert vendor["Not scored because"] == ""
    manager = next(r for r in rows if "CASE_MANAGER" in str(r["Roles"]))
    assert manager["Fix path"] == "—"
    assert manager["Not scored because"]


def test_an_invitee_with_no_roles_reads_as_invited_with_none():
    invitee = ParticipantStanding(
        participant=VENDOR,
        joined=False,
        rm=RM.START,
        case=CaseStanding(em=EM.NONE, pxa=CS_pxa.pxa),
        unscored=UnprojectableParticipant(
            participant=VENDOR,
            reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
            detail="it has no event of its own",
        ),
    )
    (row,) = view.participant_rows([invitee], NAMES)
    assert row["Participant"] == "Vendor"
    assert row["Roles"] == "—"
    assert row["Joined"] == "✉️ invited"
    assert row["Report"] == view.RM_BADGES[RM.START]
    assert row["Not scored because"] == "it has no event of its own"


def test_a_tally_with_no_unknown_desideratum_shows_no_unknown_count():
    analysis = recording_analysis()
    assert analysis.standing is not None
    rows = view.participant_rows(
        analysis.standing.participants, analysis.actor_names
    )
    assert rows
    for row in rows:
        assert "❔" not in str(row["Desiderata"])
        assert "▫️" not in str(row["Desiderata"])


def _register_problem() -> str:
    """The words :func:`derive_em` gives a register with two active entries."""
    with pytest.raises(VultronInvalidStateTransitionError) as raised:
        derive_em([EmbargoRegisterStatus.ACTIVE, EmbargoRegisterStatus.ACTIVE])
    return str(raised.value)


def test_every_kind_of_hole_reads_as_a_line(tmp_path):
    """The register problem reads once, in derive_em's own words, never
    behind a second "Embargo register:"."""
    problem = _register_problem()
    gap = StandingGap(
        missing_log_indices=[2],
        conflicting_log_indices=[4],
        unusable_rows=[
            UnusableRow(path=tmp_path / "x.jsonl", line=3, reason="not JSON")
        ],
        unreadable_entries=[UnreadableEntry(log_index=5, reason="no stamp")],
        register_problem=problem,
    )
    lines = view.gap_lines(gap)
    assert lines[0] == "Missing log indices: [2]"
    assert lines[1] == "Conflicting log indices: [4]"
    assert "not JSON" in lines[2]
    assert lines[3] == "Unreadable entry at log index 5: no stamp"
    assert lines[4] == problem


@pytest.mark.spec("DRPT-03-009")
def test_a_vince_participant_never_reads_as_its_opaque_id():
    """#6685: a reading whose payloads name no actor shows no ``urn:uuid``."""
    analysis = analyse(translate(ACTIVE))
    assert analysis.standing is not None
    participants = analysis.standing.participants
    rows = view.participant_rows(participants, analysis.actor_names)
    assert rows
    assert {row["Participant"] for row in rows} == {UNNAMED_ACTOR}
    assert all(str(row["Actor"]).startswith("urn:uuid:") for row in rows)
    columns = view.desiderata_rows(participants, analysis.actor_names)
    assert len(columns) == len(scope_desiderata())
    for row in columns:
        vendor_columns = [c for c in row if c not in ("Desideratum", "Events")]
        assert len(set(vendor_columns)) == len(vendor_columns)
        assert all(c.startswith(UNNAMED_ACTOR) for c in vendor_columns)
