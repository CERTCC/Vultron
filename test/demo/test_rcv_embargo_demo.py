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

"""Unit tests for the RCV embargo demo scenario (#2071, DEMOMA-20, #5534).

The scenario drives four containers, so these tests pin its shape instead of a
running stack: its registration, the path its story walks, the order of its
fragments, the CLI options it offers, and the EM state each fragment asserts
before the next one runs.

``rcv-embargo`` is now composed (``STORY``), so what used to be a test of a
``_phase_*`` function is a test of the fragment that phase became, run against
a stand-in :class:`~vultron.demo.helpers.story.StoryState`
(:func:`~test.demo._helpers.story_state`).  The fragments of the opening the
embargo pair shares live in
:mod:`vultron.demo.helpers.coordinated_embargo_story` and are tested here,
where ``rcv-embargo`` is the first scenario to reach each of them; the
sibling's module tests only what ``rcvv-embargo`` alone tells.

Every test patches the collaborators out, so no HTTP happens.  ``demo_gate`` /
``demo_check`` / ``demo_step`` are left real: the failure accumulator is what
tells a recorded failure from a raise, and ``test_demo_context_managers.py``
owns their own behaviour.
"""

from collections.abc import Sequence
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import vultron.demo.helpers.coordinated_embargo_story as embargo_story
import vultron.demo.scenario.rcv_embargo_demo as demo
from test.demo._helpers import mock_case, story_state
from vultron.core.states.em import EM
from vultron.demo.cli import main as demo_cli
from vultron.demo.helpers.coordinated_embargo_story import (
    PROPOSED_EMBARGO,
    REPORTER_PROPOSES_EMBARGO,
    assert_canonical_em_state,
    coordinator_ends_the_embargo,
    embargo_stays_ended_through_closure,
    embargo_stays_ended_through_publication,
    embargo_survives_the_fix,
    reporter_revises_the_default_embargo,
    the_default_embargo_is_in_force,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
)
from vultron.demo.helpers.story import Choose, Fragment, StoryState
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils import _demo_failures, reset_demo_failures
from vultron.errors import DemoStoryError

#: The cast ``rcv-embargo``'s fragments read, by the names the family seats
#: its three fixed-role members under.
_CAST = (REPORTER, COORDINATOR, VENDOR)

#: The path this scenario used to declare as ``@scenario(path=...)``, before
#: the registry started reading it off the story's choices (DEMOCI-11-019).
#: Pinned against literals rather than against the registry, which would
#: compare the derivation with itself.
EXPECTED_PATH = (
    ("reporter-whom-to-tell", "coordinator"),
    ("coordinator-invite-whom", "vendor"),
    ("vendor-join", "accept"),
    ("reporter-after-join", "propose-embargo"),
    ("vendor-after-embargo", "report-fix-ready"),
)


@pytest.fixture(autouse=True)
def _clean_failures():
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, and a fragment
    that records a failure leaves it there for the next test — where it also
    changes what ``demo_gate`` does, since a gate skips its body once anything
    is recorded.
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


def _item_names(items: Sequence[Choose | Fragment]) -> list[str]:
    """Each story item named: a fragment by name, a choice as ``point:choice``."""
    return [
        f"{item.branch_point}:{item.choice}"
        if isinstance(item, Choose)
        else getattr(item, "__name__", repr(item))
        for item in items
    ]


def _states_asserted(wait: MagicMock) -> list[EM]:
    """The EM state of each canonical-case assertion, in order.

    ``assert_canonical_em_state`` passes it positionally as the third argument
    of ``wait_for_case_em_state``.
    """
    return [c.args[2] for c in wait.call_args_list]


def _opened_state() -> StoryState:
    """A story state with the three fixed-role members and an open case."""
    return story_state(*_CAST, case=mock_case())


# ---------------------------------------------------------------------------
# Registration and the place on the tree
# ---------------------------------------------------------------------------


class TestRegistration:
    """The scenario is discoverable, in the PR set, and where the spec says."""

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

    @pytest.mark.spec("DEMOCI-11-019")
    def test_the_registered_path_is_read_off_the_story(self):
        """The scenario declares a story, so its path is the story's choices.

        ``composed`` is what the registry records about having derived it; a
        scenario still typing ``path=`` would register ``False``.
        """
        spec = {s.name: s for s in discover_scenarios()}["rcv-embargo"]
        assert spec.composed is True
        assert spec.path == demo.STORY.path


