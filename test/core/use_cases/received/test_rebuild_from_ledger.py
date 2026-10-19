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

"""The rebuild-from-ledger check itself (#4294 AC-5, CLP-07-013, CM-23-016).

Every per-actor-store scenario in this package is rebuilt from its
CASE_MANAGER's ledger when it ends (``conftest``), and every exchange demo is
rebuilt before its node is cleared (``test/demo/_helpers.py``).  These tests
show the check is not vacuous: it reaches the CASE_MANAGER's state through a
whole embargo cycle, it catches a change no entry records,
it fails on a missing entry, it compares every participant status and case
status whole, ids and times included (#4295), and its one embargo exclusion
(#4748) hides only the termination's cause.
"""

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from test.support import ledger_rebuild
from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import (
    assert_rebuilds_from_ledger,
    case_file_differences,
    creation_records,
    rebuild_from_ledger,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.embargo_termination import TerminationCauseKind
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    LedgerNetwork,
    rebuild_every_network,
)
from .conftest import call_passed
from .test_embargo_activation_copy import _owner_activates, _propose
from .test_embargo_proposal_answer_copy import _participant_answers


def _negotiated(case_suffix: str) -> tuple[LedgerNetwork, str]:
    """A revision proposed, answered by the bystander, activated by the owner."""
    net = LedgerNetwork(f"https://example.org/cases/rebuild-{case_suffix}")
    revision_id = _propose(net, "shorter", 20)
    _participant_answers(net, BYSTANDER, accept=True)
    verdict = _owner_activates(net, revision_id)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return net, revision_id


def _seed(net: LedgerNetwork) -> list[Any]:
    seed = net.rebuild_seed
    assert seed is not None, "the scenario committed no entry"
    return seed


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_a_negotiated_revision_rebuilds_from_the_ledger_alone():
    """Proposal, relayed Invites, rows, an answer, the activation and its
    carry-overs all reach an empty store from the ledger."""
    net, revision_id = _negotiated("cycle")
    manager = net.stores[MANAGER]

    replica = rebuild_from_ledger(
        manager, net.case_id, as_actor=BYSTANDER, seed=_seed(net)
    )

    rebuilt = cast(VulnerabilityCase, replica.read(net.case_id))
    assert rebuilt.em_state == EM.ACTIVE
    assert rebuilt.active_embargo_id == revision_id
    assert case_file_differences(manager, replica, net.case_id) == []


@pytest.mark.spec("CLP-07-013")
def test_a_change_no_entry_records_is_caught():
    """The check is not vacuous: a row written outside the ledger differs."""
    net = _tampered("unrecorded")
    net.bypass_ledger()

    with pytest.raises(AssertionError, match="embargo_consents"):
        assert_rebuilds_from_ledger(
            net.stores[MANAGER],
            net.case_id,
            as_actor=BYSTANDER,
            seed=_seed(net),
        )


@pytest.mark.spec("CM-23-016")
def test_a_missing_entry_fails_the_rebuild(monkeypatch):
    """An entry the replica cannot apply is named, never passed over."""
    net, _ = _negotiated("gap")
    entries = ledger_entries(net.stores[MANAGER], net.case_id)
    dropped = entries[1]

    with monkeypatch.context() as patched:
        patched.setattr(
            ledger_rebuild,
            "ledger_entries",
            lambda *_a: [e for e in entries if e.id_ != dropped.id_],
        )
        with pytest.raises(AssertionError, match="was deferred"):
            rebuild_from_ledger(
                net.stores[MANAGER],
                net.case_id,
                as_actor=BYSTANDER,
                seed=_seed(net),
            )


