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

"""A vendor beyond the first threads through the coordinated-case helpers.

``rcvv-embargo`` (DEMOMA-21) is the first scenario to seat a second vendor
through ``helpers/coordinated_case.py``; these tests pin that the second vendor
is invited, closed, covered and dumped like the first.
"""

from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.helpers.coordinated_case as cc
from test.demo._helpers import stub_closure_gate
from vultron.demo.helpers import closure
from vultron.demo.utils import _demo_failures, reset_demo_failures


@pytest.fixture(autouse=True)
def _clean_failures():
    reset_demo_failures()
    yield
    reset_demo_failures()


def _actor(name: str) -> MagicMock:
    actor = MagicMock()
    actor.id_ = f"http://{name}:7999/api/v2/actors/{name}"
    return actor


def _client(name: str) -> MagicMock:
    client = MagicMock()
    client.base_url = f"http://{name}:7999/api/v2"
    return client


@pytest.fixture
def case() -> MagicMock:
    case = MagicMock()
    case.id_ = "http://case-actor:7999/api/v2/VulnerabilityCases/abc"
    return case


class TestVendorJoins:
    @pytest.mark.spec("DEMOMA-21-003")
    def test_a_later_vendor_is_named_and_the_gate_expects_the_earlier_one(
        self, case
    ):
        opened = MagicMock(case=case)
        opened.coordinator_in_coordinator = _actor("coordinator")
        reporter, vendor, vendor2 = (
            _actor("reporter"),
            _actor("vendor"),
            _actor("vendor2"),
        )
        with (
            patch.object(cc, "get_actor_by_id", return_value=vendor2),
            patch.object(cc, "run_case_invite_chain") as chain,
            patch.object(cc, "wait_for_case_participants") as participants,
            patch.object(cc, "wait_for_case_on_container"),
            patch.object(cc, "run_invite_path_rm_triage"),
        ):
            cc.vendor_joins_coordinated_case(
                opened=opened,
                reporter=reporter,
                reporter_client=_client("reporter"),
                coordinator_client=_client("coordinator"),
                vendor=vendor2,
                vendor_client=_client("vendor2"),
                vendor_name="Vendor2",
                already_seated=[vendor],
            )

        assert chain.call_args.kwargs["invitee_name"] == "Vendor2"
        assert participants.call_args.kwargs["expected_actor_ids"] == {
            reporter.id_,
            opened.coordinator_in_coordinator.id_,
            vendor2.id_,
            vendor.id_,
        }
        assert not _demo_failures