class TestStoryPath:
    """Composition moved the code, not the scenario's place on the tree."""

    @pytest.mark.spec("DEMOCI-11-019")
    @pytest.mark.spec("DEMOMA-17-002")
    def test_the_story_walks_the_path_the_scenario_declared(self):
        assert demo.STORY.path == EXPECTED_PATH

    @pytest.mark.spec("DEMOMA-17-001")
    def test_the_story_opens_with_the_shared_prefix_objects_items(self):
        """The opening is the prefix *object*, not a copy of its steps.

        Identity of the whole shared stretch, item by item: a sibling that
        slipped a fragment in before ``vendor-after-embargo`` would still walk
        a valid path, and only this comparison would see it (DEMOCI-11-018).
        """
        shared = len(REPORTER_PROPOSES_EMBARGO.items)
        assert demo.STORY.items[:shared] == REPORTER_PROPOSES_EMBARGO.items
        # The first item of its own is the decision it parts from the sibling
        # at, so the prefix is the whole of what the two share.
        assert isinstance(demo.STORY.items[shared], Choose)

    @pytest.mark.spec("DEMOMA-20-007")
    @pytest.mark.spec("DEMOMA-20-008")
    def test_the_fragments_run_in_the_specified_order(self):
        """DEMOMA-20-007's order, with its EM assertion after each act.

        Each ``embargo_*`` fragment is the assertion DEMOMA-20-008 asks for
        between two acts, so their placement in this list is the property that
        the next act never starts before the EM state is checked.
        """
        shared = len(REPORTER_PROPOSES_EMBARGO.items)
        assert _item_names(demo.STORY.items[shared:]) == [
            "vendor-after-embargo:report-fix-ready",
            "vendor_reports_the_fix_ready",
            "embargo_survives_the_fix",
            "coordinator_ends_the_embargo",
            "everyone_publishes",
            "embargo_stays_ended_through_publication",
            "everyone_closes",
            "embargo_stays_ended_through_closure",
        ]


class TestCliOptionSurface:
    """``vultron-demo rcv-embargo`` offers one option per role, plus the skip.

    The CLI derives them from ``ROLES`` (DEMOCI-11-011), and composition left
    ``main()``'s signature alone, so the surface is pinned here rather than
    inferred from the role list.
    """

    @pytest.mark.spec("DEMOCI-11-011")
    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--coordinator-url",
            "--vendor-url",
            "--case-actor-url",
            "--reporter-id",
            "--coordinator-id",
            "--vendor-id",
        ],
    )
    def test_the_option_is_offered(self, option: str):
        result = CliRunner().invoke(demo_cli, ["rcv-embargo", "--help"])
        assert result.exit_code == 0, result.output
        assert option in result.output


# ---------------------------------------------------------------------------
# The opening the embargo pair shares (coordinated_embargo_story)
# ---------------------------------------------------------------------------


class TestTheSharedEmbargoOpening:
    """Case creation activates the default embargo; the proposal revises it.

    These fragments are the opening ``rcv-embargo`` and ``rcvv-embargo``
    share, so they are tested once, here.
    """

    @pytest.mark.spec("EP-04-001")
    @pytest.mark.spec("DEMOMA-20-008")
    def test_the_case_opens_under_the_default_embargo(self):
        """EM.ACTIVE before anyone proposes, read on the canonical case."""
        state = _opened_state()

        with patch.object(embargo_story, "wait_for_case_em_state") as em_wait:
            the_default_embargo_is_in_force(state)

        assert _states_asserted(em_wait) == [EM.ACTIVE]
        # The canonical case lives on the dedicated case-actor container, and
        # no participant's replica stands in for it (DEMOMA-20-011, #1876).
        assert em_wait.call_args.args[0] is state.case_actor_client
        # The default embargo's id is the case's, not the story's, so this
        # assertion pins no particular embargo — the proposal's does.
        assert em_wait.call_args.kwargs["active_embargo_id"] is None
        assert not _demo_failures

    @pytest.mark.spec("EP-09-001")
    @pytest.mark.spec("DEMOMA-20-002")
    @pytest.mark.spec("DEMOMA-20-008")
    def test_the_reporters_proposal_revises_the_default_embargo(self):
        """The relayed proposal takes effect, and the revision is kept.

        ``EM.ACTIVE`` alone cannot tell the revision from the embargo it
        revised, so the fragment reads the active embargo before and after and
        keeps the new one for the fragments that end it.
        """
        state = _opened_state()
        canonical = [
            MagicMock(active_embargo_id="urn:embargo:default"),
            MagicMock(active_embargo_id="urn:embargo:revised"),
        ]

        with (
            patch.object(
                embargo_story, "canonical_case", side_effect=canonical
            ),
            patch.object(embargo_story, "wait_for_case_em_state") as em_wait,
            patch.object(
                embargo_story, "demo_propose_and_activate_embargo"
            ) as helper,
        ):
            reporter_revises_the_default_embargo(state)

        helper.assert_called_once_with(
            state.actor(REPORTER),
            state.actor(COORDINATOR),
            state.actor(VENDOR),
            state.case,
            case_manager_client=state.case_actor_client,
        )
        assert state.kept(PROPOSED_EMBARGO) == "urn:embargo:revised"
        assert _states_asserted(em_wait) == [EM.ACTIVE]
        assert em_wait.call_args.args[0] is state.case_actor_client
        assert (
            em_wait.call_args.kwargs["active_embargo_id"]
            == "urn:embargo:revised"
        )
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-20-008")
    def test_a_proposal_that_took_no_effect_keeps_nothing(self):
        """An unchanged embargo is a recorded failure, not a revision.

        The fragment keeps nothing, which is how the fragments that end the
        embargo stop instead of terminating the wrong one (DEMOCI-01-007).
        """
        state = _opened_state()
        unchanged = MagicMock(active_embargo_id="urn:embargo:default")

        with (
            patch.object(
                embargo_story, "canonical_case", return_value=unchanged
            ),
            patch.object(embargo_story, "wait_for_case_em_state"),
            patch.object(embargo_story, "demo_propose_and_activate_embargo"),
        ):
            reporter_revises_the_default_embargo(state)

        assert _demo_failures
        with pytest.raises(DemoStoryError, match="embargo the Reporter"):
            state.kept(PROPOSED_EMBARGO)

    @pytest.mark.spec("DEMOCI-01-003")
    def test_a_missed_em_state_is_recorded_not_raised(self):
        """A failed EM assertion lands in the accumulator, not as a raise."""
        state = _opened_state()

        with patch.object(
            embargo_story,
            "wait_for_case_em_state",
            side_effect=AssertionError("timed out"),
        ):
            assert_canonical_em_state(state, EM.ACTIVE, "phase")

        assert _demo_failures


