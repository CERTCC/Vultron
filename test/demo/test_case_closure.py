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

"""The shared closure phase: the Case Owner leaves last (CM-23-015).

Covers :func:`vultron.demo.helpers.closure.close_case_owner_last` against the
real ``demo_gate`` (``vultron/demo/AGENTS.md`` § causal gating, rule 8), the
ledger half of the closure milestone,
:func:`vultron.demo.helpers.milestones.case_closure_violations` and
:func:`~vultron.demo.helpers.milestones.verify_case_closure_recorded`, and the
CM-23-004 checks: every participant ``RM.CLOSED`` in the CASE_MANAGER's store,
and each leaver's own replica ending at its own closure.
"""

from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.utils as demo_utils
from test.support.embargo_register import activate, terminate
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.demo.helpers import closure, milestones
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.milestones import (
    case_closure_violations,
    own_closure_tail_index,
    verify_case_closure_recorded,
)
from vultron.demo.helpers.sync import wait_for_replica_ledger_ending_at
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE = "urn:uuid:case"
_MANAGER = "http://owner:7999/api/v2/actors/case-actor"
_OWNER = "http://owner:7999/api/v2/actors/owner"
_FINDER = "http://finder:7999/api/v2/actors/finder"
_VENDOR = "http://vendor:7999/api/v2/actors/vendor"


@pytest.fixture(autouse=True)
def _clean_failures():
    demo_utils.reset_demo_failures()
    yield
    demo_utils.reset_demo_failures()


def _leaver(actor_id: str) -> CaseLeaver:
    actor = MagicMock()
    actor.id_ = actor_id
    return CaseLeaver(client=MagicMock(), actor=actor)


def _case() -> MagicMock:
    case = MagicMock()
    case.id_ = _CASE
    return case


# ---------------------------------------------------------------------------
# close_case_owner_last
# ---------------------------------------------------------------------------


