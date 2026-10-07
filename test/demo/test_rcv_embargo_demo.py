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

"""Unit tests for the RCV embargo demo scenario (#2071, DEMOMA-20).

The scenario drives four containers, so these tests pin its shape instead of a
running stack: the registration, the phase order, and the EM state each phase
asserts before the next begins.
"""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.scenario.rcv_embargo_demo as demo
from vultron.core.states.em import EM
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils import _demo_failures, reset_demo_failures

CASE_ID = "http://case-actor:7999/api/v2/VulnerabilityCases/abc"


@pytest.fixture(autouse=True)
def _clean_failures():
    reset_demo_failures()
    yield
    reset_demo_failures()


def _session(name: str) -> MagicMock:
    session = MagicMock()
    session.actor.id_ = f"http://{name}:7999/api/v2/actors/{name}"
    session.client.base_url = f"http://{name}:7999/api/v2"
    return session


@pytest.fixture
def cast() -> demo._Cast:
    return demo._Cast(
        reporter=_session("reporter"),
        coordinator=_session("coordinator"),
        vendor=_session("vendor"),
    )


@pytest.fixture
def case() -> MagicMock:
    case = MagicMock()
    case.id_ = CASE_ID
    return case


@pytest.fixture
def em_waits():
    """Stub the EM poll; the mock records ``(expected, active_embargo_id)``."""
    with (
        patch.object(demo, "wait_for_case_em_state") as wait,
        patch.object(
            demo, "resolve_case_actor_store_id", return_value="urn:manager"
        ),
    ):
        yield wait


def _states_asserted(wait: MagicMock) -> list[EM]:
    return [c.args[2] for c in wait.call_args_list]


@contextlib.contextmanager
def _stub_harness(_demo_name: str):
    yield MagicMock()


class TestRegistration:
    @pytest.mark.spec("DEMOMA-20-004")
    def test_registered_as_rcv_embargo_in_the_pr_set(self):
        registered = {s.name: s for s in discover_scenarios()}
        assert "rcv-embargo" in registered
        assert registered["rcv-embargo"].in_pr_set is True

    @pytest.mark.spec("DEMOMA-20-005")
    def test_roles_follow_the_scenario_role_naming(self):
        assert [r.name for r in demo.ROLES] == [
            "reporter",
            "coordinator",
            "vendor",
            "case-actor",
        ]

    @pytest.mark.spec("DEMOMA-20-001")
    def test_module_lives_at_the_specified_path(self):
        assert demo.__file__.endswith(
            "vultron/demo/scenario/rcv_embargo_demo.py"
        )


class TestPhaseOrder:
    @staticmethod
    def _run(cast, case, revised_embargo_id):
        """Run the scenario with stubbed phases; return the phases that ran."""
        order: list[str] = []

        def phase(name: str, result=None):
            def _run(*_a, **_kw):
                order.append(name)
                return result

            return _run

        with (
            # The real harness writes a dump manifest under devlogs/ on exit,
            # which the invariant harness would then read as an aborted run.
            patch.object(demo, "scenario_harness", _stub_harness),
            patch.object(
                demo,
                "_phase_report_submission",
                side_effect=phase("report_submission", (cast, case)),
            ),
            patch.object(
                demo,
                "_phase_embargo_proposal",
                side_effect=phase("embargo_proposal", revised_embargo_id),
            ),
            patch.object(
                demo,
                "_phase_fix_lifecycle",
                side_effect=phase("fix_lifecycle"),
            ),
            patch.object(
                demo,
                "_phase_embargo_termination",
                side_effect=phase("embargo_termination"),
            ),
            patch.object(
                demo,
                "_phase_publication",
                side_effect=phase("publication"),
            ),
            patch.object(
                demo,
                "_phase_case_closure",
                side_effect=phase("case_closure"),
            ),
        ):
            demo.run_rcv_embargo_demo(
                reporter_client=MagicMock(),
                coordinator_client=MagicMock(),
                vendor_client=MagicMock(),
            )

        return order

    @pytest.mark.spec("DEMOMA-20-007")
    def test_phases_run_in_the_specified_order(self, cast, case):
        order = self._run(cast, case, "urn:test:embargo:revised")
        assert order == [
            "report_submission",
            "embargo_proposal",
            "fix_lifecycle",
            "embargo_termination",
            "publication",
            "case_closure",
        ]

    @pytest.mark.spec("DEMOMA-20-007")
    def test_a_failed_proposal_skips_termination_publication_and_closure(
        self, cast, case
    ):
        """No revised embargo: phases 4-6 are skipped, the failure is recorded."""
        order = self._run(cast, case, None)
        assert order == [
            "report_submission",
            "embargo_proposal",
            "fix_lifecycle",
        ]
        assert _demo_failures


