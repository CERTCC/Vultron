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

"""Unit tests for the RCVV embargo demo scenario (#2072, DEMOMA-21, #5534).

The scenario drives five containers, so these tests pin its shape instead of a
running stack: its registration, the path its story walks, the order of its
fragments, the CLI options it offers, the EM state each of its own fragments
asserts, and the three rules that make the scenario what it is — Vendor2 is
seeded and seated only when it joins, it signs the embargo in force, and the
collapse is never a deliberate termination.

``rcvv-embargo`` is now composed (``STORY``) from the opening it shares with
``rcv-embargo``, so what used to be a test of a ``_phase_*`` function is a test
of the fragment that phase became, run against a stand-in
:class:`~vultron.demo.helpers.story.StoryState`
(:func:`~test.demo._helpers.story_state`).  The shared opening's own fragments
are tested in ``test_rcv_embargo_demo.py``, where the sibling reaches them
first; this module tests the prefix only for *identity* with the sibling's, the
property that keeps the two recordings byte-identical up to the branch point
(DEMOCI-11-018).

Every test patches the collaborators out, so no HTTP happens.  ``demo_gate`` /
``demo_check`` / ``demo_step`` are left real: the failure accumulator is what
tells a recorded failure from a raise, and which props a failed gate leaves
unkept.
"""

import contextlib
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import vultron.demo.helpers.coordinated_embargo_story as embargo_story
import vultron.demo.scenario.rcv_embargo_demo as sibling
import vultron.demo.scenario.rcvv_embargo_demo as demo
from test.demo._helpers import mock_actor, mock_case, story_state
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as demo_cli
from vultron.demo.helpers import coordinated_story
from vultron.demo.helpers.coordinated_embargo_story import (
    PROPOSED_EMBARGO,
    REPORTER_PROPOSES_EMBARGO,
)
from vultron.demo.helpers.coordinated_story import COORDINATOR, REPORTER
from vultron.demo.helpers.story import Choose, Fragment, StoryState
from vultron.demo.scenario.rcvv_embargo_demo import (
    REVISED_EMBARGO,
    VENDOR1,
    VENDOR2,
    VENDOR2_SIGNED,
    both_vendors_report_the_fix_ready,
    everyone_including_vendor2_closes,
    reporter_publishes_and_the_embargo_collapses,
    vendor1_proposes_a_revision,
    vendor2_joins_under_the_revision,
)
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils import _demo_failures, reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: The cast the shared opening seats.  Vendor2 is not in it: it is a character
#: actor, seeded and seated by the fragment that brings it into the case.
_SEATED_AT_THE_START = (REPORTER, COORDINATOR, VENDOR1)