class TestCloseCaseOwnerLast:
    def _run(
        self,
        others,
        owner,
        wait_side_effect=None,
        ledger_side_effect=None,
        own_side_effect=None,
        em_side_effect=None,
    ):
        sent: list[str] = []
        session_cls = MagicMock(
            side_effect=lambda client, actor: (
                sent.append(actor.id_) or MagicMock()
            )
        )
        # The owner's replica-EM gate records its call into ``sent``, so a
        # test can see it sits between the departures and the owner's Leave.
        self.em_gate = MagicMock(
            side_effect=em_side_effect
            or (lambda manager, owner, case_id: sent.append("em-gate"))
        )
        authority = MagicMock()
        self.manager = MagicMock()
        with (
            patch.object(closure, "ActorSession", session_cls),
            patch.object(
                closure, "_case_manager_reader", return_value=self.manager
            ) as resolve,
            patch.object(
                closure,
                "wait_for_participant_rm_state",
                side_effect=wait_side_effect,
            ) as wait,
            patch.object(
                closure,
                "verify_case_closure_recorded",
                side_effect=ledger_side_effect,
            ) as recorded,
            patch.object(closure, "verify_case_closed") as closed,
            patch.object(
                closure, "case_manager_ledger", return_value=["ledger"]
            ),
            patch.object(
                closure, "_verify_own_closure", side_effect=own_side_effect
            ) as own_closure,
            patch.object(closure, "_wait_for_owner_replica_em", self.em_gate),
        ):
            departed = close_case_owner_last(
                case=_case(),
                authority_client=authority,
                others=others,
                owner=owner,
                milestone="M7",
            )
        self.recorded = recorded
        self.closed = closed
        self.own_closure = own_closure
        return sent, departed, wait, resolve, authority

    @pytest.mark.spec("CM-23-015")
    def test_owner_leaves_after_every_other_participant(self):
        sent, departed, _, _, _ = self._run(
            [_leaver(_FINDER), _leaver(_VENDOR)], _leaver(_OWNER)
        )
        assert sent == [_FINDER, _VENDOR, "em-gate", _OWNER]
        assert departed == [_FINDER, _VENDOR, _OWNER]
        assert not demo_utils._demo_failures

    @pytest.mark.spec("CM-23-015")
    def test_owner_leave_gated_on_each_departure_in_manager_store(self):
        """The gate reads RM.CLOSED for each leaver where it commits (EDF-06-002)."""
        _, _, wait, resolve, authority = self._run(
            [_leaver(_FINDER), _leaver(_VENDOR)], _leaver(_OWNER)
        )
        resolve.assert_called_once_with(authority, _CASE)
        assert [c.kwargs for c in wait.call_args_list] == [
            {
                "client": self.manager,
                "case_id": _CASE,
                "actor_id": actor_id,
                "expected_states": {RM.CLOSED},
            }
            for actor_id in (_FINDER, _VENDOR)
        ]

    @pytest.mark.spec("CM-23-013")
    def test_unrecorded_departure_fails_gate_once_and_owner_stays(self):
        """An owner Leave over an unrecorded departure would lose it (CM-23-013)."""
        sent, departed, _, _, _ = self._run(
            [_leaver(_FINDER)],
            _leaver(_OWNER),
            wait_side_effect=AssertionError("finder never RM.CLOSED"),
        )
        assert sent == [_FINDER]
        assert departed == [_FINDER]
        self.recorded.assert_not_called()
        self.closed.assert_not_called()
        self.own_closure.assert_not_called()
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "CM-23-015" in failure

    @pytest.mark.spec("CM-23-015")
    def test_ledger_check_runs_after_the_owner_leaves(self):
        _, departed, _, _, _ = self._run([_leaver(_FINDER)], _leaver(_OWNER))
        self.recorded.assert_called_once_with(
            client=self.manager, case_id=_CASE, departed_actor_ids=departed
        )

    @pytest.mark.spec("CM-23-004")
    def test_every_closure_is_verified_in_the_case_managers_store(self):
        """All participants RM.CLOSED is read where the CASE_MANAGER lives."""
        self._run([_leaver(_FINDER)], _leaver(_OWNER))
        self.closed.assert_called_once_with(
            case_manager_client=self.manager, case_id=_CASE
        )

    @pytest.mark.spec("CM-23-004")
    def test_each_leaver_checks_its_own_replica_owner_included(self):
        """No replica is checked for anyone else's closure (CM-23-004)."""
        finder, vendor, owner = (
            _leaver(_FINDER),
            _leaver(_VENDOR),
            _leaver(_OWNER),
        )
        self._run([finder, vendor], owner)
        assert [c.args[0] for c in self.own_closure.call_args_list] == [
            finder,
            vendor,
            owner,
        ]
        assert all(
            c.args[2] == ["ledger"] for c in self.own_closure.call_args_list
        )

    def test_a_leaver_whose_replica_lags_is_one_check_failure(self):
        """An own-closure check failure is recorded and the next one runs."""
        self._run(
            [_leaver(_FINDER)],
            _leaver(_OWNER),
            own_side_effect=[AssertionError("finder lags"), None],
        )
        assert self.own_closure.call_count == 2
        (failure,) = demo_utils._demo_failures
        assert not failure.startswith("GATE FAILED")
        assert "replica holds its own closure" in failure
        assert "finder lags" in failure

    def test_ledger_check_failure_is_recorded_under_the_milestone(self):
        """A ledger-order failure is a check, not a gate: it is recorded once."""
        sent, _, _, _, _ = self._run(
            [_leaver(_FINDER)],
            _leaver(_OWNER),
            ledger_side_effect=AssertionError("finder left after closure"),
        )
        assert sent == [_FINDER, "em-gate", _OWNER]
        (failure,) = demo_utils._demo_failures
        assert not failure.startswith("GATE FAILED")
        assert (
            "M7: every departure recorded before case_fully_closed" in failure
        )

    @pytest.mark.spec("TRIG-13-003")
    def test_owner_leave_gated_on_its_replica_reading_the_canonical_em(self):
        """The owner's replica must catch up before leave-case reads it."""
        owner = _leaver(_OWNER)
        sent, _, _, _, _ = self._run([_leaver(_FINDER)], owner)
        self.em_gate.assert_called_once_with(self.manager, owner, _CASE)
        assert sent == [_FINDER, "em-gate", _OWNER]

    @pytest.mark.spec("TRIG-13-003")
    def test_lagging_owner_replica_fails_the_gate_and_owner_stays(self):
        """An owner replica still embargoed would get leave-case's 409."""
        sent, departed, _, _, _ = self._run(
            [_leaver(_FINDER)],
            _leaver(_OWNER),
            em_side_effect=AssertionError("owner replica still ACTIVE"),
        )
        assert sent == [_FINDER]
        assert departed == [_FINDER]
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")

    def test_owner_listed_among_others_is_refused(self):
        with pytest.raises(ValueError, match="Case Owner"):
            self._run([_leaver(_FINDER), _leaver(_OWNER)], _leaver(_OWNER))