class TestEmStateAfterEachPhase:
    """DEMOMA-20-008: each phase asserts EM before the next starts."""

    @pytest.mark.spec("DEMOMA-20-008")
    def test_proposal_phase_asserts_the_revision_is_active(
        self, cast, case, em_waits
    ):
        canonical = [
            MagicMock(active_embargo_id="urn:embargo:default"),
            MagicMock(active_embargo_id="urn:embargo:revised"),
        ]
        with (
            patch.object(demo, "_canonical_case", side_effect=canonical),
            patch.object(demo, "demo_propose_and_activate_embargo") as helper,
        ):
            revised = demo._phase_embargo_proposal(cast, case)

        helper.assert_called_once_with(
            cast.reporter, cast.coordinator, cast.vendor, case
        )
        assert revised == "urn:embargo:revised"
        assert _states_asserted(em_waits) == [EM.ACTIVE]
        assert (
            em_waits.call_args.kwargs["active_embargo_id"]
            == "urn:embargo:revised"
        )
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-20-008")
    def test_unchanged_embargo_is_recorded_as_a_failure(
        self, cast, case, em_waits
    ):
        """A proposal that never took effect must not pass as a revision."""
        same = MagicMock(active_embargo_id="urn:embargo:default")
        with (
            patch.object(demo, "_canonical_case", return_value=same),
            patch.object(demo, "demo_propose_and_activate_embargo"),
        ):
            demo._phase_embargo_proposal(cast, case)

        assert _demo_failures

    @pytest.mark.spec("DEMOMA-20-008")
    def test_fix_lifecycle_leaves_the_embargo_active(
        self, cast, case, em_waits
    ):
        with patch.object(demo, "vendor_reports_fix_ready") as fix_ready:
            demo._phase_fix_lifecycle(cast, case)
        fix_ready.assert_called_once()
        assert _states_asserted(em_waits) == [EM.ACTIVE]

    @pytest.mark.spec("DEMOMA-20-003")
    @pytest.mark.spec("DEMOMA-20-008")
    def test_termination_asserts_exited_on_canonical_and_replicas(
        self, cast, case, em_waits
    ):
        with (
            patch.object(demo, "demo_terminate_embargo") as terminate,
            patch.object(demo, "wait_for_case_em_terminated") as replica_wait,
        ):
            demo._phase_embargo_termination(cast, case)

        terminate.assert_called_once_with(cast.coordinator, case)
        assert _states_asserted(em_waits) == [EM.EXITED]
        read_through = [
            c.kwargs["client"] for c in replica_wait.call_args_list
        ]
        assert read_through == [cast.reporter.client, cast.vendor.client]

    @pytest.mark.spec("DEMOMA-20-008")
    def test_publication_keeps_the_embargo_exited(self, cast, case, em_waits):
        with patch.object(demo, "everyone_reports_published") as published:
            demo._phase_publication(cast, case)
        published.assert_called_once()
        assert _states_asserted(em_waits) == [EM.EXITED]

    @pytest.mark.spec("DEMOMA-20-008")
    def test_closure_keeps_the_embargo_exited(self, cast, case, em_waits):
        with patch.object(demo, "everyone_closes_case") as closed:
            demo._phase_case_closure(cast, case)
        closed.assert_called_once()
        assert _states_asserted(em_waits) == [EM.EXITED]

    @pytest.mark.spec("DEMOMA-20-008")
    def test_a_missed_em_state_is_recorded_not_raised(
        self, cast, case, em_waits
    ):
        """A failed EM assertion lands in the accumulator, not as a raise."""
        em_waits.side_effect = AssertionError("timed out")
        demo._assert_em_state(cast, case, EM.ACTIVE, "phase")
        assert _demo_failures
