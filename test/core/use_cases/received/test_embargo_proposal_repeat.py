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
"""A proposal of terms the case already holds changes nothing (EP-09-032).

The CASE_MANAGER decides a repeated proposal by its end time, not by its
ids or its sender.  The two strict markers of the rule live beside the relay
tests in ``test_embargo_revision_relay.py``; these cover the rest of #5720:
an initial proposal at EM ``PROPOSED``, a repeat from another participant,
the counter-proposal of the in-force terms during a revision (EP-09-020), and
the guard's own reading of the register.
"""

import logging
from typing import cast

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.test_embargo_revision_relay import (
    MANAGER,
    OTHER_A,
    PROPOSER,
    _active_case_with_revision,
    _active_id,
    _deliver,
    _ledger_entries,
    _participant_of,
    _proposal,
    _relayed_invites,
    _unbound_case,
)
from test.support.embargo_register import propose
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.embargo.nodes.proposal_repeat import (
    EmbargoTermsNotHeldNode,
)
from vultron.core.behaviors.embargo.nodes.relay_guards import (
    case_manager_admits_proposal_guard,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent


def run_node(node, dl, *, actor_id: str) -> Status:
    """Run *node* alone against *dl* as *actor_id*."""
    return BTTestScenario(actor_id, dl=dl).run(node).status


def _terms(dl, case_id: str, slug: str, end_time) -> as_EmbargoEvent:
    """Fresh terms under a fresh id, stored like a received proposal's."""
    terms = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/{slug}",
        content=f"Terms {slug}",
        context=case_id,
        end_time=end_time,
    )
    dl.create(terms)
    return terms


def _sign_active(dl, case_id: str, actor_id: str) -> None:
    """Bind *actor_id* to the embargo in force, making it an active
    participant whose proposal is acted on (CM-10-004, ADR-0115)."""
    participant = _participant_of(dl, case_id, actor_id)
    participant.sign_embargo(_active_id(dl, case_id))
    dl.save(participant)


@pytest.mark.spec("EP-09-032")
def test_an_initial_proposal_repeating_pending_terms_registers_nothing(
    make_payload,
):
    """At EM ``PROPOSED`` a second first proposal of the same end time is a
    duplicate: nothing is registered, committed or relayed."""
    case_id = "https://example.org/cases/repeat-initial"
    dl, first = _unbound_case(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _deliver(dl, _proposal(first, case_id), make_payload, MANAGER)
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.em_state == EM.PROPOSED
    entries_before = [e.id_ for e in _ledger_entries(dl, case_id)]
    outbox_before = set(dl.outbox_list())

    repeat = _terms(dl, case_id, "repeat", first.end_time)
    verdict = _deliver(
        dl,
        _proposal(repeat, case_id, id_=f"{case_id}/embargo_proposals/repeat"),
        make_payload,
        MANAGER,
    )

    assert verdict.disposition is HandlerDisposition.SKIPPED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.em_state == EM.PROPOSED
    assert case.proposed_embargo_ids == [first.id_]
    assert [e.id_ for e in _ledger_entries(dl, case_id)] == entries_before
    assert set(dl.outbox_list()) == outbox_before


@pytest.mark.spec("EP-09-032")
def test_the_same_terms_from_another_participant_are_a_duplicate(
    make_payload,
):
    """Whoever proposes them, terms already pending are not proposed again.

    The other participant holds the relayed Invite to those terms and agrees
    by accepting it (EP-09-004).
    """
    case_id = "https://example.org/cases/repeat-other-sender"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)
    _sign_active(dl, case_id, OTHER_A)
    entries_before = [e.id_ for e in _ledger_entries(dl, case_id)]
    outbox_before = set(dl.outbox_list())

    repeat = _terms(dl, case_id, "other", revision.end_time)
    verdict = _deliver(
        dl,
        _proposal(
            repeat,
            case_id,
            actor=OTHER_A,
            id_=f"{case_id}/embargo_proposals/other",
        ),
        make_payload,
        MANAGER,
    )

    assert verdict.disposition is HandlerDisposition.SKIPPED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.proposed_embargo_ids == [revision.id_]
    assert [e.id_ for e in _ledger_entries(dl, case_id)] == entries_before
    assert set(dl.outbox_list()) == outbox_before


@pytest.mark.spec("EP-09-032")
def test_different_terms_are_still_registered_and_relayed(make_payload):
    """A proposal one day off the pending terms is new: committed, relayed."""
    case_id = "https://example.org/cases/repeat-different-terms"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)
    _sign_active(dl, case_id, OTHER_A)
    invites_before = len(_relayed_invites(dl))

    other = _terms(dl, case_id, "different", days_from_now_utc(91))
    verdict = _deliver(
        dl,
        _proposal(
            other,
            case_id,
            actor=OTHER_A,
            id_=f"{case_id}/embargo_proposals/different",
        ),
        make_payload,
        MANAGER,
    )

    assert verdict.disposition is HandlerDisposition.APPLIED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert set(case.proposed_embargo_ids) == {revision.id_, other.id_}
    assert len(_relayed_invites(dl)) == invites_before + 1


@pytest.mark.spec("EP-09-032")
@pytest.mark.spec("EP-09-020")
def test_the_in_force_terms_during_a_revision_are_a_counter_proposal(
    make_payload,
):
    """While a revision is pending, proposing the in-force end time is a
    counter-proposal to keep the current terms, so it is committed."""
    case_id = "https://example.org/cases/repeat-keep-current"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    in_force = cast(as_EmbargoEvent, dl.read(_active_id(dl, case_id)))
    _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)
    _sign_active(dl, case_id, OTHER_A)
    entries_before = len(_ledger_entries(dl, case_id))

    keep = _terms(dl, case_id, "keep", in_force.end_time)
    verdict = _deliver(
        dl,
        _proposal(
            keep,
            case_id,
            actor=OTHER_A,
            id_=f"{case_id}/embargo_proposals/keep",
        ),
        make_payload,
        MANAGER,
    )

    assert verdict.disposition is HandlerDisposition.APPLIED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.em_state == EM.REVISE
    assert set(case.proposed_embargo_ids) == {revision.id_, keep.id_}
    assert len(_ledger_entries(dl, case_id)) > entries_before
    assert [
        a.to for a in _relayed_invites(dl) if a.attributed_to == OTHER_A
    ] == [[PROPOSER]]