# ---------------------------------------------------------------------------
# The continuation ``rcv-embargo`` alone tells
# ---------------------------------------------------------------------------


class TestTheDeliberateTermination:
    """The fix leaves the embargo alone; the Coordinator then ends it."""

    @pytest.mark.spec("DEMOMA-20-008")
    def test_the_fix_being_ready_leaves_the_embargo_active(self):
        state = _opened_state()

        with patch.object(embargo_story, "wait_for_case_em_state") as em_wait:
            embargo_survives_the_fix(state)

        assert _states_asserted(em_wait) == [EM.ACTIVE]
        assert em_wait.call_args.args[0] is state.case_actor_client

    @pytest.mark.spec("DEMOMA-20-003")
    @pytest.mark.spec("DEMOMA-20-008")
    def test_the_coordinator_ends_the_embargo_in_force(self):
        """The owner terminates, and canonical plus replicas read EM.EXITED."""
        state = _opened_state()
        state.keep(PROPOSED_EMBARGO, "urn:embargo:revised")

        with (
            patch.object(embargo_story, "demo_terminate_embargo") as terminate,
            patch.object(embargo_story, "wait_for_case_em_state") as em_wait,
            patch.object(
                embargo_story, "wait_for_case_em_terminated"
            ) as replica_wait,
        ):
            coordinator_ends_the_embargo(state)

        terminate.assert_called_once_with(
            state.actor(COORDINATOR),
            state.case,
            case_manager_client=state.case_actor_client,
        )
        assert _states_asserted(em_wait) == [EM.EXITED]
        assert em_wait.call_args.args[0] is state.case_actor_client
        # The replicas learn it from the fan-out after the commit, so they are
        # read through their own containers, in turn (EDF-06-006).
        assert [c.kwargs["client"] for c in replica_wait.call_args_list] == [
            state.client(REPORTER),
            state.client(VENDOR),
        ]
        assert not _demo_failures

    @pytest.mark.spec("DEMOCI-01-007")
    def test_ending_an_embargo_no_fragment_kept_raises(self):
        """Without the revision there is nothing to end, so the story stops.

        This is what the old nested ``demo_gate`` did: a failed proposal
        skipped termination, publication and closure.  The fragment raises
        before terminating anything, and ``run_story`` turns that into the
        stop (``_run_fragment``).
        """
        state = _opened_state()

        with (
            patch.object(embargo_story, "demo_terminate_embargo") as terminate,
            patch.object(embargo_story, "wait_for_case_em_state") as em_wait,
            patch.object(embargo_story, "wait_for_case_em_terminated"),
            pytest.raises(DemoStoryError, match="embargo the Reporter"),
        ):
            coordinator_ends_the_embargo(state)

        terminate.assert_not_called()
        em_wait.assert_not_called()

    @pytest.mark.spec("DEMOMA-20-008")
    def test_publication_keeps_the_embargo_exited(self):
        state = _opened_state()

        with patch.object(embargo_story, "wait_for_case_em_state") as em_wait:
            embargo_stays_ended_through_publication(state)

        assert _states_asserted(em_wait) == [EM.EXITED]

    @pytest.mark.spec("DEMOMA-20-008")
    def test_closure_keeps_the_embargo_exited(self):
        state = _opened_state()

        with patch.object(embargo_story, "wait_for_case_em_state") as em_wait:
            embargo_stays_ended_through_closure(state)

        assert _states_asserted(em_wait) == [EM.EXITED]


class TestTheScenarioRunsItsOwnStory:
    """``run_rcv_embargo_demo`` hands ``run_story`` its name and its story."""

    def test_the_run_plays_this_scenarios_story(self):
        played: list[tuple[str, object]] = []

        with patch.object(
            demo,
            "run_story",
            side_effect=lambda name, plot, _open: played.append((name, plot)),
        ):
            demo.run_rcv_embargo_demo(
                reporter_client=MagicMock(),
                coordinator_client=MagicMock(),
                vendor_client=MagicMock(),
                case_actor_client=MagicMock(),
            )

        assert played == [("rcv-embargo", demo.STORY)]