# ---------------------------------------------------------------------------
# case_closure_violations
# ---------------------------------------------------------------------------


def _entry(index: int, event_type: str, actor: str, **object_: str) -> dict:
    snapshot: dict = {"actor": actor}
    if object_:
        snapshot["object"] = object_
    return {
        "case_id": _CASE,
        "log_index": index,
        "event_type": event_type,
        "payload_snapshot": snapshot,
    }


def _status(index: int, attributed_to: str, rm_state: str) -> dict:
    return _entry(
        index,
        "add_participant_status_to_participant",
        _MANAGER,
        attributedTo=attributed_to,
        rmState=rm_state,
    )


def _owner_last_ledger() -> list[dict]:
    """The FV closure tail: Finder leaves, then the owner closes the case.

    Each ``close_case`` is followed by the status entry the CASE_MANAGER
    commits for the leaver's closure step (CM-23-001).
    """
    return [
        _status(0, _FINDER, "ACCEPTED"),
        _status(1, _OWNER, "ACCEPTED"),
        _entry(2, "close_case", _FINDER),
        _status(3, _FINDER, "CLOSED"),
        _entry(4, "close_case", _OWNER),
        _status(5, _OWNER, "CLOSED"),
        _status(6, _MANAGER, "CLOSED"),
        _entry(7, "case_fully_closed", _OWNER),
    ]


