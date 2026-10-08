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

"""Unit tests for the RCVV embargo demo scenario (#2072, DEMOMA-21).

The scenario drives five containers, so these tests pin its shape instead of a
running stack: the registration, the phase order, the EM state each of phases
2, 3, 4 and 6 asserts, and the two rules that make the scenario what it is —
Vendor2 joins only after the revision, and the collapse is never a deliberate
termination.
"""

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.helpers.embargo_phases as phases
import vultron.demo.scenario.rcvv_embargo_demo as demo
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
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
    # ``quiet()`` returns the session itself so ``.quiet().notify_published()``
    # lands on the same mock.
    session.quiet.return_value = session
    return session


@pytest.fixture
def cast() -> demo._Cast:
    return demo._Cast(
        reporter=_session("reporter"),
        coordinator=_session("coordinator"),
        vendor=_session("vendor"),
        vendor2=_session("vendor2"),
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
        patch.object(phases, "wait_for_case_em_state") as wait,
        patch.object(
            phases, "resolve_case_actor_store_id", return_value="urn:manager"
        ),
    ):
        yield wait


def _states_asserted(wait: MagicMock) -> list[EM]:
    return [c.args[2] for c in wait.call_args_list]


@contextlib.contextmanager
def _stub_harness(_demo_name: str):
    yield MagicMock()


class TestRegistration:
    @pytest.mark.spec("DEMOMA-21-005")
    def test_registered_as_rcvv_embargo_in_the_pr_set(self):
        registered = {s.name: s for s in discover_scenarios()}
        assert "rcvv-embargo" in registered
        assert registered["rcvv-embargo"].in_pr_set is True

    @pytest.mark.spec("DEMOMA-21-006")
    def test_roles_follow_the_scenario_role_naming(self):
        assert [r.name for r in demo.ROLES] == [
            "reporter",
            "coordinator",
            "vendor",
            "vendor2",
            "case-actor",
        ]

    @pytest.mark.spec("DEMOMA-21-001")
    def test_module_lives_at_the_specified_path(self):
        assert demo.__file__.endswith(
            "vultron/demo/scenario/rcvv_embargo_demo.py"
        )


class TestPhaseOrder:
    @staticmethod
    def _run(cast, case, proposed, revised, v2_error=None):
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
                side_effect=phase(
                    "report_submission", (cast, case, MagicMock())
                ),
            ),
            patch.object(
                demo,
                "_phase_embargo_proposal",
                side_effect=phase("embargo_proposal", proposed),
            ),
            patch.object(
                demo,
                "_phase_embargo_revision",
                side_effect=phase("embargo_revision", revised),
            ),
            patch.object(
                demo,
                "_phase_v2_late_invite",
                side_effect=v2_error or phase("v2_late_invite"),
            ),
            patch.object(
                demo,
                "_phase_fix_lifecycle",
                side_effect=phase("fix_lifecycle"),
            ),
            patch.object(
                demo,
                "_phase_accidental_collapse",
                side_effect=phase("accidental_collapse"),
            ),
            patch.object(
                demo,
                "_phase_case_closure",
                side_effect=phase("case_closure"),
            ),
        ):
            demo.run_rcvv_embargo_demo(
                reporter_client=MagicMock(),
                coordinator_client=MagicMock(),
                vendor_client=MagicMock(),
                vendor2_client=MagicMock(),
            )

        return order

    @pytest.mark.spec("DEMOMA-21-008")
    def test_phases_run_in_the_specified_order(self, cast, case):
        order = self._run(cast, case, "urn:embargo:1", "urn:embargo:2")
        assert order == [
            "report_submission",
            "embargo_proposal",
            "embargo_revision",
            "v2_late_invite",
            "fix_lifecycle",
            "accidental_collapse",
            "case_closure",
        ]

    @pytest.mark.spec("DEMOMA-21-008")
    def test_a_failed_proposal_skips_every_later_phase(self, cast, case):
        order = self._run(cast, case, None, None)
        assert order == ["report_submission", "embargo_proposal"]
        assert _demo_failures

    @pytest.mark.spec("DEMOMA-21-012")
    def test_a_vendor2_that_does_not_sign_skips_the_later_phases(
        self, cast, case
    ):
        """Fix lifecycle, collapse and closure presuppose a signatory Vendor2."""
        order = self._run(
            cast,
            case,
            "urn:embargo:1",
            "urn:embargo:2",
            v2_error=AssertionError("timed out"),
        )
        assert order == [
            "report_submission",
            "embargo_proposal",
            "embargo_revision",
        ]
        assert _demo_failures

    @pytest.mark.spec("DEMOMA-21-003")
    def test_a_failed_revision_keeps_vendor2_out(self, cast, case):
        """Vendor2 is invited only after the revision is confirmed active."""
        order = self._run(cast, case, "urn:embargo:1", None)
        assert order == [
            "report_submission",
            "embargo_proposal",
            "embargo_revision",
        ]
        assert _demo_failures


