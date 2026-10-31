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

"""Story fragments of the Reporter → Coordinator → Vendor family (#5533).

``rcv`` and ``rcv-reject`` are assembled from
``vultron.demo.helpers.coordinated_story``, so the checks that used to sit on
each scenario's ``_phase_*`` functions sit on the shared fragments here: the
milestone calls, the causal gates, and the skip-on-failure behaviour of the
invite chain now that the Invite and the answer are two fragments with the
Vendor's branch point between them.

Every test patches the collaborators out, so no HTTP happens; ``demo_gate`` /
``demo_check`` / ``demo_step`` are left real wherever the test is about control
flow, and stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).
"""

import contextlib
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, call, patch

import pytest

from test.demo._helpers import (
    mock_actor,
    mock_case,
    mock_client,
    patch_chain_shared,
    story_state,
    stub_closure_gate,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import (
    coordinated_case,
    coordinated_story,
    invite_chain,
)
from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    role_map,
)
from vultron.demo.helpers.cast import (
    CASE_ACTOR,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
    coordinated_clients,
    coordinator_invites_vendor,
    everyone_closes,
    everyone_publishes,
    open_coordinated_cast,
    reporter_tells_coordinator,
    reporter_then_coordinator_close,
    vendor_accepts_and_joins,
    vendor_rejects_invite,
    vendor_reports_the_fix_ready,
)
from vultron.demo.utils import reset_demo_failures
from vultron.errors import DemoStoryError

_CAST = (REPORTER, COORDINATOR, VENDOR)


@contextlib.contextmanager
def _no_banners():
    """Make the fragments' own context managers pass-through.

    The tests that use it observe call parameters and ordering, not gate
    control flow.
    """
    with contextlib.ExitStack() as stack:
        for module in (coordinated_story, coordinated_case):
            for name in ("demo_gate", "demo_check", "demo_step"):
                stack.enter_context(
                    patch.object(
                        module,
                        name,
                        side_effect=lambda _: contextlib.nullcontext(),
                    )
                )
        yield


# ---------------------------------------------------------------------------
# The shared cast opening
# ---------------------------------------------------------------------------