class TestEveryoneClosesCase:
    @pytest.mark.spec("DEMOMA-21-008")
    def test_later_vendors_close_and_are_covered(self, case):
        reporter_client = _client("reporter")
        vendor2_client = _client("vendor2")
        vendor2 = _actor("vendor2")
        with (
            patch.object(closure, "ActorSession") as session_cls,
            patch.object(cc, "wait_for_all_participants_rm_closed"),
            stub_closure_gate(),
            patch.object(cc, "verify_case_closed"),
            patch.object(cc, "wait_for_event_type_in_ledger"),
            patch.object(cc, "wait_for_replica_ledger_coverage") as coverage,
        ):
            cc.everyone_closes_case(
                reporter_client=reporter_client,
                coordinator_client=_client("coordinator"),
                vendor_client=_client("vendor"),
                reporter_in_reporter=_actor("reporter"),
                coordinator_in_coordinator=_actor("coordinator"),
                vendor_in_vendor=_actor("vendor"),
                case=case,
                later_vendors=[("Vendor2", vendor2_client, vendor2)],
            )

        closed_by = [c.kwargs["actor"].id_ for c in session_cls.call_args_list]
        assert vendor2.id_ in closed_by
        kwargs = coverage.call_args.kwargs
        assert (vendor2_client, "Vendor2") in kwargs["replicas"]
        assert vendor2_client in kwargs["late_joiners"]

    def test_no_later_vendors_changes_nothing(self, case):
        with (
            patch.object(closure, "ActorSession") as session_cls,
            patch.object(cc, "wait_for_all_participants_rm_closed"),
            stub_closure_gate(),
            patch.object(cc, "verify_case_closed"),
            patch.object(cc, "wait_for_event_type_in_ledger"),
            patch.object(cc, "wait_for_replica_ledger_coverage") as coverage,
        ):
            cc.everyone_closes_case(
                reporter_client=_client("reporter"),
                coordinator_client=_client("coordinator"),
                vendor_client=_client("vendor"),
                reporter_in_reporter=_actor("reporter"),
                coordinator_in_coordinator=_actor("coordinator"),
                vendor_in_vendor=_actor("vendor"),
                case=case,
            )

        assert session_cls.call_count == 3
        assert len(coverage.call_args.kwargs["replicas"]) == 2

    @pytest.mark.spec("CM-23-015")
    def test_coordinator_case_owner_leaves_last(self, case):
        """Every other participant leaves before the Coordinator (CM-23-015).

        The Coordinator owns the case in ``fcv``, ``rcv-embargo`` and
        ``rcvv-embargo``; a ``Leave`` sent after its owner close is not
        recorded (CM-23-013).  The owner's ``Leave`` waits on each earlier
        departure being ``RM.CLOSED`` in the CASE_MANAGER's store, and the
        ledger check is handed every departure in the order it was sent.
        """
        coordinator, vendor, reporter, vendor2 = (
            _actor("coordinator"),
            _actor("vendor"),
            _actor("reporter"),
            _actor("vendor2"),
        )
        with (
            patch.object(closure, "ActorSession") as session_cls,
            patch.object(cc, "wait_for_all_participants_rm_closed"),
            stub_closure_gate() as gate_wait,
            patch.object(closure, "verify_case_closure_recorded") as recorded,
            patch.object(cc, "verify_case_closed"),
            patch.object(cc, "wait_for_event_type_in_ledger"),
            patch.object(cc, "wait_for_replica_ledger_coverage"),
        ):
            cc.everyone_closes_case(
                reporter_client=_client("reporter"),
                coordinator_client=_client("coordinator"),
                vendor_client=_client("vendor"),
                reporter_in_reporter=reporter,
                coordinator_in_coordinator=coordinator,
                vendor_in_vendor=vendor,
                case=case,
                later_vendors=[("Vendor2", _client("vendor2"), vendor2)],
            )

        order = [vendor.id_, reporter.id_, vendor2.id_, coordinator.id_]
        closed_by = [c.kwargs["actor"].id_ for c in session_cls.call_args_list]
        assert closed_by == order
        waited_on = [c.kwargs["actor_id"] for c in gate_wait.call_args_list]
        assert waited_on == order[:-1]
        assert recorded.call_args.kwargs["departed_actor_ids"] == order


class TestDump:
    @pytest.mark.spec("DEMOMA-21-008")
    def test_later_vendors_are_dumped_under_their_own_name(self, case):
        vendor2_client = _client("vendor2")
        with (
            patch.object(cc, "dump_case_ledgers") as dump,
            patch.object(cc, "replica_route_key", side_effect=lambda c, n: n),
            patch.object(
                cc, "resolve_case_actor_route_key", return_value="urn:mgr"
            ),
        ):
            cc.dump_coordinated_case_ledgers(
                demo_name="rcvv-embargo",
                reporter_name="reporter",
                reporter_client=_client("reporter"),
                coordinator_client=_client("coordinator"),
                vendor_client=_client("vendor"),
                case=case,
                later_vendors=[("vendor2", vendor2_client)],
            )

        names = [t.actor_name for t in dump.call_args.kwargs["targets"]]
        assert names == [
            "reporter",
            "coordinator",
            "vendor",
            "vendor2",
            "case-actor",
        ]