class TestEmStateAfterEachPhase:
    """DEMOMA-21-009: phases 2, 3, 4 and 6 assert EM before the next starts."""

    @pytest.mark.spec("DEMOMA-21-009")
    def test_proposal_phase_asserts_the_revision_is_active(
        self, cast, case, em_waits
    ):
        canonical = [
            MagicMock(active_embargo_id="urn:embargo:default"),
            MagicMock(active_embargo_id="urn:embargo:one"),
        ]
        with (
            patch.object(phases, "canonical_case", side_effect=canonical),
            patch.object(phases, "demo_propose_and_activate_embargo"),
        ):
            proposed = demo._phase_embargo_proposal(cast, case)

        assert proposed == "urn:embargo:one"
        assert _states_asserted(em_waits) == [EM.ACTIVE]
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-21-002")
    @pytest.mark.spec("DEMOMA-21-009")
    def test_revision_phase_runs_the_helper_and_asserts_the_new_embargo(
        self, cast, case, em_waits
    ):
        with (
            patch.object(
                phases,
                "canonical_case",
                return_value=MagicMock(active_embargo_id="urn:embargo:two"),
            ),
            patch.object(demo, "demo_propose_embargo_revision") as helper,
        ):
            revised = demo._phase_embargo_revision(
                cast, case, "urn:embargo:one"
            )

        helper.assert_called_once_with(
            proposing=cast.vendor,
            accepting=cast.reporter,
            owner=cast.coordinator,
            case=case,
        )
        assert revised == "urn:embargo:two"
        assert _states_asserted(em_waits) == [EM.ACTIVE]
        assert (
            em_waits.call_args.kwargs["active_embargo_id"] == "urn:embargo:two"
        )
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-21-009")
    def test_an_unrevised_embargo_is_recorded_as_a_failure(
        self, cast, case, em_waits
    ):
        """A revision that never took effect must not pass as one."""
        with (
            patch.object(
                phases,
                "canonical_case",
                return_value=MagicMock(active_embargo_id="urn:embargo:one"),
            ),
            patch.object(demo, "demo_propose_embargo_revision"),
        ):
            revised = demo._phase_embargo_revision(
                cast, case, "urn:embargo:one"
            )

        assert revised is None
        assert _demo_failures

    @pytest.mark.spec("DEMOMA-21-003")
    @pytest.mark.spec("DEMOMA-21-009")
    @pytest.mark.spec("DEMOMA-21-012")
    def test_late_invite_asserts_active_and_vendor2_signatory(
        self, cast, case, em_waits
    ):
        opened = MagicMock()
        with (
            patch.object(demo, "vendor_joins_coordinated_case") as joins,
            patch.object(
                demo, "wait_for_participant_embargo_consent"
            ) as consent,
            patch.object(demo, "wait_for_case_em_state") as replica_wait,
            patch.object(
                demo, "resolve_case_actor_store_id", return_value="urn:mgr"
            ),
        ):
            demo._phase_v2_late_invite(cast, case, opened, "urn:embargo:two")

        kwargs = joins.call_args.kwargs
        assert kwargs["vendor"] is cast.vendor2.actor
        assert kwargs["vendor_client"] is cast.vendor2.client
        assert kwargs["already_seated"] == [cast.vendor.actor]
        assert _states_asserted(em_waits) == [EM.ACTIVE]
        args = consent.call_args.args
        assert args[2] == cast.vendor2.actor.id_
        assert args[3] == "urn:embargo:two"
        assert args[4] is EmbargoConsentState.ACCEPTED
        assert replica_wait.call_args.args[0] is cast.vendor2.client
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-21-012")
    def test_a_vendor2_that_never_signs_fails_the_late_invite_phase(
        self, cast, case, em_waits
    ):
        with (
            patch.object(demo, "vendor_joins_coordinated_case"),
            patch.object(
                demo,
                "wait_for_participant_embargo_consent",
                side_effect=AssertionError("timed out"),
            ),
            patch.object(demo, "wait_for_case_em_state"),
            patch.object(
                demo, "resolve_case_actor_store_id", return_value="urn:mgr"
            ),
        ):
            with pytest.raises(AssertionError, match="timed out"):
                demo._phase_v2_late_invite(
                    cast, case, MagicMock(), "urn:embargo:two"
                )

    @pytest.mark.spec("DEMOMA-21-008")
    def test_fix_lifecycle_runs_for_both_vendors_and_keeps_em_active(
        self, cast, case, em_waits
    ):
        with patch.object(demo, "vendor_reports_fix_ready") as fix_ready:
            demo._phase_fix_lifecycle(cast, case)

        assert [
            c.kwargs["vendor_client"] for c in fix_ready.call_args_list
        ] == [cast.vendor.client, cast.vendor2.client]
        assert _states_asserted(em_waits) == [EM.ACTIVE]

    @pytest.mark.spec("DEMOMA-21-004")
    @pytest.mark.spec("DEMOMA-21-009")
    @pytest.mark.spec("DEMOMA-21-014")
    def test_collapse_is_caused_by_the_reporters_publication(
        self, cast, case, em_waits
    ):
        with (
            patch.object(demo, "wait_for_event_type_in_ledger") as ledger,
            patch.object(demo, "wait_for_case_em_terminated") as replica_wait,
            patch.object(
                demo, "resolve_case_actor_store_id", return_value="urn:mgr"
            ),
        ):
            demo._phase_accidental_collapse(cast, case)

        cast.reporter.notify_published.assert_called_once_with()
        # Nobody terminates the embargo: the collapse is CS.P's consequence.
        for session in (
            cast.reporter,
            cast.coordinator,
            cast.vendor,
            cast.vendor2,
        ):
            session.terminate_embargo.assert_not_called()
        assert ledger.call_args.kwargs["event_type"] == (
            "remove_embargo_event_from_case"
        )
        assert _states_asserted(em_waits) == [EM.EXITED]
        read_through = [
            c.kwargs["client"] for c in replica_wait.call_args_list
        ]
        assert read_through == [
            cast.coordinator.client,
            cast.reporter.client,
            cast.vendor.client,
            cast.vendor2.client,
        ]
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-21-014")
    def test_the_scenario_never_calls_the_terminate_trigger(self):
        """The module contains no deliberate termination at all."""
        source = Path(demo.__file__).read_text(encoding="utf-8")
        assert "terminate_embargo(" not in source

    @pytest.mark.spec("DEMOMA-21-008")
    def test_closure_closes_vendor2_too_and_keeps_the_embargo_exited(
        self, cast, case, em_waits
    ):
        with patch.object(demo, "everyone_closes_case") as closed:
            demo._phase_case_closure(cast, case)

        later = closed.call_args.kwargs["later_vendors"]
        assert later == [("Vendor2", cast.vendor2.client, cast.vendor2.actor)]
        assert _states_asserted(em_waits) == [EM.EXITED]