#: The path this scenario used to declare as ``@scenario(path=...)``, before
#: the registry started reading it off the story's choices (DEMOCI-11-019).
#: Pinned against literals rather than against the registry, which would
#: compare the derivation with itself.
EXPECTED_PATH = (
    ("reporter-whom-to-tell", "coordinator"),
    ("coordinator-invite-whom", "vendor"),
    ("vendor-join", "accept"),
    ("reporter-after-join", "propose-embargo"),
    ("vendor-after-embargo", "propose-revision"),
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


def _opened_state(*, vendor2_waiting: bool = False) -> StoryState:
    """A story state with the three seated members and an open case.

    Args:
        vendor2_waiting: Leave a container waiting for Vendor2, as
            ``run_rcvv_embargo_demo`` does, for the fragment that seeds it.
    """
    return story_state(
        *_SEATED_AT_THE_START,
        case=mock_case(),
        unseated=(VENDOR2,) if vendor2_waiting else (),
    )


# ---------------------------------------------------------------------------
# Registration and the place on the tree
# ---------------------------------------------------------------------------


class TestRegistration:
    """The scenario is discoverable, in the PR set, and where the spec says."""

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

    @pytest.mark.spec("DEMOCI-11-019")
    def test_the_registered_path_is_read_off_the_story(self):
        """The scenario declares a story, so its path is the story's choices.

        ``composed`` is what the registry records about having derived it; a
        scenario still typing ``path=`` would register ``False``.
        """
        spec = {s.name: s for s in discover_scenarios()}["rcvv-embargo"]
        assert spec.composed is True
        assert spec.path == demo.STORY.path


class TestStoryPath:
    """Composition moved the code, not the scenario's place on the tree."""

    @pytest.mark.spec("DEMOCI-11-019")
    @pytest.mark.spec("DEMOMA-17-002")
    def test_the_story_walks_the_path_the_scenario_declared(self):
        assert demo.STORY.path == EXPECTED_PATH

    @pytest.mark.spec("DEMOMA-17-001")
    @pytest.mark.spec("DEMOCI-11-018")
    def test_both_embargo_stories_share_the_prefix_objects_items(self):
        """The pair's opening is one prefix *object*, not two copies of it.

        Identity of the whole shared stretch, item by item, for both
        siblings: a scenario that slipped a fragment in before
        ``vendor-after-embargo`` would still walk a valid path, and only this
        comparison would see it.  The two recordings must match byte for byte
        up to the branch point, so the shared stretch has to be the same
        objects in the same order (DEMOCI-11-018, #5532).
        """
        shared = len(REPORTER_PROPOSES_EMBARGO.items)
        assert demo.STORY.items[:shared] == REPORTER_PROPOSES_EMBARGO.items
        assert sibling.STORY.items[:shared] == REPORTER_PROPOSES_EMBARGO.items
        # Each one's first own item is the decision it parts from the other
        # at, so the prefix is the whole of what the two share.
        assert isinstance(demo.STORY.items[shared], Choose)
        assert isinstance(sibling.STORY.items[shared], Choose)
        assert demo.STORY.items[shared] != sibling.STORY.items[shared]

    @pytest.mark.spec("DEMOMA-21-008")
    @pytest.mark.spec("DEMOMA-21-009")
    def test_the_fragments_run_in_the_specified_order(self):
        """DEMOMA-21-008's order, with its EM assertions between the acts.

        ``embargo_survives_the_fix`` and ``embargo_stays_ended_through_closure``
        are the assertions DEMOMA-21-009 asks for, so their placement in this
        list is the property that the next act never starts before the EM
        state is checked.
        """
        shared = len(REPORTER_PROPOSES_EMBARGO.items)
        assert _item_names(demo.STORY.items[shared:]) == [
            "vendor-after-embargo:propose-revision",
            "vendor1_proposes_a_revision",
            "vendor2_joins_under_the_revision",
            "both_vendors_report_the_fix_ready",
            "embargo_survives_the_fix",
            "reporter_publishes_and_the_embargo_collapses",
            "everyone_including_vendor2_closes",
            "embargo_stays_ended_through_closure",
        ]

    @pytest.mark.spec("DEMOMA-21-014")
    def test_the_story_never_ends_the_embargo_deliberately(self):
        """No termination fragment, and no termination trigger in the module.

        The collapse is CS.P's own consequence, so the scenario must not reach
        ``coordinator_ends_the_embargo`` — the sibling's fragment — nor call
        the trigger itself anywhere.
        """
        assert embargo_story.coordinator_ends_the_embargo in (
            sibling.STORY.items
        )
        assert embargo_story.coordinator_ends_the_embargo not in (
            demo.STORY.items
        )
        source = Path(demo.__file__).read_text(encoding="utf-8")
        assert "terminate_embargo(" not in source


class TestCliOptionSurface:
    """``vultron-demo rcvv-embargo`` offers one option per role, plus the skip.

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
            "--vendor2-url",
            "--case-actor-url",
            "--reporter-id",
            "--coordinator-id",
            "--vendor-id",
            "--vendor2-id",
        ],
    )
    def test_the_option_is_offered(self, option: str):
        result = CliRunner().invoke(demo_cli, ["rcvv-embargo", "--help"])
        assert result.exit_code == 0, result.output
        assert option in result.output


# ---------------------------------------------------------------------------
# The opening seeds three containers, and leaves Vendor2's waiting
# ---------------------------------------------------------------------------


class TestTheSharedOpeningSeedsOnlyTheThree:
    """Vendor2's container is reset with the rest, and seeded later.

    Every actor and peer record written before the case exists reads the
    recording clock, so one extra container moves the first ledger entry's
    timestamp away from ``rcv-embargo``, whose bytes this scenario's opening
    must match (DEMOCI-11-018, #5532).  A run must still start from a clean
    baseline on every container it will touch (DEMOMA-01-003), so the reset
    covers Vendor2's and the seeding does not.
    """

    @staticmethod
    def _open_the_cast(vendor2_client: MagicMock, vendor2_id: str):
        """Run the scenario's own ``open_cast``; return its state and mocks.

        ``run_story`` is intercepted to get hold of the closure the scenario
        builds, which is the only place the opening's seeding is wired, and it
        is then run with the seeding collaborators patched out.
        """
        opened: list[StoryState] = []
        recorded: list[SimpleNamespace] = []
        actors = [
            mock_actor(f"urn:test:{name}") for name in _SEATED_AT_THE_START
        ]

        def _capture(_name, _plot, open_cast):
            with (
                patch.object(
                    coordinated_story,
                    "reset_datalayer",
                    return_value={"status": "ok"},
                ) as reset,
                patch("vultron.demo.helpers.seeding.seed_case_actor_identity"),
                patch.object(
                    coordinated_story,
                    "seed_containers_rcv",
                    return_value=tuple(actors),
                ) as seed_three,
                patch.object(demo, "seed_containers_rcvv") as seed_four,
                patch.object(
                    coordinated_story,
                    "get_actor_by_id",
                    side_effect=list(actors),
                ),
            ):
                opened.append(open_cast(MagicMock()))
                recorded.append(
                    SimpleNamespace(
                        reset=reset,
                        seed_three=seed_three,
                        seed_four=seed_four,
                    )
                )

        with patch.object(demo, "run_story", side_effect=_capture):
            demo.run_rcvv_embargo_demo(
                reporter_client=MagicMock(),
                coordinator_client=MagicMock(),
                vendor_client=MagicMock(),
                vendor2_client=vendor2_client,
                case_actor_client=MagicMock(),
                vendor2_id=vendor2_id,
            )
        return opened[0], recorded[0]

    @pytest.mark.spec("DEMOCI-11-018")
    def test_only_the_three_fixed_containers_are_seeded(self):
        vendor2_client = MagicMock(name="vendor2_client")
        state, mocks = self._open_the_cast(
            vendor2_client, "urn:test:seeded:vendor2"
        )

        assert sorted(state.cast) == sorted(_SEATED_AT_THE_START)
        mocks.seed_three.assert_called_once()
        # The four-container seeding belongs to the fragment that brings
        # Vendor2 in, not to the opening.
        mocks.seed_four.assert_not_called()

    @pytest.mark.spec("DEMOMA-01-003")
    def test_vendor2s_container_is_still_reset_with_the_rest(self):
        vendor2_client = MagicMock(name="vendor2_client")
        _state, mocks = self._open_the_cast(
            vendor2_client, "urn:test:seeded:vendor2"
        )

        wiped = [c.kwargs["client"] for c in mocks.reset.call_args_list]
        assert vendor2_client in wiped

    @pytest.mark.spec("DEMOCI-11-018")
    def test_the_waiting_container_carries_vendor2s_client_and_id(self):
        """What the joining fragment reads: the client and the chosen URI."""
        vendor2_client = MagicMock(name="vendor2_client")
        state, _mocks = self._open_the_cast(
            vendor2_client, "urn:test:seeded:vendor2"
        )

        assert sorted(state.unseated) == [VENDOR2]
        waiting = state.container(VENDOR2)
        assert waiting.client is vendor2_client
        assert waiting.actor_id == "urn:test:seeded:vendor2"
        assert waiting.label == demo.VENDOR2_LABEL

    def test_the_run_plays_this_scenarios_story(self):
        """``run_story`` is handed this scenario's name and its own story."""
        played: list[tuple[str, object]] = []

        with patch.object(
            demo,
            "run_story",
            side_effect=lambda name, plot, _open: played.append((name, plot)),
        ):
            demo.run_rcvv_embargo_demo(
                reporter_client=MagicMock(),
                coordinator_client=MagicMock(),
                vendor_client=MagicMock(),
                vendor2_client=MagicMock(),
                case_actor_client=MagicMock(),
            )

        assert played == [("rcvv-embargo", demo.STORY)]


# ---------------------------------------------------------------------------
# Vendor1's revision (DEMOMA-21-002)
# ---------------------------------------------------------------------------


class TestVendor1ProposesARevision:
    """The second revision is relayed, activated, and kept for its dependents.

    ``EM.ACTIVE`` alone cannot tell this revision from the one it revised, so
    the fragment reads the active embargo and keeps the new id; Vendor2 signs
    whatever that is when it joins.
    """

    @staticmethod
    def _revise(*, now_in_force: str):
        """Run the fragment with ``now_in_force`` as the canonical embargo."""
        state = _opened_state()
        state.keep(PROPOSED_EMBARGO, "urn:embargo:one")

        with (
            patch.object(
                embargo_story,
                "canonical_case",
                return_value=MagicMock(active_embargo_id=now_in_force),
            ),
            patch.object(embargo_story, "wait_for_case_em_state") as em_wait,
            patch.object(demo, "demo_propose_embargo_revision") as helper,
        ):
            vendor1_proposes_a_revision(state)
        return state, em_wait, helper

    @pytest.mark.spec("DEMOMA-21-002")
    @pytest.mark.spec("DEMOMA-21-009")
    def test_the_revision_is_relayed_and_the_new_embargo_is_kept(self):
        state, em_wait, helper = self._revise(now_in_force="urn:embargo:two")

        helper.assert_called_once_with(
            proposing=state.actor(VENDOR1),
            accepting=state.actor(REPORTER),
            owner=state.actor(COORDINATOR),
            case=state.case,
            case_manager_client=state.case_actor_client,
        )
        assert state.kept(REVISED_EMBARGO) == "urn:embargo:two"
        assert _states_asserted(em_wait) == [EM.ACTIVE]
        # The canonical case lives on the dedicated case-actor container, and
        # no participant's replica stands in for it (DEMOMA-21-010, #1876).
        assert em_wait.call_args.args[0] is state.case_actor_client
        assert (
            em_wait.call_args.kwargs["active_embargo_id"] == "urn:embargo:two"
        )
        assert not _demo_failures

    @pytest.mark.spec("DEMOCI-01-007")
    @pytest.mark.spec("DEMOMA-21-009")
    def test_a_revision_that_took_no_effect_keeps_nothing(self):
        """The embargo still in force is not a revision of itself.

        The failure is recorded and nothing is kept, which is how the late
        invite stops rather than asserting about the wrong embargo.
        """
        state, em_wait, _helper = self._revise(now_in_force="urn:embargo:one")

        assert _demo_failures
        em_wait.assert_not_called()
        with pytest.raises(DemoStoryError, match="Vendor1's revision"):
            state.kept(REVISED_EMBARGO)

    @pytest.mark.spec("DEMOCI-01-007")
    def test_revising_an_embargo_no_fragment_kept_raises(self):
        """Without the Reporter's revision there is nothing to revise from."""
        state = _opened_state()

        with (
            patch.object(demo, "demo_propose_embargo_revision") as helper,
            pytest.raises(DemoStoryError, match="embargo the Reporter"),
        ):
            vendor1_proposes_a_revision(state)

        helper.assert_not_called()


# ---------------------------------------------------------------------------
# Vendor2 joins late and signs the embargo in force (DEMOMA-21-003/012)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _joining_vendor2(*, signs: bool = True) -> Iterator[SimpleNamespace]:
    """Patch every collaborator of ``vendor2_joins_under_the_revision``.

    Yields the mocks the tests assert on.  ``seed_containers_rcvv`` returns
    four actors as the real one does, so the fragment seats the fourth; the
    read-back is patched because ``seat_character_actor`` reads the new actor
    off its own container.

    Args:
        signs: Whether the consent wait finds Vendor2 a signatory.  A timeout
            is how a Vendor2 that never signed presents (DEMOMA-21-012).
    """
    seeded = tuple(
        mock_actor(f"urn:test:{name}")
        for name in (*_SEATED_AT_THE_START, VENDOR2)
    )
    consent: dict = {} if signs else {"side_effect": AssertionError("timeout")}
    with (
        patch.object(
            demo, "seed_containers_rcvv", return_value=seeded
        ) as seed,
        patch.object(
            coordinated_story, "get_actor_by_id", return_value=seeded[3]
        ) as read_back,
        patch.object(demo, "invitee_joins_the_case") as joins,
        patch.object(embargo_story, "wait_for_case_em_state") as canonical,
        patch.object(
            demo, "wait_for_participant_embargo_consent", **consent
        ) as signatory,
        patch.object(demo, "wait_for_case_em_state") as replica,
    ):
        yield SimpleNamespace(
            seed=seed,
            read_back=read_back,
            joins=joins,
            canonical=canonical,
            signatory=signatory,
            replica=replica,
        )


def _state_with_vendor2_joining() -> StoryState:
    """A state as Vendor2's fragment finds it: revision kept, container waiting."""
    state = _opened_state(vendor2_waiting=True)
    state.keep(PROPOSED_EMBARGO, "urn:embargo:one")
    state.keep(REVISED_EMBARGO, "urn:embargo:two")
    return state


def _state_after_vendor2_joined(*, signed: bool = True) -> StoryState:
    """A state as the fragments after Vendor2's join find it: four seated.

    Vendor2 is seated directly rather than by replaying its own fragment,
    which :class:`TestVendor2JoinsUnderTheRevision` covers on its own.

    Args:
        signed: Whether the join left a signed embargo behind.  A Vendor2 that
            never consented keeps none (DEMOMA-21-012).
    """
    state = story_state(*_SEATED_AT_THE_START, VENDOR2, case=mock_case())
    state.keep(PROPOSED_EMBARGO, "urn:embargo:one")
    state.keep(REVISED_EMBARGO, "urn:embargo:two")
    if signed:
        state.keep(VENDOR2_SIGNED, "urn:embargo:two")
    return state


class TestVendor2JoinsUnderTheRevision:
    """Vendor2 is seeded and seated by the fragment that invites it.

    The ordering is load-bearing: the shared opening seeds only the three
    fixed-role containers, so Vendor2's own seeding has to happen here, after
    the case exists, for the two scenarios' recordings to match up to the
    branch point (DEMOCI-11-018).
    """

    @pytest.mark.spec("DEMOCI-11-018")
    def test_vendor2_is_seeded_through_the_four_container_seeding(self):
        """The idempotent four-way seeding, on the waiting container.

        It re-creates the three already-seated actors under the ids they
        already hold — ``POST /actors/`` and the peer registration are
        idempotent — so Vendor2 becomes a peer of each of them.
        """
        state = _state_with_vendor2_joining()
        waiting = state.container(VENDOR2)

        with _joining_vendor2() as mocks:
            vendor2_joins_under_the_revision(state)

        mocks.seed.assert_called_once_with(
            reporter_client=state.client(REPORTER),
            coordinator_client=state.client(COORDINATOR),
            vendor_client=state.client(VENDOR1),
            vendor2_client=waiting.client,
            reporter_actor_id="urn:test:reporter",
            coordinator_actor_id="urn:test:coordinator",
            vendor_actor_id="urn:test:vendor",
            vendor2_actor_id=waiting.actor_id,
            case_actor_client=state.case_actor_client,
        )

    @pytest.mark.spec("DEMOCI-11-018")
    def test_vendor2_is_then_seated_for_the_later_fragments(self):
        """The container stops waiting and the cast gains the fourth member.

        The session is bound to Vendor2's own container and reads its actor
        back from there, which is the form a trigger session binds to.
        """
        state = _state_with_vendor2_joining()
        waiting = state.container(VENDOR2)

        with _joining_vendor2() as mocks:
            vendor2_joins_under_the_revision(state)

        assert state.unseated == {}
        assert state.client(VENDOR2) is waiting.client
        assert state.actor_id(VENDOR2) == f"urn:test:{VENDOR2}"
        assert mocks.read_back.call_args.args[0] is waiting.client

    @pytest.mark.spec("DEMOMA-21-003")
    def test_the_invite_offers_the_vendor_role_to_the_full_roster(self):
        state = _state_with_vendor2_joining()

        with _joining_vendor2() as mocks:
            vendor2_joins_under_the_revision(state)

        args = mocks.joins.call_args.args
        kwargs = mocks.joins.call_args.kwargs
        assert args[1:] == (VENDOR2, demo.VENDOR2_LABEL)
        assert kwargs["role"] is CVDRole.VENDOR
        assert kwargs["seated"] == (REPORTER, COORDINATOR, VENDOR1, VENDOR2)

    @pytest.mark.spec("DEMOMA-21-003")
    @pytest.mark.spec("DEMOMA-21-009")
    def test_the_canonical_case_and_vendor2s_replica_hold_the_revision(self):
        """Both reads name the revision, which ``EM.ACTIVE`` alone cannot."""
        state = _state_with_vendor2_joining()

        with _joining_vendor2() as mocks:
            vendor2_joins_under_the_revision(state)

        assert _states_asserted(mocks.canonical) == [EM.ACTIVE]
        assert mocks.canonical.call_args.args[0] is state.case_actor_client
        assert (
            mocks.canonical.call_args.kwargs["active_embargo_id"]
            == "urn:embargo:two"
        )
        assert mocks.replica.call_args.args[0] is state.client(VENDOR2)
        assert mocks.replica.call_args.args[2] is EM.ACTIVE
        assert (
            mocks.replica.call_args.kwargs["active_embargo_id"]
            == "urn:embargo:two"
        )
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-21-012")
    def test_vendor2_is_a_signatory_of_the_embargo_in_force(self):
        """Accepting the invitation consents to it (CM-11-002).

        The consent row is read in the CASE_MANAGER's own store, on the
        dedicated case-actor container (#1876), and the signed embargo is kept
        for the fragments that presuppose it.
        """
        state = _state_with_vendor2_joining()

        with _joining_vendor2() as mocks:
            vendor2_joins_under_the_revision(state)

        args = mocks.signatory.call_args.args
        assert args[0] is state.case_actor_client
        assert args[1] == state.case.id_
        assert args[2] == state.actor_id(VENDOR2)
        assert args[3] == "urn:embargo:two"
        assert args[4] is EmbargoConsentState.AGREED
        assert state.kept(VENDOR2_SIGNED) == "urn:embargo:two"

    @pytest.mark.spec("DEMOMA-21-012")
    def test_a_vendor2_that_never_signs_keeps_nothing(self):
        """The signature gate records the failure and keeps no signed embargo.

        The fix lifecycle, the collapse and the closure presuppose it, so they
        stop rather than acting on a case Vendor2 never consented to.
        """
        state = _state_with_vendor2_joining()

        with _joining_vendor2(signs=False):
            vendor2_joins_under_the_revision(state)

        assert _demo_failures
        with pytest.raises(DemoStoryError, match="Vendor2 signed"):
            state.kept(VENDOR2_SIGNED)

    @pytest.mark.spec("DEMOCI-01-007")
    def test_joining_without_a_kept_revision_raises(self):
        """Vendor2 is invited only once the revision is confirmed active."""
        state = _opened_state(vendor2_waiting=True)

        with (
            _joining_vendor2() as mocks,
            pytest.raises(DemoStoryError, match="Vendor1's revision"),
        ):
            vendor2_joins_under_the_revision(state)

        mocks.seed.assert_not_called()
        mocks.joins.assert_not_called()


# ---------------------------------------------------------------------------
# Both vendors fix, the Reporter publishes, and the embargo collapses
# ---------------------------------------------------------------------------


class TestBothVendorsReportTheFixReady:
    """Each vendor reports fix ready from its own container, Vendor1 first."""

    @pytest.mark.spec("DEMOMA-21-008")
    def test_both_vendors_report_in_turn(self):
        state = _state_after_vendor2_joined()

        with (
            patch.object(coordinated_story, "wait_for_participant_rm_state"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(coordinated_story, "verify_fix_ready") as verified,
        ):
            both_vendors_report_the_fix_ready(state)

        # verify_fix_ready names the vendor whose CS the Coordinator reads.
        reported = [
            c.kwargs["receiver_actor_id"] for c in verified.call_args_list
        ]
        assert reported[0] == state.actor_id(VENDOR1)
        assert state.actor_id(VENDOR2) in reported
        assert reported.index(state.actor_id(VENDOR2)) > 0

    @pytest.mark.spec("DEMOMA-21-012")
    def test_reporting_without_vendor2s_signature_raises(self):
        """The fix lifecycle presupposes the signatory, so it stops without it."""
        state = _state_after_vendor2_joined(signed=False)

        with (
            patch.object(ActorSession, "notify_fix_ready") as fix_ready,
            pytest.raises(DemoStoryError, match="Vendor2 signed"),
        ):
            both_vendors_report_the_fix_ready(state)

        fix_ready.assert_not_called()


class TestTheAccidentalCollapse:
    """CS.P ends the embargo, and nobody terminates it (DEMOMA-21-014)."""

    @staticmethod
    def _collapse(state: StoryState):
        with (
            patch.object(ActorSession, "notify_published") as published,
            patch.object(ActorSession, "terminate_embargo") as terminate,
            patch.object(demo, "wait_for_semantic_type_in_ledger") as ledger,
            patch.object(embargo_story, "wait_for_case_em_state") as em_wait,
            patch.object(
                embargo_story, "wait_for_case_em_terminated"
            ) as replica_wait,
        ):
            reporter_publishes_and_the_embargo_collapses(state)
        return SimpleNamespace(
            published=published,
            terminate=terminate,
            ledger=ledger,
            em_wait=em_wait,
            replica_wait=replica_wait,
        )

    @pytest.mark.spec("DEMOMA-21-004")
    @pytest.mark.spec("DEMOMA-21-014")
    def test_the_reporters_publication_is_what_ends_the_embargo(self):
        state = _state_after_vendor2_joined()

        mocks = self._collapse(state)

        mocks.published.assert_called_once_with()
        # Nobody terminates the embargo: the collapse is CS.P's consequence.
        mocks.terminate.assert_not_called()
        assert not _demo_failures

    @pytest.mark.spec("DEMOMA-21-009")
    @pytest.mark.spec("DEMOMA-21-014")
    def test_the_teardown_is_read_where_the_case_manager_commits_it(self):
        """The commit is gated on before any replica is expected to show it."""
        state = _state_after_vendor2_joined()

        mocks = self._collapse(state)

        assert mocks.ledger.call_args.kwargs["semantic_type"] == (
            "remove_embargo_event_from_case"
        )
        assert mocks.ledger.call_args.kwargs["client"] is (
            state.case_actor_client
        )
        assert _states_asserted(mocks.em_wait) == [EM.EXITED]
        assert mocks.em_wait.call_args.args[0] is state.case_actor_client
        assert [
            c.kwargs["client"] for c in mocks.replica_wait.call_args_list
        ] == [
            state.client(COORDINATOR),
            state.client(REPORTER),
            state.client(VENDOR1),
            state.client(VENDOR2),
        ]


class TestClosure:
    """Vendor2 closes with the rest; the Case Owner leaves last."""

    @pytest.mark.spec("DEMOMA-21-008")
    @pytest.mark.spec("CM-23-015")
    def test_every_participant_closes_and_vendor2_is_one_of_them(self):
        state = _state_after_vendor2_joined()

        with patch.object(
            coordinated_story, "close_case_owner_last"
        ) as closure:
            everyone_including_vendor2_closes(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M7"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(VENDOR1),
            state.client(REPORTER),
            state.client(VENDOR2),
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)
