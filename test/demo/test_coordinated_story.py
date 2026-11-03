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

"""Story fragments of the Reporter → Coordinator → Vendor family (#5533, #5534).

Every scenario of the family is assembled from
``vultron.demo.helpers.coordinated_story``, so the checks that used to sit on
each scenario's ``_phase_*`` functions — and then briefly on
``helpers/coordinated_case.py`` — sit on the shared fragments and helpers
here: the milestone calls, the causal gates, the skip-on-failure behaviour of
the invite chain now that the Invite and the answer are two fragments with the
Vendor's branch point between them, and the two helpers the continuations
share (``invitee_joins_the_case``, ``close_the_case``).  The client and
ledger-dump plumbing every family shares is pinned in ``test_story_cast.py``.

Every test patches the collaborators out, so no HTTP happens; ``demo_gate`` /
``demo_check`` / ``demo_step`` are left real wherever the test is about control
flow, and stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).

These tests are mock-only, yet they live here rather than in
``test/demo_unit/`` — and so are auto-marked ``integration`` by this
directory's ``conftest.py`` — because they depend on that conftest's autouse
fixtures: ``stub_summary_seed`` and ``stub_full_case_reply`` skip the two
chain steps that have no container to talk to when the client is a mock
(#5444), and the ledger-rebuild guard runs on the way out.  Copying them
under ``test/demo_unit/`` would leave two copies to keep in step, which is
where order-dependent failures live, so the module stays here and pays the
``integration`` marker.  ``test/demo_unit/test_story.py`` states the other
half of the rule: a test that needs none of those fixtures belongs there.
"""

import contextlib
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, call, patch

import pytest

from test.demo._helpers import (
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    patch_chain_shared,
    story_state,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import coordinated_story, invite_chain, story_cast
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    ENGAGED_CASE,
    OWNER_TRIAGE_TIMEOUT,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
    close_the_case,
    coordinated_seats,
    coordinator_invites_vendor,
    everyone_closes,
    everyone_publishes,
    invitee_joins_the_case,
    invitee_triages_after_joining,
    open_coordinated_cast,
    reporter_tells_coordinator,
    reporter_then_coordinator_close,
    vendor_accepts_and_joins,
    vendor_rejects_invite,
    vendor_reports_the_fix_ready,
)
from vultron.demo.helpers.story import (
    StoryProp,
    UnseatedContainer,
)
from vultron.demo.utils import reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

_CAST = (REPORTER, COORDINATOR, VENDOR)

#: A character actor this family's continuations bring in mid-story: the second
#: Coordinator of ``rcvcv`` and the second Vendor of ``rcvv-embargo`` are both
#: seated under a name the shared opening never sees.
_JOINER = "joiner"

#: A stand-in for the prop a caller hands ``invitee_joins_the_case``, where
#: the two-coordinator pair hands it ``SECOND_COORDINATOR_JOINED`` (#5535).
_JOINED: StoryProp[str] = StoryProp("case the test joiner joined", str)


@pytest.fixture(autouse=True)
def _fresh_failures():
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, and a fragment
    that records a failure leaves it there for the next test — where it
    changes what ``demo_gate`` does (a gate skips its body once anything is
    recorded).  One fixture for the whole module rather than a reset per
    class, which is where the classes that had none were reading another
    class's leftovers.
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


@contextlib.contextmanager
def _join_stubs() -> Iterator[SimpleNamespace]:
    """Stub every collaborator of ``invitee_joins_the_case``.

    Yields the invite chain, the roster wait and the RM triage, so a test can
    say which of the three ran and what each was handed.
    """
    with (
        patch.object(coordinated_story, "wait_for_case_on_container"),
        patch.object(coordinated_story, "run_case_invite_chain") as chain,
        patch.object(
            coordinated_story, "wait_for_case_participants"
        ) as roster,
        patch.object(coordinated_story, "run_invite_path_rm_triage") as triage,
        no_demo_banners(coordinated_story),
    ):
        yield SimpleNamespace(chain=chain, roster=roster, triage=triage)