class TestOpenCoordinatedCast:
    """One reset and one seeding for every scenario of the family."""

    def test_the_reset_covers_every_container(self):
        reporter_client = mock_client()
        coordinator_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        actors = [mock_actor(f"urn:test:{name}") for name in _CAST]

        with (
            patch.object(
                coordinated_story,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset_mock,
            patch(
                "vultron.demo.helpers.seeding.seed_case_actor_identity"
            ) as reseed,
            patch.object(
                coordinated_story,
                "seed_containers_rcv",
                return_value=tuple(actors),
            ),
            patch.object(
                coordinated_story,
                "get_actor_by_id",
                side_effect=list(actors),
            ),
        ):
            state = open_coordinated_cast(
                MagicMock(),
                reporter_client=reporter_client,
                coordinator_client=coordinator_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
            )

        reset_mock.assert_has_calls(
            [
                call(client=reporter_client),
                call(client=coordinator_client),
                call(client=vendor_client),
                call(client=case_actor_client),
            ]
        )
        # The dedicated case-actor identity is re-seeded after the wipe
        # (#1876 AC-2): every proposal is addressed to it.
        reseed.assert_called_once_with(case_actor_client)
        assert sorted(state.cast) == sorted(_CAST)
        assert state.client(REPORTER) is reporter_client
        assert state.case_actor_client is case_actor_client

    def test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with(self):
        """The failure is recorded by demo_step; the story stops here."""
        reset_demo_failures()
        with (
            patch.object(coordinated_story, "reset_datalayer"),
            patch("vultron.demo.helpers.seeding.seed_case_actor_identity"),
            patch.object(
                coordinated_story,
                "seed_containers_rcv",
                side_effect=RuntimeError("container unreachable"),
            ),
            pytest.raises(DemoStoryError, match="could not be seeded"),
        ):
            open_coordinated_cast(
                MagicMock(),
                reporter_client=mock_client(),
                coordinator_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )
        reset_demo_failures()


class TestCoordinatedClients:
    """One client set and one health check for the whole family."""

    def test_each_address_falls_back_to_its_cast_slot(self):
        roles = role_map(
            [
                ActorRole(REPORTER, REPORTER_SLOT, "Reporter", has_id=True),
                ActorRole(
                    COORDINATOR, COORDINATOR_SLOT, "Coordinator", has_id=True
                ),
                ActorRole(VENDOR, VENDOR_SLOT, "Vendor", has_id=True),
                case_actor_role(),
            ]
        )
        with patch.object(
            coordinated_story, "check_all_containers"
        ) as checked:
            clients = coordinated_clients(roles, skip_health_check=False)

        assert clients.reporter.base_url == REPORTER_SLOT.url
        assert clients.coordinator.base_url == COORDINATOR_SLOT.url
        assert clients.vendor.base_url == VENDOR_SLOT.url
        assert clients.case_actor.base_url == CASE_ACTOR.url
        # The case-actor client is bound to the CaseActor its container hosts,
        # so a read through it addresses the canonical store (ADR-0073).
        assert clients.case_actor.actor_id
        assert [label for label, _c in checked.call_args.args[0]] == [
            "Reporter",
            "Coordinator",
            "Vendor",
            "CaseActor",
        ]

    def test_an_override_wins_and_the_check_can_be_skipped(self):
        roles = role_map(
            [
                ActorRole(REPORTER, REPORTER_SLOT, "Reporter", has_id=True),
                ActorRole(
                    COORDINATOR, COORDINATOR_SLOT, "Coordinator", has_id=True
                ),
                ActorRole(VENDOR, VENDOR_SLOT, "Vendor", has_id=True),
                case_actor_role(),
            ]
        )
        with patch.object(
            coordinated_story, "check_all_containers"
        ) as checked:
            clients = coordinated_clients(
                roles,
                skip_health_check=True,
                vendor_url="http://elsewhere:7999/api/v2",
            )

        assert clients.vendor.base_url == "http://elsewhere:7999/api/v2"
        assert clients.reporter.base_url == REPORTER_SLOT.url
        checked.assert_not_called()


# ---------------------------------------------------------------------------
# Milestone assertions — AC-4 of ISSUE-1976, now on the fragments
# ---------------------------------------------------------------------------


class TestCoordinatedMilestones:
    """Each fragment calls the milestone helper its phase did."""

    @pytest.mark.spec("CM-12-001")
    @pytest.mark.spec("VP-02-015")
    def test_reporter_tells_coordinator_calls_verify_case_active(self):
        """M1 runs when the Coordinator engages the case."""
        state = story_state(*_CAST)
        case = mock_case()

        with (
            patch.object(
                coordinated_case,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
            ),
            patch.object(
                coordinated_case,
                "run_direct_path_rm_triage",
                return_value=case,
            ),
            patch.object(coordinated_case, "wait_for_case_participants"),
            patch.object(coordinated_case, "as_VulnerabilityCase") as mock_vc,
            patch.object(coordinated_case, "verify_case_active") as mock_m1,
            patch.object(
                coordinated_case,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = case
            reporter_tells_coordinator(state)

        mock_m1.assert_called_once()
        # The fragment hands the case to the state, which arms the dump as
        # soon as there is something to dump (DEMOMA-23-003).
        assert state.case is case
        cast(MagicMock, state.harness).dump_with.assert_called_once()

    def test_vendor_reports_the_fix_ready_calls_verify_fix_ready(self):
        """M5 runs when the Vendor reports fix ready."""
        state = story_state(*_CAST, case=mock_case())

        with (
            patch.object(coordinated_case, "wait_for_participant_rm_state"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(coordinated_case, "wait_for_participant_vf_state"),
            patch.object(coordinated_case, "verify_fix_ready") as mock_m5,
            patch.object(
                coordinated_case,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            vendor_reports_the_fix_ready(state)

        mock_m5.assert_called()

    def test_vendor_reports_the_fix_ready_gates_on_rm_accepted(self):
        """The RM wait precedes notify-fix-ready (ADR-0058/CSB-18-001)."""
        from vultron.core.states.rm import RM

        state = story_state(*_CAST, case=mock_case())
        call_order: list[str] = []
        rm_calls: list[dict] = []

        def _rm_wait(*_args, **kwargs):
            rm_calls.append(kwargs)
            call_order.append("rm_wait")

        with (
            patch.object(
                coordinated_case, "wait_for_participant_rm_state", _rm_wait
            ),
            patch.object(
                ActorSession,
                "notify_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(coordinated_case, "wait_for_participant_vf_state"),
            patch.object(coordinated_case, "verify_fix_ready"),
        ):
            vendor_reports_the_fix_ready(state)

        assert rm_calls, (
            "wait_for_participant_rm_state must be called (ADR-0058/CSB-18-001)"
        )
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} (CSB-18-001)"
        assert call_order.index("rm_wait") < call_order.index("fix_ready"), (
            "wait_for_participant_rm_state must precede notify_fix_ready"
            " (ADR-0058)"
        )

    def test_everyone_publishes_calls_verify_publicly_disclosed(self):
        """M6 runs when every participant has reported publication."""
        state = story_state(*_CAST, case=mock_case())

        with (
            patch.object(ActorSession, "notify_published"),
            patch.object(coordinated_case, "wait_for_case_em_terminated"),
            patch.object(coordinated_case, "wait_for_participant_vf_state"),
            patch.object(
                coordinated_case, "verify_publicly_disclosed"
            ) as mock_m6,
            patch.object(
                coordinated_case,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            everyone_publishes(state)

        mock_m6.assert_called()

    def test_everyone_closes_runs_the_closure_milestone(self):
        """The milestone lives in ``close_case_owner_last`` (CM-23-004)."""
        state = story_state(*_CAST, case=mock_case())

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(coordinated_case, "close_case_owner_last") as mock_m7,
            patch.object(
                coordinated_case,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            everyone_closes(state)

        mock_m7.assert_called_once()
        assert mock_m7.call_args.kwargs.get("milestone") == "M7"

    def test_reporter_then_coordinator_close_runs_its_own_milestone(self):
        """The two-party closure is the Case Owner leaving last (CM-23-015)."""
        state = story_state(*_CAST, case=mock_case())

        with patch.object(
            coordinated_story, "close_case_owner_last"
        ) as closure:
            reporter_then_coordinator_close(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M4"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(REPORTER)
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)


# ---------------------------------------------------------------------------
# Bug #2135 (CLP-08-005): the Reporter's replica before the Vendor's triage
# ---------------------------------------------------------------------------


@pytest.mark.spec("CLP-08-005")
class TestReporterCaseReplicaWaitBeforeVendorTriage:
    """The Vendor's acceptance broadcasts to every participant.

    The Vendor's reply to the full-case Invite broadcasts
    ``Announce(CaseLedgerEntry)`` to all participants including the Reporter.
    If the Reporter's DataLayer does not yet hold the ``VulnerabilityCase``
    (genesis hash unavailable), the chain bootstrap fails with CLP-08-005.
    """

    def test_reporter_wait_before_vendor_triage(self):
        state = story_state(*_CAST, case=mock_case())
        state.invited(VENDOR, "urn:test:invite")
        call_order: list[str] = []

        def _wait_for_case(client, case_id, **_kwargs):
            if client is state.client(REPORTER):
                call_order.append("reporter_wait")

        with (
            patch_chain_shared(
                coordinated_case,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            patch.object(
                coordinated_case,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: call_order.append("triage"),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_chain, "reply_to_full_case_invite"),
            patch.object(coordinated_case, "wait_for_case_participants"),
            _no_banners(),
        ):
            vendor_accepts_and_joins(state)

        assert "reporter_wait" in call_order, (
            "wait_for_case_on_container(reporter_client) was never called"
            " before Vendor triage"
        )
        assert "triage" in call_order, (
            "run_invite_path_rm_triage was never called"
        )
        assert call_order.index("reporter_wait") < call_order.index(
            "triage"
        ), (
            f"Reporter case-replica wait must come BEFORE "
            f"run_invite_path_rm_triage. Call order: {call_order} —"
            " Bug #2135 (CLP-08-005)"
        )


# ---------------------------------------------------------------------------
# The invite chain, split across two fragments, still skips its dependents
# ---------------------------------------------------------------------------


class TestInviteChainSkipsDependents:
    """A failed invite trigger or delivery lookup skips the answer.

    The composed form puts the Vendor's branch point between the Invite and
    the answer, so the two halves are two fragments: the first records no
    Invite on the state, and the second refuses to answer inside its own gate
    rather than posting ``invite_id: None`` (EDF-06-005, #3038).
    """

    def setup_method(self):
        reset_demo_failures()

    def teardown_method(self):
        reset_demo_failures()

    def _invite(self, *, invite_trigger, invite_lookup):
        state = story_state(*_CAST, case=mock_case())
        with (
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            patch.object(ActorSession, "set_stub_summary"),
            patch.object(
                invite_chain,
                "find_case_actor_participant_id",
                return_value="p",
            ),
            patch.object(
                invite_chain, "get_actor_by_id", return_value=mock_actor()
            ),
            patch.object(
                invite_chain, "find_case_invite_for_actor", **invite_lookup
            ) as find_invite,
        ):
            coordinator_invites_vendor(state)
        return state, find_invite

    def test_invite_trigger_failure_skips_the_lookup_and_the_answer(self):
        state, find_invite = self._invite(
            invite_trigger={
                "side_effect": RuntimeError("invite trigger failed")
            },
            invite_lookup={"return_value": "urn:test:invite"},
        )
        find_invite.assert_not_called()
        assert state.delivered_invite(VENDOR) is None

        with (
            patch.object(ActorSession, "accept_case_invite") as accept,
            patch_chain_shared(coordinated_case, "wait_for_case_on_container"),
            patch.object(coordinated_case, "wait_for_case_participants"),
            patch.object(coordinated_case, "run_invite_path_rm_triage"),
        ):
            vendor_accepts_and_joins(state)
        accept.assert_not_called()

    def test_invite_lookup_failure_skips_the_answer(self):
        state, _ = self._invite(
            invite_trigger={
                "return_value": SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                )
            },
            invite_lookup={
                "side_effect": AssertionError("timed out polling for Invite")
            },
        )
        assert state.delivered_invite(VENDOR) is None

        with patch.object(ActorSession, "reject_case_invite") as reject:
            vendor_rejects_invite(state)
        reject.assert_not_called()

    def test_a_delivered_invite_is_recorded_for_the_answer(self):
        state, _ = self._invite(
            invite_trigger={
                "return_value": SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                )
            },
            invite_lookup={"return_value": "urn:test:invite"},
        )
        assert state.delivered_invite(VENDOR) == "urn:test:invite"

    def test_the_invite_names_the_case_manager_so_the_stub_is_seeded(self):
        """#4285: the family's first chain seeds ``stub_summary``."""
        state = story_state(*_CAST, case=mock_case())
        with (
            patch.object(invite_chain, "_seed_stub_summary") as seed,
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                ),
            ),
            patch.object(
                invite_chain,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
        ):
            coordinator_invites_vendor(state)
        seed.assert_called_once_with(state.case_actor_client, state.case)


# ---------------------------------------------------------------------------
# The rejection reads the CASE_MANAGER's own store (#1876)
# ---------------------------------------------------------------------------


class TestVendorRejectsInvite:
    """The rejection commits only in the CASE_MANAGER's store (CLP-10-006).

    That store lives on the dedicated case-actor container; the Coordinator's
    container cannot address it, so every post-rejection read must go through
    ``case_actor_client``.
    """

    def setup_method(self):
        reset_demo_failures()

    def test_post_rejection_reads_go_through_the_case_actor_client(self):
        state = story_state(*_CAST, case=mock_case())
        state.invited(VENDOR, "urn:test:invite")

        with (
            patch.object(ActorSession, "reject_case_invite"),
            patch.object(
                coordinated_story, "wait_for_semantic_type_in_ledger"
            ) as ledger,
            patch.object(
                coordinated_story, "wait_for_case_participants"
            ) as roster,
            patch.object(
                coordinated_story, "wait_for_participant_rm_state"
            ) as rm_wait,
            patch.object(
                coordinated_story, "_check_participant_rm_state_in"
            ) as rm_check,
        ):
            vendor_rejects_invite(state)

        assert ledger.call_args.kwargs["client"] is state.case_actor_client
        assert (
            roster.call_args.kwargs["vendor_client"] is state.case_actor_client
        )
        assert rm_wait.call_args.kwargs["client"] is state.case_actor_client
        assert rm_check.call_args.kwargs["client"] is state.case_actor_client
