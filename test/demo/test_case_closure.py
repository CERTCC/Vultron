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
real ``demo_gate`` (``vultron/demo/AGENTS.md`` § causal gating, rule 8), and
the ledger half of the closure milestone,
:func:`vultron.demo.helpers.milestones.case_closure_violations` and
:func:`~vultron.demo.helpers.milestones.verify_case_closure_recorded`.
"""

from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.utils as demo_utils
from vultron.core.states.rm import RM
from vultron.demo.helpers import closure, milestones
from vultron.demo.helpers.closure import CaseLeaver, close_case_owner_last
from vultron.demo.helpers.milestones import (
    case_closure_violations,
    verify_case_closure_recorded,
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
        self, others, owner, wait_side_effect=None, ledger_side_effect=None
    ):
        sent: list[str] = []
        session_cls = MagicMock(
            side_effect=lambda client, actor: (
                sent.append(actor.id_) or MagicMock()
            )
        )
        authority = MagicMock()
        with (
            patch.object(closure, "ActorSession", session_cls),
            patch.object(
                closure,
                "resolve_case_actor_store_id",
                return_value=_MANAGER,
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
        ):
            departed = close_case_owner_last(
                case=_case(),
                authority_client=authority,
                others=others,
                owner=owner,
                milestone="M7",
            )
        self.recorded = recorded
        return sent, departed, wait, resolve, authority

    @pytest.mark.spec("CM-23-015")
    def test_owner_leaves_after_every_other_participant(self):
        sent, departed, _, _, _ = self._run(
            [_leaver(_FINDER), _leaver(_VENDOR)], _leaver(_OWNER)
        )
        assert sent == [_FINDER, _VENDOR, _OWNER]
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
                "client": authority,
                "case_id": _CASE,
                "actor_id": actor_id,
                "expected_states": {RM.CLOSED},
                "dl_actor_id": _MANAGER,
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
        (failure,) = demo_utils._demo_failures
        assert failure.startswith("GATE FAILED")
        assert "CM-23-015" in failure

    @pytest.mark.spec("CM-23-015")
    def test_ledger_check_runs_after_the_owner_leaves(self):
        _, departed, _, _, authority = self._run(
            [_leaver(_FINDER)], _leaver(_OWNER)
        )
        self.recorded.assert_called_once_with(
            client=authority, case_id=_CASE, departed_actor_ids=departed
        )

    def test_ledger_check_failure_is_recorded_under_the_milestone(self):
        """A ledger-order failure is a check, not a gate: it is recorded once."""
        sent, _, _, _, _ = self._run(
            [_leaver(_FINDER)],
            _leaver(_OWNER),
            ledger_side_effect=AssertionError("finder left after closure"),
        )
        assert sent == [_FINDER, _OWNER]
        (failure,) = demo_utils._demo_failures
        assert not failure.startswith("GATE FAILED")
        assert (
            "M7: every departure recorded before case_fully_closed" in failure
        )

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
    """The FV closure tail: Finder leaves, then the owner closes the case."""
    return [
        _status(0, _FINDER, "ACCEPTED"),
        _status(1, _OWNER, "ACCEPTED"),
        _entry(2, "close_case", _FINDER),
        _entry(3, "close_case", _OWNER),
        _status(4, _MANAGER, "CLOSED"),
        _entry(5, "case_fully_closed", _OWNER),
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
            _status(2, _MANAGER, "CLOSED"),
            _entry(3, "case_fully_closed", _OWNER),
            _entry(4, "close_case", _FINDER),
        ]
        violations = case_closure_violations(
            ledger, [_FINDER, _OWNER], _MANAGER
        )
        assert len(violations) == 2
        assert f"no 'close_case' entry for {_FINDER!r}" in violations[0]
        assert "logIndex=4 'close_case'" in violations[1]

    def test_manager_housekeeping_after_boundary_is_allowed(self):
        """case_fully_closed is a write boundary, not the last entry (CM-23-002)."""
        ledger = [*_owner_last_ledger(), _status(6, _MANAGER, "CLOSED")]
        assert (
            case_closure_violations(ledger, [_FINDER, _OWNER], _MANAGER) == []
        )

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
        ledger = [e for e in _owner_last_ledger() if e["log_index"] < 5]
        ledger += [
            _entry(5 + i, "case_fully_closed", _OWNER) for i in range(count)
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
                "resolve_case_actor_store_id",
                return_value=_MANAGER,
            ),
            patch.object(
                milestones,
                "find_case_actor_participant_id",
                return_value=_MANAGER,
            ),
        )

    @pytest.mark.spec("CM-23-015")
    def test_reads_the_case_managers_store_after_the_boundary(self):
        client = self._client(_owner_last_ledger())
        waited, resolved, found = self._patches()
        with waited as wait, resolved, found:
            verify_case_closure_recorded(client, _CASE, [_FINDER, _OWNER])
        wait.assert_called_once_with(
            client=client, case_id=_CASE, event_type="case_fully_closed"
        )
        client.dl_path.assert_called_once_with(
            "CaseLedgerEntrys/", actor_id=_MANAGER
        )

    def test_raises_with_every_violation(self):
        ledger = [
            *_owner_last_ledger(),
            _entry(6, "add_note_to_case", _VENDOR),
        ]
        waited, resolved, found = self._patches()
        with waited, resolved, found:
            with pytest.raises(AssertionError) as exc:
                verify_case_closure_recorded(
                    self._client(ledger), _CASE, [_FINDER, _OWNER, _VENDOR]
                )
        message = str(exc.value)
        assert "logIndex=6 'add_note_to_case'" in message
        assert f"no 'close_case' entry for {_VENDOR!r}" in message