def _terminated(cause: bool, reason: TerminationReason) -> VulnerabilityCase:
    """A case whose one register entry is TERMINATED as given."""
    termination: dict[str, Any] = {"reason": reason}
    if cause:
        termination["cause"] = {
            "kind": TerminationCauseKind.THREAT_SIGNAL,
            "signals": ["P"],
        }
    return VulnerabilityCase.model_validate(
        {
            "id_": "https://example.org/cases/rebuild-register",
            "name": "Register",
            "embargo_register": [
                {
                    "embargo": "https://example.org/embargo_events/e1",
                    "status": EmbargoRegisterStatus.TERMINATED,
                    "termination": termination,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "replica, differs",
    [
        (_terminated(False, TerminationReason.EARLY), False),
        (_terminated(False, TerminationReason.END_TIME_REACHED), True),
    ],
    ids=["cause-only", "reason"],
)
def test_only_the_termination_cause_is_left_out(replica, differs):
    """#4748: a replica cannot learn the cause; the reason is still compared."""
    manager = _terminated(True, TerminationReason.EARLY)

    assert (
        ledger_rebuild._register(replica) != ledger_rebuild._register(manager)
    ) is differs


_STATUS_CASE = "https://example.org/cases/rebuild-status"
_STATUS_ACTOR = "https://example.org/actors/status"


def _with_status(status: ParticipantStatus) -> CaseParticipant:
    return CaseParticipant(
        id_=f"{_STATUS_CASE}/participants/status",
        attributed_to=_STATUS_ACTOR,
        context=_STATUS_CASE,
        participant_statuses=[status],
    )


def _status(state: RM, **fields: Any) -> ParticipantStatus:
    return ParticipantStatus(
        attributed_to=_STATUS_ACTOR,
        context=_STATUS_CASE,
        rm=RmDimension(state=state),
        **fields,
    )


@pytest.mark.parametrize(
    "replica",
    [
        _status(RM.VALID, id_=f"{_STATUS_CASE}/statuses/replayed"),
        _status(
            RM.VALID,
            id_=f"{_STATUS_CASE}/statuses/held",
            published=datetime(2100, 1, 1, tzinfo=UTC),
            updated=datetime(2100, 1, 1, tzinfo=UTC),
        ),
        _status(RM.INVALID, id_=f"{_STATUS_CASE}/statuses/held"),
    ],
    ids=["id", "times", "rm-state"],
)
@pytest.mark.spec("CM-23-016")
def test_a_status_is_compared_whole(replica):
    """#4295: a replica copies each status, so its id and times compare too."""
    manager = _status(RM.VALID, id_=f"{_STATUS_CASE}/statuses/held")

    assert ledger_rebuild._participant(
        _with_status(replica)
    ) != ledger_rebuild._participant(_with_status(manager))


@pytest.mark.spec("CLP-07-013")
def test_a_case_status_no_entry_records_is_caught():
    """A case status written outside the ledger differs from the rebuild."""
    net, _ = _negotiated("case-status")
    net.bypass_ledger()
    manager = net.stores[MANAGER]
    case = net.case(MANAGER)
    current = case.current_status
    case.add_case_status(
        CaseStatus(context=net.case_id, em=current.em, pxa=current.pxa)
    )
    manager.save(case)

    with pytest.raises(AssertionError, match="case statuses"):
        assert_rebuilds_from_ledger(
            manager, net.case_id, as_actor=BYSTANDER, seed=_seed(net)
        )


def test_creation_records_stop_at_the_first_act():
    """Only the leading creation entries seed the store; acts are replayed."""
    case = VulnerabilityCase(
        id_="https://example.org/cases/rebuild-seed", name="Seed"
    )
    entries = [
        CaseLedgerEntry.model_construct(
            event_type="create_case", payload_snapshot={"object": case}
        ),
        CaseLedgerEntry.model_construct(
            event_type="invite_to_embargo_on_case", payload_snapshot={}
        ),
        CaseLedgerEntry.model_construct(
            event_type="create_case",
            payload_snapshot={"object": case.model_copy(update={"name": "X"})},
        ),
    ]

    (record,) = creation_records(entries)

    assert record == case


# -- the check every scenario runs (conftest) -------------------------------


def _tampered(case_suffix: str) -> LedgerNetwork:
    """A negotiated network whose CASE_MANAGER holds a row no entry records."""
    net, revision_id = _negotiated(case_suffix)
    manager = net.stores[MANAGER]
    record = cast(
        CaseParticipant,
        manager.read(net.case(MANAGER).actor_participant_index[BYSTANDER]),
    )
    record.embargo_consents = [
        row.model_copy(update={"state": EmbargoConsentState.DECLINED})
        if row.embargo_id == revision_id
        else row
        for row in record.embargo_consents
    ]
    manager.save(record)
    return net


def test_the_scenario_check_fails_a_network_that_differs():
    net = _tampered("check-fails")

    with pytest.raises(AssertionError, match="embargo_consents"):
        rebuild_every_network([net])
    net.bypass_ledger()  # the test's own write; skip the autouse check


def test_the_scenario_check_skips_a_bypassed_network():
    net = _tampered("check-bypassed")
    net.bypass_ledger()

    rebuild_every_network([net])


def test_the_scenario_check_skips_a_network_with_no_entries():
    net = LedgerNetwork("https://example.org/cases/rebuild-no-entries")

    assert net.rebuild_seed is None
    rebuild_every_network([net])


def test_the_scenario_check_refuses_entries_with_no_seed():
    """A network that committed entries but captured no seed is not skipped."""
    net, _ = _negotiated("check-no-seed")
    net._seed = None

    with pytest.raises(AssertionError, match="no rebuild seed"):
        rebuild_every_network([net])
    net.bypass_ledger()  # the test's own break; skip the autouse check


class _Item:
    """A stand-in test item: only its stash is read."""

    def __init__(self, report: Any | None) -> None:
        self.stash = pytest.Stash()
        if report is not None:
            from .conftest import _CALL_REPORT

            self.stash[_CALL_REPORT] = report


class _Report:
    def __init__(self, passed: bool) -> None:
        self.passed = passed


@pytest.mark.parametrize(
    "report, checked",
    [(_Report(True), True), (_Report(False), False), (None, False)],
    ids=["passed", "failed", "never-called"],
)
def test_the_scenario_check_runs_only_after_a_passing_call(report, checked):
    assert call_passed(cast(Any, _Item(report))) is checked