class TestCaseClosureViolations:
    @pytest.mark.spec("CM-23-015")
    def test_owner_last_ledger_records_the_closure(self):
        assert (
            case_closure_violations(
                _owner_last_ledger(), [_FINDER, _OWNER], _MANAGER
            )
            == []
        )

    def test_entry_order_is_read_from_log_index(self):
        assert (
            case_closure_violations(
                list(reversed(_owner_last_ledger())),
                [_FINDER, _OWNER],
                _MANAGER,
            )
            == []
        )

    @pytest.mark.spec("CM-23-013")
    def test_departure_after_case_fully_closed_is_reported(self):
        """The owner-first order every demo used to run (#4163)."""
        ledger = [
            _status(0, _FINDER, "ACCEPTED"),
            _entry(1, "close_case", _OWNER),
            _status(2, _OWNER, "CLOSED"),
            _status(3, _MANAGER, "CLOSED"),
            _entry(4, "case_fully_closed", _OWNER),
            _entry(5, "close_case", _FINDER),
        ]
        violations = case_closure_violations(
            ledger, [_FINDER, _OWNER], _MANAGER
        )
        assert len(violations) == 2
        assert f"no 'close_case' entry for {_FINDER!r}" in violations[0]
        assert "logIndex=5 'close_case'" in violations[1]

    def test_manager_housekeeping_after_boundary_is_allowed(self):
        """case_fully_closed is a write boundary, not the last entry (CM-23-002)."""
        ledger = [*_owner_last_ledger(), _status(8, _MANAGER, "CLOSED")]
        assert (
            case_closure_violations(ledger, [_FINDER, _OWNER], _MANAGER) == []
        )

    @pytest.mark.spec("CM-23-001")
    def test_close_case_alone_does_not_record_the_closure(self):
        """A Leave with no status entry after it leaves the leaver open.

        ``close_case`` records the Leave, not an RM state; the CASE_MANAGER's
        status entries record the closure (CM-23-001, #4210).
        """
        ledger = [
            _status(0, _FINDER, "ACCEPTED"),
            _entry(1, "close_case", _FINDER),
            _entry(2, "close_case", _OWNER),
            _status(3, _OWNER, "CLOSED"),
            _entry(4, "case_fully_closed", _OWNER),
        ]
        (violation,) = case_closure_violations(
            ledger, [_FINDER, _OWNER], _MANAGER
        )
        assert f"{_FINDER!r} is at RM 'ACCEPTED'" in violation

    def test_status_reopening_a_departed_actor_is_reported(self):
        ledger = [
            _entry(0, "close_case", _FINDER),
            _status(1, _FINDER, "ACCEPTED"),
            _entry(2, "close_case", _OWNER),
            _entry(3, "case_fully_closed", _OWNER),
        ]
        (violation,) = case_closure_violations(ledger, [_FINDER], _MANAGER)
        assert "RM 'ACCEPTED'" in violation

    @pytest.mark.parametrize("count", [0, 2])
    def test_boundary_must_appear_exactly_once(self, count):
        ledger = [e for e in _owner_last_ledger() if e["log_index"] < 7]
        ledger += [
            _entry(7 + i, "case_fully_closed", _OWNER) for i in range(count)
        ]
        assert case_closure_violations(ledger, [_FINDER], _MANAGER) == [
            f"expected exactly one 'case_fully_closed' entry, found {count}"
        ]

    def test_unknown_case_manager_is_reported(self):
        violations = case_closure_violations(
            _owner_last_ledger(), [_FINDER, _OWNER], None
        )
        assert violations == [
            "no CASE_MANAGER in the case's participant index; cannot tell its"
            " own entries from a participant's"
        ]

    def test_actor_reference_object_is_read_by_id(self):
        ledger = _owner_last_ledger()
        ledger[2]["payload_snapshot"]["actor"] = {"id": _FINDER}
        assert (
            case_closure_violations(ledger, [_FINDER, _OWNER], _MANAGER) == []
        )


class TestVerifyCaseClosureRecorded:
    def _client(self, ledger: list[dict]) -> MagicMock:
        client = MagicMock()
        client.get.return_value = {str(e["log_index"]): e for e in ledger} | {
            "other": {"case_id": "urn:uuid:other", "log_index": 99}
        }
        return client

    def _patches(self):
        return (
            patch.object(milestones, "wait_for_case_actor_ledger_event"),
            patch.object(
                milestones,
                "find_case_actor_participant_id",
                return_value=_MANAGER,
            ),
        )

    @pytest.mark.spec("CM-23-015")
    def test_reads_the_case_managers_store_after_the_boundary(self):
        client = self._client(_owner_last_ledger())
        waited, found = self._patches()
        with waited as wait, found:
            verify_case_closure_recorded(client, _CASE, [_FINDER, _OWNER])
        wait.assert_called_once_with(
            client=client, case_id=_CASE, event_type="case_fully_closed"
        )
        # The client is already bound to the CASE_MANAGER's store: read as
        # given, with no second store lookup.
        client.dl_path.assert_called_once_with("CaseLedgerEntrys/")

    def test_raises_with_every_violation(self):
        ledger = [
            *_owner_last_ledger(),
            _entry(8, "add_note_to_case", _VENDOR),
        ]
        waited, found = self._patches()
        with waited, found:
            with pytest.raises(AssertionError) as exc:
                verify_case_closure_recorded(
                    self._client(ledger), _CASE, [_FINDER, _OWNER, _VENDOR]
                )
        message = str(exc.value)
        assert "logIndex=8 'add_note_to_case'" in message
        assert f"no 'close_case' entry for {_VENDOR!r}" in message


