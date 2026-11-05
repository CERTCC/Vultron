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

"""The coordinator-first family's shared opening (#5533, #5534).

Pins :mod:`vultron.demo.helpers.coordinated_story.opening`: the M1
milestone and the owner's triage budget when the Coordinator engages the
case, and the invite chain that still skips its dependents now that the
Invite and the answer are two fragments with the Vendor's branch point
between them.
"""

import contextlib
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import (
    mock_case,
    patch_chain_shared,
    story_state,
)
from test.demo.coordinated_story._support import (
    CAST,
    patched_rejection_polls,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.coordinated_story import (
    ENGAGED_CASE,
    OWNER_TRIAGE_TIMEOUT,
    VENDOR,
    coordinator_invites_vendor,
    joining as coordinated_joining,
    opening as coordinated_opening,
    reporter_tells_coordinator,
    vendor_accepts_and_joins,
    vendor_rejects_invite,
)
from vultron.demo.helpers.invite_chain import (
    chain as invite_runs,
    links as invite_links,
)
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")

# ---------------------------------------------------------------------------
# Milestone assertions — AC-4 of ISSUE-1976, now on the fragments
# ---------------------------------------------------------------------------


class TestCoordinatedMilestones:
    """Each fragment calls the milestone helper its phase did."""

    @pytest.mark.spec("CM-12-001")
    @pytest.mark.spec("VP-02-015")
    def test_reporter_tells_coordinator_calls_verify_case_active(self):
        """M1 runs when the Coordinator engages the case, on one budget.

        The fragment's own triage budget is pinned here because this is the
        only place left that can pin it: the opening is one copy of the code,
        so the five scenarios that share it share the one
        :data:`OWNER_TRIAGE_TIMEOUT` and none of them passes a budget of its
        own.  ``rcvcv`` is what set the value — 60 s for a run that brings
        five actor containers up under CI load (ISSUE-2811) — and a budget
        only bounds how long a wait may take, so the narrower siblings
        inherit it without admitting or refusing anything differently.
        """
        state = story_state(*CAST)
        case = mock_case()
        # A distinct object, so the re-read below is observable: handing back
        # the triage's own case would pass whether or not the fragment
        # restated it.
        reread = mock_case()

        with (
            patch.object(
                coordinated_opening,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
            ),
            patch.object(
                coordinated_opening,
                "run_direct_path_rm_triage",
                return_value=case,
            ) as triage,
            patch.object(coordinated_opening, "wait_for_case_participants"),
            patch.object(
                coordinated_opening, "as_VulnerabilityCase"
            ) as mock_vc,
            patch.object(coordinated_opening, "verify_case_active") as mock_m1,
            patch.object(
                coordinated_opening,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            mock_vc.model_validate.return_value = reread
            reporter_tells_coordinator(state)

        mock_m1.assert_called_once()
        assert (
            triage.call_args.kwargs["timeout_seconds"] == OWNER_TRIAGE_TIMEOUT
        ), (
            "the Coordinator's RM triage runs on the family's one budget"
            f" (ISSUE-2811); got {triage.call_args.kwargs!r}"
        )
        # The fragment hands the case to the state, which arms the dump as
        # soon as there is something to dump (DEMOMA-23-003), and then
        # restates it from the owner's own store once the triage and the
        # participant seating have moved on.
        assert state.case is reread, (
            "the fragment must re-read the case the Coordinator now stores; "
            f"state holds {state.case!r}"
        )
        harness = cast(MagicMock, state.harness)
        harness.dump_with.assert_called_once()
        # Armed once, on the case that existed first: restating must not
        # re-arm the dump or follow a second ledger (DEMOMA-23-003).
        harness.follow_ledger.assert_called_once_with(
            state.case_actor_client, case.id_
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

    def _invite(self, *, invite_trigger, invite_lookup):
        state = story_state(*CAST, case=mock_case())
        # The roster the opening confirmed is this invite's precondition
        # (ENGAGED_CASE); the tests below are about what happens *after* it
        # held, so they stand in for the opening that keeps it.
        state.keep(ENGAGED_CASE, str(state.case.id_))
        with (
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            # Nothing stubs the stub-summary seed here: this directory's
            # conftest no-ops ``invite_chain.chain._seed_stub_summary``
            # whenever the case-manager client is a mock, and
            # ``story_state`` builds mocks (#5444).
            patch.object(
                invite_links, "find_case_invite_for_actor", **invite_lookup
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
            patch_chain_shared(
                coordinated_joining, "wait_for_case_on_container"
            ),
            patch.object(coordinated_joining, "wait_for_case_participants"),
            patch.object(coordinated_joining, "run_invite_path_rm_triage"),
        ):
            vendor_accepts_and_joins(state)
        accept.assert_not_called()

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_roster_the_opening_never_confirmed_skips_the_invite(self):
        """The roster is this invite's causal precondition, so it gates it.

        A flat story cannot nest the invite inside the roster wait's gate, so
        the gate keeps ``ENGAGED_CASE`` and the invite reads it: a roster that
        never arrived stops the story here instead of inviting into a case the
        owner cannot vouch for, which is what the hand-placed scenarios got
        from nesting the whole invite/admit chain inside that gate.
        """
        state = story_state(*CAST, case=mock_case())

        with (
            patch.object(ActorSession, "invite_actor_to_case") as invite,
            patch.object(invite_links, "find_case_invite_for_actor") as find,
            pytest.raises(DemoStoryError, match="roster"),
        ):
            coordinator_invites_vendor(state)

        invite.assert_not_called()
        find.assert_not_called()

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

        # The rejection fragment's own container polls are stubbed, the way the
        # sibling above stubs the joining fragment's.  The subject here is that
        # the answer is skipped; left real, those polls run out their budget
        # against a mock store and cost 20 s proving nothing (#5597).
        with (
            patch.object(ActorSession, "reject_case_invite") as reject,
            patched_rejection_polls(),
        ):
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
        state = story_state(*CAST, case=mock_case())
        state.keep(ENGAGED_CASE, str(state.case.id_))
        with (
            patch.object(invite_runs, "_seed_stub_summary") as seed,
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                ),
            ),
            patch.object(
                invite_links,
                "find_case_invite_for_actor",
                return_value="urn:test:invite",
            ),
        ):
            coordinator_invites_vendor(state)
        seed.assert_called_once_with(state.case_actor_client, state.case)