# ---------------------------------------------------------------------------
# The guard alone
# ---------------------------------------------------------------------------


def _guard_status(dl, case_id: str, terms) -> tuple[Status, bool]:
    node = EmbargoTermsNotHeldNode(
        case_id=case_id, embargo_id=terms.id_, embargo=terms
    )
    status = run_node(node, dl, actor_id=MANAGER)
    return status, node.failed_as_repeat


@pytest.mark.spec("EP-09-032")
def test_the_guard_admits_new_terms_and_flags_held_ones():
    """New terms SUCCEED; the in-force end time with nothing pending FAILS
    as a repeat, not as a refusal."""
    case_id = "https://example.org/cases/repeat-guard"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    in_force = cast(as_EmbargoEvent, dl.read(_active_id(dl, case_id)))

    assert _guard_status(
        dl, case_id, _terms(dl, case_id, "new", days_from_now_utc(120))
    ) == (Status.SUCCESS, False)
    assert _guard_status(
        dl, case_id, _terms(dl, case_id, "held", in_force.end_time)
    ) == (Status.FAILURE, True)


@pytest.mark.spec("EP-09-032")
def test_the_guard_admits_a_proposal_on_a_case_this_store_lacks():
    """With no case to compare against, nothing is a repeat."""
    case_id = "https://example.org/cases/repeat-guard-no-case"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    node = EmbargoTermsNotHeldNode(
        case_id="https://example.org/cases/absent",
        embargo_id=revision.id_,
        embargo=revision,
    )

    assert run_node(node, dl, actor_id=MANAGER) == Status.SUCCESS
    assert node.failed_as_repeat is False


@pytest.mark.spec("EP-09-032")
def test_the_guard_reads_stored_terms_when_none_are_inline():
    """A proposal named by bare id is compared by its stored terms; one that
    does not resolve is admitted, as there is nothing to compare."""
    case_id = "https://example.org/cases/repeat-guard-stored"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    in_force = cast(as_EmbargoEvent, dl.read(_active_id(dl, case_id)))
    held = _terms(dl, case_id, "stored", in_force.end_time)

    by_id = EmbargoTermsNotHeldNode(case_id=case_id, embargo_id=held.id_)
    assert run_node(by_id, dl, actor_id=MANAGER) == Status.FAILURE
    assert by_id.failed_as_repeat is True

    missing = EmbargoTermsNotHeldNode(
        case_id=case_id, embargo_id=f"{case_id}/embargo_events/missing"
    )
    assert run_node(missing, dl, actor_id=MANAGER) == Status.SUCCESS
    assert missing.failed_as_repeat is False


@pytest.mark.spec("EP-09-032")
def test_a_participant_replica_is_not_asked_about_held_terms(make_payload):
    """Only the CASE_MANAGER decides a repeat: the terms check is declared on
    its path alone, so a replica's relayed Invite to terms the replica
    already holds is still applied and answered."""
    case_id = "https://example.org/cases/repeat-guard-replica"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=OTHER_A, participants=[PROPOSER, OTHER_A]
    )
    in_force = cast(as_EmbargoEvent, dl.read(_active_id(dl, case_id)))
    held = _terms(dl, case_id, "replica", in_force.end_time)
    relayed = em_propose_embargo_activity(
        held,
        context=case_id,
        actor=MANAGER,
        attributed_to=PROPOSER,
        to=[OTHER_A],
        id_=f"{case_id}/embargo_invites/replica",
    )

    verdict = _deliver(dl, relayed, make_payload, receiving_actor_id=OTHER_A)

    assert verdict.disposition is HandlerDisposition.APPLIED
    assert case_manager_admits_proposal_guard(
        case_id, held.id_, held
    ).paths == frozenset({ReceivedPath.CASE_MANAGER})


@pytest.mark.spec("EP-09-032")
def test_the_guard_does_not_match_a_proposal_against_its_own_entry():
    """An Invite naming the embargo in force itself repeats no *other*
    proposal's terms, so the terms guard leaves it to the id-keyed checks."""
    case_id = "https://example.org/cases/repeat-guard-own-entry"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    in_force = cast(as_EmbargoEvent, dl.read(_active_id(dl, case_id)))

    assert _guard_status(dl, case_id, in_force) == (Status.SUCCESS, False)


@pytest.mark.spec("EP-09-032")
def test_an_unreadable_pending_entry_is_left_out_with_a_warning(caplog):
    """A pending entry whose terms do not resolve cannot be compared, so it
    is skipped with a WARNING and the proposal is judged by the rest."""
    case_id = "https://example.org/cases/repeat-guard-unreadable"
    dl, _ = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    case = cast(VulnerabilityCase, dl.read(case_id))
    missing_id = f"{case_id}/embargo_events/never-stored"
    propose(case, missing_id)
    dl.save(case)
    terms = _terms(dl, case_id, "judged", days_from_now_utc(60))

    with caplog.at_level(logging.WARNING):
        assert _guard_status(dl, case_id, terms) == (Status.SUCCESS, False)

    assert any(
        missing_id in r.getMessage() and r.levelno == logging.WARNING
        for r in caplog.records
    )