# ---------------------------------------------------------------------------
# CM-23-004: each leaver's replica ends at its own closure
# ---------------------------------------------------------------------------


class TestOwnClosureTailIndex:
    @pytest.mark.spec("CM-23-004")
    def test_tail_is_the_leavers_last_closure_step(self):
        ledger = _owner_last_ledger()
        assert own_closure_tail_index(ledger, _FINDER) == 3
        # The owner stops at its own step; the CASE_MANAGER's step and
        # case_fully_closed come after it.
        assert own_closure_tail_index(ledger, _OWNER) == 5

    def test_status_entries_before_the_leave_do_not_count(self):
        """An earlier status entry is not part of the closure."""
        ledger = [
            _status(0, _FINDER, "ACCEPTED"),
            _entry(1, "close_case", _OWNER),
        ]
        assert own_closure_tail_index(ledger, _FINDER) is None
        assert own_closure_tail_index(ledger, _OWNER) == 1

    def test_order_is_read_from_log_index(self):
        assert own_closure_tail_index(_owner_last_ledger()[::-1], _FINDER) == 3


class TestVerifyOwnClosure:
    def test_waits_for_the_prefix_then_its_own_rm_closed(self):
        leaver = _leaver(_FINDER)
        with (
            patch.object(closure, "wait_for_replica_ledger_ending_at") as ends,
            patch.object(closure, "wait_for_participant_rm_state") as rm,
        ):
            closure._verify_own_closure(leaver, _case(), _owner_last_ledger())
        ends.assert_called_once_with(leaver.client, _CASE, 3)
        rm.assert_called_once_with(
            client=leaver.client,
            case_id=_CASE,
            actor_id=_FINDER,
            expected_states={RM.CLOSED},
        )

    def test_a_leave_the_ledger_lacks_is_reported(self):
        with pytest.raises(AssertionError, match="no close_case entry"):
            closure._verify_own_closure(
                _leaver(_VENDOR), _case(), _owner_last_ledger()
            )


class TestWaitForReplicaLedgerEndingAt:
    def _client(self, indices: list[int]) -> MagicMock:
        client = MagicMock()
        client.actor_id = _FINDER
        client.get.return_value = {
            str(i): {"case_id": _CASE, "log_index": i} for i in indices
        }
        return client

    @pytest.mark.spec("CM-23-004")
    def test_passes_when_the_replica_ends_at_its_closure(self):
        wait_for_replica_ledger_ending_at(self._client([0, 1, 2, 3]), _CASE, 3)

    @pytest.mark.spec("CM-23-004")
    def test_an_entry_after_the_closure_is_reported(self):
        with pytest.raises(AssertionError, match=r"holds entries \[4\]"):
            wait_for_replica_ledger_ending_at(
                self._client([0, 1, 2, 3, 4]), _CASE, 3
            )

    def test_a_gap_times_out(self):
        with pytest.raises(AssertionError):
            wait_for_replica_ledger_ending_at(
                self._client([0, 2, 3]), _CASE, 3, timeout_seconds=0.05
            )


