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

"""A CASE_MANAGER note that answers a received activity is recorded once.

The re-run of a record a run left in holding runs the handling tree again
(ADR-0154).  Each note the CASE_MANAGER writes in answer to a received
activity -- the RSH-06-004 RM-anomaly note after an accepted gap and after a
refused regression, the CSB-18 diagnostic and the CM-16-016 reinforcing
suggestion -- takes an id derived from the CASE_MANAGER, the received
activity and the note's kind, so the re-run names the note its first run
stored, and its ``Add(Note)`` is the one already committed and announced
(ID-04-004).  Each test runs the received activity twice from holding and
compares the ledger and the outbox after each run by content.

The refused regression is the case a skip used to mask: the refusal stage
skips its effects on a re-run, so one test turns the skip off to prove the
id, not the skip, keeps the note single.
"""

import json
from typing import Any

import pytest

from test.architecture._received_tree_builds import built_received_trees
from test.support.failed_teardown import fail_pxa_teardown
from test.support.ledger import ledger_entries
from test.support.received import received_event
from test.support.rerun_from_holding import Rerun, rerun_from_holding
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.case.nodes import earlier_run
from vultron.core.behaviors.note.case_manager_note import (
    _CommitCaseManagerNoteBase,
)
from vultron.core.models.activity_ids import derived_object_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.errors import VultronWiringError
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    recommend_actor_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.parser import parse_activity

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)
from .test_case_manager_note_replay import RECOMMENDED, _notes, _set_rm


def _event_for(net: LedgerNetwork, activity: Any) -> Any:
    """*activity* as the CASE_MANAGER's inbox extracts it, stamped as sent."""
    body = net.stamp(
        json.loads(dump_outbound_body(activity)), receiver=MANAGER
    )
    return received_event(
        parse_activity(body), as_sent=True, receiving_actor_id=MANAGER
    )


def _note_entries(net: LedgerNetwork) -> list[str]:
    return [
        e.log_object_id
        for e in ledger_entries(net.stores[MANAGER], net.case_id)
        if e.semantic_type == "add_note_to_case"
    ]


def _assert_recorded_once(
    net: LedgerNetwork, rerun: Rerun, kind: str, event: Any
) -> None:
    """The first run recorded the note under its derived id; the re-run nothing."""
    notes = [n.id_ for n in _notes(net, MANAGER)]
    expected = derived_object_id(
        "case-manager-note", kind, MANAGER, event.activity_id
    )
    # The first run reached its effect: the note is on the case, and its
    # Add(Note) is committed.
    assert expected in notes, notes
    assert len(_note_entries(net)) >= 1
    assert rerun.after_first.ledger != (), "the first run committed nothing"
    assert rerun.doubled == []
    assert rerun.after_second == rerun.after_first
    assert notes.count(expected) == 1


@pytest.mark.spec("ID-04-004", "RSH-06-004")
def test_a_rerun_rm_gap_records_no_second_note():
    net = LedgerNetwork(
        "https://example.org/cases/note-rerun-rm-gap", em_state=EM.NONE
    )
    _set_rm(net, BYSTANDER, RM.RECEIVED)
    event = _event_for(
        net,
        rm_engage_case_activity(
            net.case(BYSTANDER), actor=BYSTANDER, to=[MANAGER]
        ),
    )

    rerun = rerun_from_holding(net.stores[MANAGER], event)

    assert rerun.first.disposition is HandlerDisposition.APPLIED
    _assert_recorded_once(net, rerun, "rm-anomaly", event)


def _regression_event(net: LedgerNetwork) -> Any:
    participant = net.stores[MANAGER].read(
        net.case(MANAGER).actor_participant_index[BYSTANDER]
    )
    assert isinstance(participant, CaseParticipant)
    status = ParticipantStatus(
        context=net.case_id,
        attributed_to=BYSTANDER,
        rm=RmDimension(state=RM.VALID),
    )
    return _event_for(
        net,
        add_status_to_participant_activity(
            status, target=participant, actor=BYSTANDER, to=[MANAGER]
        ),
    )


@pytest.mark.spec("ID-04-004", "RSH-06-004", "CLP-10-044")
def test_a_rerun_rm_regression_records_no_second_note():
    net = LedgerNetwork(
        "https://example.org/cases/note-rerun-rm-regression", em_state=EM.NONE
    )
    _set_rm(net, BYSTANDER, RM.ACCEPTED)
    event = _regression_event(net)

    rerun = rerun_from_holding(net.stores[MANAGER], event)

    assert rerun.first.disposition is HandlerDisposition.REFUSED
    assert rerun.second.disposition is HandlerDisposition.REFUSED
    _assert_recorded_once(net, rerun, "rm-anomaly", event)