@contextlib.contextmanager
def _recorded_gates() -> Iterator[list[str]]:
    """Collect every ``demo_gate`` label the fragment under test opens.

    A gate's label is what a reader sees when its wait times out, so a label
    naming the family's Coordinator while the first Vendor is the one
    inviting sends that reader to the wrong container (#5536).  Enter it
    *after* :func:`_join_stubs`, whose ``no_demo_banners`` also patches
    ``demo_gate``: the later patch is the one in force.
    """
    labels: list[str] = []

    def _gate(label: str) -> contextlib.AbstractContextManager[None]:
        labels.append(label)
        return contextlib.nullcontext()

    with patch.object(coordinated_story, "demo_gate", side_effect=_gate):
        yield labels


# ---------------------------------------------------------------------------
# The shared cast opening
# ---------------------------------------------------------------------------


class TestOpenCoordinatedCast:
    """One reset and one seeding for every scenario of the family.

    The reset and the read-back are patched on
    ``vultron.demo.helpers.story_cast``, not on this module: the opening every
    composed family shares lives there (``open_story_cast``) and this family's
    opening only supplies its seats and its seeder, so ``reset_datalayer`` and
    ``get_actor_by_id`` are resolved on ``story_cast``.  ``seed_containers_rcv``
    stays on this module, which is the only place that names it.
    """

    def test_the_reset_covers_every_container(self):
        reporter_client = mock_client()
        coordinator_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        actors = [mock_actor(f"urn:test:{name}") for name in _CAST]

        with (
            patch.object(
                story_cast,
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
                story_cast,
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

    def test_a_character_actors_container_is_reset_but_not_seeded(self):
        """An unseated container is wiped here and seeded later (#5532).

        A run starts from a clean baseline on every container it will touch
        (DEMOMA-01-003), so the reset covers the character actor's; but every
        actor and peer record written before the case exists reads the
        recording clock, so seeding it here would move the first ledger
        entry's timestamp away from the siblings this opening must match byte
        for byte (DEMOCI-11-018).
        """
        joiner_client = mock_client()
        actors = [mock_actor(f"urn:test:{name}") for name in _CAST]

        with (
            patch.object(
                story_cast,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset_mock,
            patch("vultron.demo.helpers.seeding.seed_case_actor_identity"),
            patch.object(
                coordinated_story,
                "seed_containers_rcv",
                return_value=tuple(actors),
            ) as seeded,
            patch.object(
                story_cast,
                "get_actor_by_id",
                side_effect=list(actors),
            ),
        ):
            state = open_coordinated_cast(
                MagicMock(),
                reporter_client=mock_client(),
                coordinator_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                dump=lambda _state: None,
                unseated={
                    _JOINER: UnseatedContainer(
                        "Joiner", joiner_client, "urn:test:joiner"
                    )
                },
            )

        reset_mock.assert_has_calls([call(client=joiner_client)])
        assert joiner_client not in seeded.call_args.kwargs.values()
        assert _JOINER not in state.cast
        assert state.container(_JOINER).client is joiner_client
        assert state.container(_JOINER).actor_id == "urn:test:joiner"

    def test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with(self):
        """The failure is recorded by demo_step; the story stops here."""
        with (
            patch.object(story_cast, "reset_datalayer"),
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


class TestCoordinatedSeats:
    """The three seats the shared opening hands ``open_story_cast``."""

    @pytest.mark.spec("DEMOMA-17-001")
    def test_the_seats_are_in_the_seeders_return_order(self):
        """Seat order is ``seed_containers_rcv``'s return order.

        ``open_story_cast`` zips the seats with what the seeder returned, so
        the order is what binds each session to its own container: a seat out
        of place would seat the Coordinator's session on the Vendor's client
        and every later fragment would act as the wrong actor.
        ``seed_containers_rcv`` returns ``(reporter, coordinator, vendor)``.
        """
        clients = {name: mock_client() for name in _CAST}

        seats = coordinated_seats(
            reporter_client=clients[REPORTER],
            coordinator_client=clients[COORDINATOR],
            vendor_client=clients[VENDOR],
            reporter_id="urn:test:reporter",
            coordinator_id="urn:test:coordinator",
            vendor_id="urn:test:vendor",
        )

        assert [seat.name for seat in seats] == list(_CAST), (
            "the seats must be in seed_containers_rcv's return order, which is"
            f" what binds each session to its own container; got {seats!r}"
        )
        assert [seat.label for seat in seats] == [
            REPORTER_LABEL,
            COORDINATOR_LABEL,
            VENDOR_LABEL,
        ]
        assert [seat.client for seat in seats] == [
            clients[name] for name in _CAST
        ], "each seat carries its own container's client (DEMOCI-11-020)"
        assert [seat.actor_id for seat in seats] == [
            f"urn:test:{name}" for name in _CAST
        ]

    def test_an_undeclared_actor_id_leaves_the_container_to_derive_one(self):
        """A run given no deterministic id passes none on (``CastSeat``)."""
        seats = coordinated_seats(
            reporter_client=mock_client(),
            coordinator_client=mock_client(),
            vendor_client=mock_client(),
        )

        assert [seat.actor_id for seat in seats] == [None, None, None], (
            "an absent --<role>-id must stay absent, so the container derives"
            f" the actor's URI itself; got {seats!r}"
        )


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
        state = story_state(*_CAST)
        case = mock_case()
        # A distinct object, so the re-read below is observable: handing back
        # the triage's own case would pass whether or not the fragment
        # restated it.
        reread = mock_case()

        with (
            patch.object(
                coordinated_story,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
            ),
            patch.object(
                coordinated_story,
                "run_direct_path_rm_triage",
                return_value=case,
            ) as triage,
            patch.object(coordinated_story, "wait_for_case_participants"),
            patch.object(coordinated_story, "as_VulnerabilityCase") as mock_vc,
            patch.object(coordinated_story, "verify_case_active") as mock_m1,
            patch.object(
                coordinated_story,
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

    def test_vendor_reports_the_fix_ready_calls_verify_fix_ready(self):
        """M5 runs when the Vendor reports fix ready."""
        state = story_state(*_CAST, case=mock_case())

        with (
            patch.object(coordinated_story, "wait_for_participant_rm_state"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(coordinated_story, "verify_fix_ready") as mock_m5,
            patch.object(
                coordinated_story,
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
                coordinated_story, "wait_for_participant_rm_state", _rm_wait
            ),
            patch.object(
                ActorSession,
                "notify_fix_ready",
                side_effect=lambda *a, **kw: call_order.append("fix_ready"),
            ),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(coordinated_story, "verify_fix_ready"),
        ):
            vendor_reports_the_fix_ready(state)

        assert rm_calls, (
            "wait_for_participant_rm_state must be called (ADR-0058/CSB-18-001)"
        )
        assert all(
            c.get("expected_states") == {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
            for c in rm_calls
        ), "expected_states must be {ACCEPTED, DEFERRED, CLOSED} (CSB-18-001)"
        # Membership first: indexing a missing call raises ValueError and the
        # ordering assertion's message never prints.
        assert "rm_wait" in call_order, call_order
        assert "fix_ready" in call_order, (
            f"notify_fix_ready was never called. Call order: {call_order}"
        )
        assert call_order.index("rm_wait") < call_order.index("fix_ready"), (
            "wait_for_participant_rm_state must precede notify_fix_ready"
            " (ADR-0058)"
        )

    def test_everyone_publishes_calls_verify_publicly_disclosed(self):
        """M6 runs when every participant has reported publication."""
        state = story_state(*_CAST, case=mock_case())

        with (
            patch.object(ActorSession, "notify_published"),
            patch.object(coordinated_story, "wait_for_case_em_terminated"),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(
                coordinated_story, "verify_publicly_disclosed"
            ) as mock_m6,
            patch.object(
                coordinated_story,
                "demo_check",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            everyone_publishes(state)

        mock_m6.assert_called()


# ---------------------------------------------------------------------------
# The closure every continuation shares (CM-23-015)
# ---------------------------------------------------------------------------


class TestCloseTheCase:
    """Who leaves, through whose container, and who is named the owner.

    ``close_the_case`` is the shared wrapper; the sequencing itself —
    the owner's ``Leave`` after every other departure is recorded — belongs
    to ``close_case_owner_last`` and is pinned on a real run of it in
    ``test_later_vendors.py``.
    """

    def test_everyone_closes_runs_the_closure_milestone(self):
        """``rcv``'s three-party closure is M7 (CM-23-004)."""
        state = story_state(*_CAST, case=mock_case())

        with patch.object(
            coordinated_story, "close_case_owner_last"
        ) as closure:
            everyone_closes(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M7"
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(VENDOR),
            state.client(REPORTER),
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)

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

    @pytest.mark.spec("CM-23-015")
    def test_the_leavers_keep_their_order_and_the_owner_stands_apart(self):
        """The order given is the order handed over, the owner excluded.

        A scenario with a character actor among its leavers (``rcvcv``,
        ``rcvv-embargo``) passes it in the position it leaves in, and each
        leaver acts through its own container — a leaver paired with another's
        client would send that actor's ``Leave`` twice and never its own.
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with patch.object(
            coordinated_story, "close_case_owner_last"
        ) as closure:
            close_the_case(
                state,
                others=(VENDOR, _JOINER, REPORTER),
                owner=COORDINATOR,
                milestone="M8",
            )

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M8"
        assert [leaver.actor.id_ for leaver in kwargs["others"]] == [
            f"urn:test:{name}" for name in (VENDOR, _JOINER, REPORTER)
        ]
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(name) for name in (VENDOR, _JOINER, REPORTER)
        ]
        assert kwargs["owner"].actor.id_ == f"urn:test:{COORDINATOR}"
        assert kwargs["owner"].client is state.client(COORDINATOR)

    @pytest.mark.spec("CM-23-004")
    def test_a_scenario_that_numbers_no_milestone_passes_none_through(self):
        """``rvcv-handoff`` numbers no closure milestone (#5536).

        Its check descriptions are then unprefixed, which is
        ``close_case_owner_last``'s own ``milestone=None`` behaviour; the
        wrapper's part is to pass the absence through rather than invent an
        ``"M?"`` prefix the scenario never declared.
        """
        state = story_state(*_CAST, case=mock_case())

        with patch.object(
            coordinated_story, "close_case_owner_last"
        ) as closure:
            close_the_case(state, others=(REPORTER,), milestone=None)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] is None, (
            "a scenario that numbers no closure milestone must reach"
            " close_case_owner_last with milestone=None, so its checks are"
            f" unprefixed (CM-23-004); got {kwargs['milestone']!r}"
        )
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(REPORTER)
        ]
        assert kwargs["owner"].client is state.client(COORDINATOR)

    def test_the_milestone_defaults_to_none(self):
        """The default is "numbers none", so a caller opts in to a prefix."""
        state = story_state(*_CAST, case=mock_case())

        with patch.object(
            coordinated_story, "close_case_owner_last"
        ) as closure:
            close_the_case(state, others=(REPORTER,))

        assert closure.call_args.kwargs["milestone"] is None


# ---------------------------------------------------------------------------
# The shared join for an invitee whose decision is no branch point
# ---------------------------------------------------------------------------


class TestInviteeJoinsTheCase:
    """One invite chain, and whether an RM triage follows it (CM-11-002)."""

    def test_an_accepting_invitee_triages_after_the_chain(self):
        """A vendor judges the report it was invited over (CM-11-002).

        The triage reads the canonical ledger through the case-actor
        container, not the Coordinator's replica (DEMOMA-06-005).
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())
        seated = (REPORTER, COORDINATOR, VENDOR, _JOINER)

        with _join_stubs() as stubs:
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=seated,
            )

        chain = stubs.chain.call_args.kwargs
        assert chain["then"] is None, (
            "an invitee that triages confirms the roster in its own gate"
        )
        assert chain["invitee_client"] is state.client(_JOINER)
        assert chain["case_manager_client"] is state.case_actor_client
        assert chain["inviter"].role is CVDRole.VENDOR
        assert chain["inviter"].client is state.client(COORDINATOR)

        triage = stubs.triage.call_args.kwargs
        assert triage["invited_client"] is state.client(_JOINER)
        assert triage["auth_client"] is state.case_actor_client
        roster = stubs.roster.call_args.kwargs
        assert roster["expected_actor_ids"] == {
            f"urn:test:{name}" for name in seated
        }
        assert roster["vendor_client"] is state.client(COORDINATOR)

    @pytest.mark.spec("DEMOMA-17-002")
    def test_triages_false_hands_the_roster_check_to_the_chain(self):
        """A coordinator joining to help coordinate runs no RM triage.

        Giving it one would put an ``engage_case`` act in the ledger the
        scenario's semantic-type list does not claim (DEMOMA-17-002).  Its
        roster check then moves inside the chain's own gate, as the chain's
        ``then``, so a failed invite skips it rather than timing out on a
        roster that will never fill (EDF-06-005).
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())
        seated = (REPORTER, COORDINATOR, VENDOR, _JOINER)

        with _join_stubs() as stubs:
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=seated,
                triages=False,
            )
            then = stubs.chain.call_args.kwargs["then"]
            assert then is not None, (
                "the roster check must be handed to the chain as its `then`"
            )
            stubs.roster.assert_not_called()
            then()
            roster = stubs.roster.call_args.kwargs
            assert roster["expected_actor_ids"] == {
                f"urn:test:{name}" for name in seated
            }
            assert roster["vendor_client"] is state.client(COORDINATOR)

        stubs.triage.assert_not_called()
        assert (
            stubs.chain.call_args.kwargs["inviter"].role is CVDRole.COORDINATOR
        )

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_joined_prop_makes_the_roster_a_gate_that_keeps_it(self):
        """A non-triaging joiner whose join the next act presupposes (#5535).

        The two-coordinator pair decides the case's ownership once its second
        Coordinator is a participant (DEMOMA-13-003, DEMOMA-14-010), and a
        flat story cannot nest that decision inside this roster's gate.  So
        the roster becomes the gate and keeps the case id, which the deciding
        fragment reads.  The real ``demo_gate`` runs here: this test is about
        control flow.
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with (
            patch.object(coordinated_story, "wait_for_case_on_container"),
            patch.object(coordinated_story, "run_case_invite_chain") as chain,
            patch.object(coordinated_story, "wait_for_case_participants"),
            patch.object(
                coordinated_story,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=(REPORTER, COORDINATOR, _JOINER),
                triages=False,
                joined=_JOINED,
            )
            chain.call_args.kwargs["then"]()

        assert state.kept(_JOINED) == str(state.case.id_)

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_roster_that_never_fills_keeps_no_prop(self):
        """The gate records the timeout and leaves the prop unkept.

        That is how the dependent fragment stops the story instead of
        suggesting or offering into a case the joiner is not in: it reads the
        prop through an accessor that raises
        (:func:`~vultron.demo.helpers.story.run_story`).
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with (
            patch.object(coordinated_story, "wait_for_case_on_container"),
            patch.object(coordinated_story, "run_case_invite_chain") as chain,
            patch.object(
                coordinated_story,
                "wait_for_case_participants",
                side_effect=AssertionError("roster never filled"),
            ),
            patch.object(
                coordinated_story,
                "demo_step",
                side_effect=lambda _: contextlib.nullcontext(),
            ),
        ):
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=(REPORTER, COORDINATOR, _JOINER),
                triages=False,
                joined=_JOINED,
            )
            chain.call_args.kwargs["then"]()

        with pytest.raises(
            DemoStoryError, match="no case the test joiner joined yet"
        ):
            state.kept(_JOINED)

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_prop_asked_for_on_the_triaging_path_is_refused(self):
        """Only the non-triaging path keeps one, so the pairing raises.

        A triaging invitee's roster is already the gate inside
        ``invitee_triages_after_joining``, and the chain's ``then`` — the only
        place a prop is kept — is not run on that path.  Accepting the
        pairing would leave a prop no step ever keeps, so every fragment that
        read it would stop the story on a healthy run.
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with (
            _join_stubs() as stubs,
            pytest.raises(DemoStoryError, match="triages=True and a prop"),
        ):
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=(REPORTER, COORDINATOR, _JOINER),
                joined=_JOINED,
            )

        stubs.chain.assert_not_called()

    @pytest.mark.spec("CM-17-007")
    def test_the_inviter_defaults_to_the_familys_coordinator(self):
        """Every coordinator-first caller is unchanged by the keyword (#5536).

        Only the Case Owner may invite (CM-17-007), and in this family that is
        the Coordinator.  The default is pinned here so adding *inviter* for
        the vendor-first family cannot quietly move the Invite, the roster
        read or the gate label onto somebody else for the callers that pass
        nothing.
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with _join_stubs() as stubs, _recorded_gates() as labels:
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=(REPORTER, COORDINATOR, VENDOR, _JOINER),
            )

        inviter = stubs.chain.call_args.kwargs["inviter"]
        assert inviter.name == COORDINATOR_LABEL
        assert inviter.client is state.client(COORDINATOR)
        assert inviter.actor is state.actor(COORDINATOR).actor
        assert stubs.roster.call_args.kwargs["vendor_client"] is state.client(
            COORDINATOR
        ), "the default roster read is the Coordinator's own replica"
        assert labels == [
            f"{COORDINATOR_LABEL} case has Joiner before Joiner RM triage"
        ], f"the gate must name the default inviter; got {labels!r}"

    @pytest.mark.spec("CM-17-007")
    def test_a_named_inviter_invites_from_its_own_container(self):
        """The vendor-first family has its first Vendor invite (#5536).

        Only the Case Owner may invite (CM-17-007), and which cast member that
        is differs by family.  Naming one must move all four of the things
        that follow from it: the Invite's sending client, the actor the Invite
        comes from, the replica the roster is read from, and the label that
        tells a reader whose container to look in.
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())
        seated = (REPORTER, VENDOR, _JOINER)

        with _join_stubs() as stubs, _recorded_gates() as labels:
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.VENDOR,
                seated=seated,
                inviter=VENDOR,
                inviter_label="Vendor1",
            )

        inviter = stubs.chain.call_args.kwargs["inviter"]
        assert inviter.client is state.client(VENDOR), (
            "the Invite must be sent from the named inviter's own container"
            " (CM-17-007)"
        )
        assert inviter.actor is state.actor(VENDOR).actor
        assert inviter.name == "Vendor1"
        roster = stubs.roster.call_args.kwargs
        assert roster["vendor_client"] is state.client(VENDOR), (
            "a triaging invitee's roster is read from the named inviter's"
            " replica too, not from the family's Coordinator"
        )
        assert roster["expected_actor_ids"] == {
            f"urn:test:{name}" for name in seated
        }
        assert labels == ["Vendor1 case has Joiner before Joiner RM triage"], (
            f"the gate must name the inviter it waited on; got {labels!r}"
        )

    @pytest.mark.spec("CM-17-007")
    def test_a_named_inviter_also_owns_the_non_triaging_roster_gate(self):
        """The other arm of the join reads the same replica (#5536).

        A non-triaging joiner confirms the roster inside the chain's own
        ``then``, which is a second place the Case Owner is named; a default
        left behind there would wait on the Coordinator's replica for a case
        the first Vendor owns.
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())
        seated = (REPORTER, VENDOR, _JOINER)

        with _join_stubs() as stubs, _recorded_gates() as labels:
            invitee_joins_the_case(
                state,
                _JOINER,
                "Joiner",
                role=CVDRole.COORDINATOR,
                seated=seated,
                triages=False,
                joined=_JOINED,
                inviter=VENDOR,
                inviter_label="Vendor1",
            )
            stubs.chain.call_args.kwargs["then"]()

        assert stubs.roster.call_args.kwargs["vendor_client"] is state.client(
            VENDOR
        )
        assert labels == [
            "Vendor1 case reflects 3 participants after Joiner joined"
        ], f"the gate must name the inviter it waited on; got {labels!r}"
        assert state.kept(_JOINED) == str(state.case.id_)
        stubs.triage.assert_not_called()

    @pytest.mark.spec("DEMOMA-14-005")
    def test_the_triage_roster_is_read_from_the_named_owner(self):
        """A story whose owner changed mid-run names the owner of this step.

        ``invitee_triages_after_joining`` reads the roster from the Case
        Owner's replica, which is the family's Coordinator by default and the
        new owner after an ownership transfer (#5535).
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with _join_stubs() as stubs:
            invitee_triages_after_joining(
                state,
                VENDOR,
                "Vendor",
                seated=(REPORTER, COORDINATOR, _JOINER, VENDOR),
                owner=_JOINER,
                owner_label="Joiner",
            )

        assert stubs.roster.call_args.kwargs["vendor_client"] is state.client(
            _JOINER
        )
        stubs.triage.assert_called_once()

    @pytest.mark.spec("DEMOMA-17-002")
    def test_the_join_logs_the_milestone_the_scenario_numbers_it(self, caplog):
        """The default is the coordinator-first families' ``M2``.

        Every scenario that reached this step before the vendor-first half
        was composed numbers the join M2, so the default keeps their output
        as it was (#5536).
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with caplog.at_level(logging.INFO), _join_stubs():
            invitee_triages_after_joining(
                state,
                _JOINER,
                "Joiner",
                seated=(REPORTER, COORDINATOR, VENDOR, _JOINER),
            )

        assert "✓ M2: Joiner joined case" in caplog.text

    @pytest.mark.spec("DEMOMA-17-002")
    def test_a_scenario_that_numbers_no_join_milestone_logs_none(self, caplog):
        """``milestone=None`` drops the number, not the line.

        ``rvv`` spends M2 on its replica synchronization, so the shared
        step's default would put a second ``✓ M2:`` line in the output
        ``docs/howto/demos/rvv-demo.md`` documents and the two could not be
        told apart (#5536).
        """
        state = story_state(*_CAST, _JOINER, case=mock_case())

        with caplog.at_level(logging.INFO), _join_stubs():
            invitee_triages_after_joining(
                state,
                _JOINER,
                "Joiner",
                seated=(REPORTER, COORDINATOR, VENDOR, _JOINER),
                milestone=None,
            )

        assert "✓ Joiner joined case" in caplog.text
        assert "M2" not in caplog.text


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
                coordinated_story,
                "wait_for_case_on_container",
                side_effect=_wait_for_case,
            ),
            patch.object(
                coordinated_story,
                "run_invite_path_rm_triage",
                side_effect=lambda **_kw: call_order.append("triage"),
            ),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_chain, "reply_to_full_case_invite"),
            patch.object(coordinated_story, "wait_for_case_participants"),
            no_demo_banners(coordinated_story),
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
# The accept arm answers against the canonical case (#5533)
# ---------------------------------------------------------------------------


@pytest.mark.spec("SYNC-10-004")
class TestVendorAcceptsAndJoins:
    """The ledger authority of the accept arm is the case-actor container.

    The full-case reply trigger fails closed until the invitee's own ledger
    copy reaches the Invite's floor, so the chain waits for coverage against
    the container holding the canonical ledger first (SYNC-10-004, ADR-0073,
    DEMOMA-06-005).  A participant's replica is the wrong one to wait on and
    would pass the wait before the entries landed.

    ``rcv`` is the only scenario that reaches this fragment and it is not in
    the PR set (``in_pr_set=False``), so Docker CI exercises the wiring only
    on the full suite; it is pinned here.
    """

    def test_the_full_case_reply_waits_on_the_case_actor_container(self):
        state = story_state(*_CAST, case=mock_case())
        state.invited(VENDOR, "urn:test:invite")

        with (
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
            patch.object(coordinated_story, "run_invite_path_rm_triage"),
            patch.object(ActorSession, "accept_case_invite"),
            patch.object(invite_chain, "reply_to_full_case_invite") as reply,
            patch.object(coordinated_story, "wait_for_case_participants"),
            no_demo_banners(coordinated_story),
        ):
            vendor_accepts_and_joins(state)

        reply.assert_called_once()
        assert (
            reply.call_args.kwargs["authority_client"]
            is state.case_actor_client
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
        state = story_state(*_CAST, case=mock_case())
        # The roster the opening confirmed is this invite's precondition
        # (ENGAGED_CASE); the tests below are about what happens *after* it
        # held, so they stand in for the opening that keeps it.
        state.keep(ENGAGED_CASE, str(state.case.id_))
        with (
            patch.object(
                ActorSession, "invite_actor_to_case", **invite_trigger
            ),
            # Nothing stubs the stub-summary seed here: this directory's
            # conftest no-ops ``invite_chain._seed_stub_summary`` whenever the
            # case-manager client is a mock, and ``story_state`` builds mocks
            # (#5444).
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
            patch_chain_shared(
                coordinated_story, "wait_for_case_on_container"
            ),
            patch.object(coordinated_story, "wait_for_case_participants"),
            patch.object(coordinated_story, "run_invite_path_rm_triage"),
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
        state = story_state(*_CAST, case=mock_case())

        with (
            patch.object(ActorSession, "invite_actor_to_case") as invite,
            patch.object(invite_chain, "find_case_invite_for_actor") as find,
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
        state.keep(ENGAGED_CASE, str(state.case.id_))
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