class TestCaseManagerReader:
    """The closure checks read through the authority, bound to the CaseActor."""

    def test_binds_the_case_actor_store_onto_the_authority_client(self):
        authority = DataLayerClient(
            base_url="http://case-actor:7999/api/v2", actor_id=_FINDER
        )
        with patch.object(
            closure,
            "case_manager_store",
            return_value=(authority, _MANAGER),
        ) as store:
            reader = closure._case_manager_reader(authority, _CASE)
        store.assert_called_once_with(authority, _CASE)
        assert reader.base_url == authority.base_url
        assert reader.actor_id == _MANAGER
        assert (
            authority.actor_id == _FINDER
        )  # the caller's client is unchanged

    @pytest.mark.spec("CM-23-004", "DEMOMA-06-004")
    def test_a_client_bound_to_the_case_actor_is_read_as_is(self):
        dedicated = DataLayerClient(
            base_url="http://case-actor:7999/api/v2", actor_id=_MANAGER
        )
        with patch.object(
            closure, "case_manager_store", return_value=(dedicated, None)
        ):
            assert closure._case_manager_reader(dedicated, _CASE) is dedicated


class TestVerifyCaseClosed:
    def _run(self, rm_by_actor: dict[str, str]) -> None:
        index = {actor: f"{actor}/participant" for actor in rm_by_actor}
        client = MagicMock()
        client.get.return_value = {
            "id": _CASE,
            "type": "VulnerabilityCase",
            "attributedTo": _OWNER,
            "actorParticipantIndex": index,
        }
        records = {
            index[actor]: {
                "id": index[actor],
                "type": "CaseParticipant",
                "attributedTo": actor,
                "context": _CASE,
                "joined": True,
                "participantStatuses": [
                    {
                        "type": "ParticipantStatus",
                        "attributedTo": actor,
                        "context": _CASE,
                        "rmState": rm,
                    }
                ],
            }
            for actor, rm in rm_by_actor.items()
        }
        with (
            patch.object(milestones, "wait_for_all_participants_rm_closed"),
            patch.object(
                milestones,
                "_fetch_participant_data",
                side_effect=lambda _c, p_id: records[p_id],
            ),
        ):
            milestones.verify_case_closed(
                case_manager_client=client, case_id=_CASE
            )

    @pytest.mark.spec("CM-23-004")
    def test_passes_when_every_record_is_closed(self):
        self._run({_OWNER: "CLOSED", _FINDER: "CLOSED", _MANAGER: "CLOSED"})

    @pytest.mark.spec("CM-23-004")
    def test_names_every_open_participant(self):
        with pytest.raises(AssertionError) as exc:
            self._run(
                {_OWNER: "CLOSED", _FINDER: "ACCEPTED", _MANAGER: "ACCEPTED"}
            )
        assert _FINDER in str(exc.value)
        assert _MANAGER in str(exc.value)
        assert _OWNER not in str(exc.value)


# ---------------------------------------------------------------------------
# wait_for_owner_replica_embargo_state
# ---------------------------------------------------------------------------


class TestWaitForOwnerReplicaEmbargoState:
    @pytest.mark.spec("TRIG-13-003")
    @pytest.mark.parametrize("canonical", [EM.EXITED, EM.NONE])
    def test_waits_on_the_owner_store_for_the_canonical_em(self, canonical):
        """The owner's own store is polled for the CASE_MANAGER's EM state."""
        case = as_VulnerabilityCase(id_=_CASE, name="Case")
        if canonical == EM.EXITED:
            activate(case, f"{_CASE}/embargo_events/e1")
            terminate(case)
        manager = MagicMock()
        manager.get.return_value = case.model_dump(mode="json", by_alias=True)
        owner = _leaver(_OWNER)
        authority = MagicMock()
        with (
            patch.object(
                closure, "_case_manager_reader", return_value=manager
            ) as resolve,
            patch.object(closure, "wait_for_case_em_state") as wait,
        ):
            closure.wait_for_owner_replica_embargo_state(
                authority_client=authority, owner=owner, case_id=_CASE
            )
        resolve.assert_called_once_with(authority, _CASE)
        manager.get.assert_called_once_with(manager.dl_path(_CASE))
        wait.assert_called_once_with(
            owner.client,
            _CASE,
            canonical,
            closure.LEDGER_COVERAGE_TIMEOUT,
            dl_actor_id=_OWNER,
        )