@pytest.mark.spec("ID-04-004", "RSH-06-004", "CLP-10-048")
def test_a_rerun_that_reaches_the_refusal_effects_records_no_second_note(
    monkeypatch,
):
    """The note, run again as a refusal effect, is still recorded once.

    The refusal stage skips its effects on a re-run, which would hide a
    minted id.  Here the stage reads every run as a first run, so the re-run
    reaches the RSH-06-004 note again, and only the derived id keeps it
    single.  The refusal notice's id is derived too, so nothing is sent
    twice either.
    """
    monkeypatch.setattr(
        earlier_run, "began_in_an_earlier_run", lambda *a, **k: False
    )
    net = LedgerNetwork(
        "https://example.org/cases/note-rerun-refusal-effect",
        em_state=EM.NONE,
    )
    _set_rm(net, BYSTANDER, RM.ACCEPTED)
    event = _regression_event(net)

    rerun = rerun_from_holding(net.stores[MANAGER], event)

    assert rerun.second.disposition is HandlerDisposition.REFUSED
    _assert_recorded_once(net, rerun, "rm-anomaly", event)


@pytest.mark.spec("ID-04-004", "CSB-18-002")
def test_a_rerun_pxa_em_diagnostic_records_no_second_note(monkeypatch):
    fail_pxa_teardown(monkeypatch)
    net = LedgerNetwork(
        "https://example.org/cases/note-rerun-csb-18", em_state=EM.ACTIVE
    )
    event = _event_for(net, net.pxa_report(OWNER, CS_pxa.Pxa))

    rerun = rerun_from_holding(net.stores[MANAGER], event)

    assert rerun.first.disposition is HandlerDisposition.APPLIED
    _assert_recorded_once(net, rerun, "pxa-em-invariant", event)


@pytest.mark.spec("ID-04-004", "CM-16-016")
def test_a_rerun_reinforcing_suggestion_records_no_second_note():
    net = LedgerNetwork(
        "https://example.org/cases/note-rerun-reinforcing", em_state=EM.NONE
    )

    def _recommend(recommender: str) -> Any:
        return _event_for(
            net,
            recommend_actor_activity(
                RECOMMENDED,
                target=net.case_id,
                actor=recommender,
                to=[MANAGER],
                content=f"{recommender} vouches for them",
            ),
        )

    first = net.receive_event(MANAGER, _recommend(PROPOSER))
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    event = _recommend(BYSTANDER)

    rerun = rerun_from_holding(net.stores[MANAGER], event)

    assert rerun.first.disposition is HandlerDisposition.APPLIED
    _assert_recorded_once(net, rerun, "duplicate-recommendation", event)


def test_every_received_note_kind_is_named() -> None:
    """Each note class a received tree runs names its kind, distinctly.

    A class with no kind raises when it answers a received activity, so a
    new one is caught the first time it runs; this keeps the kinds the
    derived ids are built from distinct.
    """
    kinds = {
        cls.__name__: cls._NOTE_KIND
        for cls in _subclasses(_CommitCaseManagerNoteBase)
        if cls._NOTE_KIND is not None
    }
    assert len(set(kinds.values())) == len(kinds), kinds
    assert set(kinds) >= {
        "EmitRMGapNoteNode",
        "EmitNoteDuplicateRecommendationToOwnerNode",
        "PxaEmInvariantDiagnosticNode",
    }


@pytest.mark.spec("ID-04-004")
def test_every_note_node_in_a_received_tree_names_its_kind() -> None:
    """Checked over every built received tree, not only when a note runs.

    A kindless note class raises only on the run that builds its note, which
    a rare arm may never reach in a test.
    """
    trees = built_received_trees()
    notes = {
        (site, type(node).__name__): node._NOTE_KIND
        for site, root in trees.items()
        for node in root.iterate()
        if isinstance(node, _CommitCaseManagerNoteBase)
    }
    assert notes, "no received tree holds a CASE_MANAGER note node"
    assert sorted(k for k, kind in notes.items() if kind is None) == []


def _subclasses(
    cls: type[_CommitCaseManagerNoteBase],
) -> list[type[_CommitCaseManagerNoteBase]]:
    found: list[type[_CommitCaseManagerNoteBase]] = []
    for sub in cls.__subclasses__():
        found.append(sub)
        found.extend(_subclasses(sub))
    return found


class _KindlessNote(_CommitCaseManagerNoteBase):
    """A note class that names no kind, as a new one might."""

    def _compose(self) -> None:
        return None


@pytest.mark.spec("ID-04-004")
def test_a_note_with_no_kind_answering_a_received_activity_raises() -> None:
    """Its id would be minted, so a re-run would record it twice."""
    net = LedgerNetwork(
        "https://example.org/cases/note-rerun-no-kind", em_state=EM.NONE
    )
    node = _KindlessNote(case_id=net.case_id)
    node._answers = _regression_event(net)

    with pytest.raises(VultronWiringError, match="names no _NOTE_KIND"):
        node._derived_note_id(MANAGER)


@pytest.mark.spec("ID-04-004")
def test_a_note_answering_no_received_activity_gets_a_minted_id() -> None:
    """The add-note trigger answers nothing received: no derived id."""
    node = _KindlessNote(case_id="https://example.org/cases/c")
    node._answers = None

    assert node._derived_note_id(MANAGER) is None
