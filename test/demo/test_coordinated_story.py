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
Vendor's branch point between them, and the three helpers the continuations
share (``invitee_joins_the_case``, ``close_the_case``,
``dump_coordinated_ledgers``).

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
from collections.abc import Iterator
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
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import coordinated_story, invite_chain
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
    CASE_ACTOR_NAME,
    COORDINATOR,
    ENGAGED_CASE,
    OWNER_TRIAGE_TIMEOUT,
    REPORTER,
    VENDOR,
    CastContainer,
    close_the_case,
    coordinated_clients,
    coordinator_invites_vendor,
    dump_coordinated_ledgers,
    everyone_closes,
    everyone_publishes,
    invitee_joins_the_case,
    open_coordinated_cast,
    reporter_tells_coordinator,
    reporter_then_coordinator_close,
    vendor_accepts_and_joins,
    vendor_rejects_invite,
    vendor_reports_the_fix_ready,
)
from vultron.demo.helpers.story import StoryState, UnseatedContainer
from vultron.demo.utils import case_actor_id_on, reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

_CAST = (REPORTER, COORDINATOR, VENDOR)

#: A character actor this family's continuations bring in mid-story: the second
#: Coordinator of ``rcvcv`` and the second Vendor of ``rcvv-embargo`` are both
#: seated under a name the shared opening never sees.
_JOINER = "joiner"


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
def _no_banners():
    """Make the fragments' own context managers pass-through.

    The tests that use it observe call parameters and ordering, not gate
    control flow.
    """
    with contextlib.ExitStack() as stack:
        for name in ("demo_gate", "demo_check", "demo_step"):
            stack.enter_context(
                patch.object(
                    coordinated_story,
                    name,
                    side_effect=lambda _: contextlib.nullcontext(),
                )
            )
        yield


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
        _no_banners(),
    ):
        yield SimpleNamespace(chain=chain, roster=roster, triage=triage)


def _bind_container_actors(state: StoryState, *names: str) -> None:
    """Bind each named client's ``actor_id``, and the case actor's, as seeding does.

    ``replica_route_key`` reads a dump target's route key off the client's own
    actor id (ADR-0073), and ``seeding._own_actor`` binds it as each
    container's actor is created.  A ``MagicMock`` client carries a truthy
    ``actor_id`` that is not a URI, so without this the real helper would key
    the dump on a mock's repr and a mis-paired client would still look right.
    """
    for name in (*names, CASE_ACTOR_NAME):
        client = (
            state.case_actor_client
            if name == CASE_ACTOR_NAME
            else state.client(name)
        )
        client.actor_id = f"http://{name}:7999/api/v2/actors/{name}"


def _roles() -> dict[str, ActorRole]:
    """The family's three fixed roles plus the dedicated case actor."""
    return role_map(
        [
            ActorRole(REPORTER, REPORTER_SLOT, "Reporter", has_id=True),
            ActorRole(
                COORDINATOR, COORDINATOR_SLOT, "Coordinator", has_id=True
            ),
            ActorRole(VENDOR, VENDOR_SLOT, "Vendor", has_id=True),
            case_actor_role(),
        ]
    )


def _members(
    vendor_url: str | None = None,
) -> list[CastContainer]:
    """The family's three containers in ``ROLES`` order."""
    return [
        CastContainer(REPORTER, "Reporter"),
        CastContainer(COORDINATOR, "Coordinator"),
        CastContainer(VENDOR, "Vendor", vendor_url),
    ]


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
                coordinated_story,
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
                coordinated_story,
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


class TestCoordinatedClients:
    """One client set and one health check for the whole family."""

    def test_each_address_falls_back_to_its_cast_slot(self):
        with patch.object(
            coordinated_story, "check_all_containers"
        ) as checked:
            clients = coordinated_clients(
                _roles(), _members(), skip_health_check=False
            )

        assert sorted(clients) == sorted(
            [REPORTER, COORDINATOR, VENDOR, CASE_ACTOR_NAME]
        )
        assert clients[REPORTER].base_url == REPORTER_SLOT.url
        assert clients[COORDINATOR].base_url == COORDINATOR_SLOT.url
        assert clients[VENDOR].base_url == VENDOR_SLOT.url
        assert clients[CASE_ACTOR_NAME].base_url == CASE_ACTOR.url
        # The case-actor client is bound to the CaseActor its container hosts,
        # so a read through it addresses the canonical store (ADR-0073).
        assert clients[CASE_ACTOR_NAME].actor_id == case_actor_id_on(
            CASE_ACTOR.url
        )
        assert [label for label, _c in checked.call_args.args[0]] == [
            "Reporter",
            "Coordinator",
            "Vendor",
            "CaseActor",
        ]

    def test_an_override_wins_and_the_check_can_be_skipped(self):
        """A ``--<role>-url`` beats the slot, for both kinds of container."""
        case_actor_url = "http://other-case-actor:7999/api/v2"
        with patch.object(
            coordinated_story, "check_all_containers"
        ) as checked:
            clients = coordinated_clients(
                _roles(),
                _members(vendor_url="http://elsewhere:7999/api/v2"),
                skip_health_check=True,
                case_actor_url=case_actor_url,
            )

        assert clients[VENDOR].base_url == "http://elsewhere:7999/api/v2"
        assert clients[REPORTER].base_url == REPORTER_SLOT.url
        # The overridden case-actor client is still bound to the CaseActor of
        # the container it now addresses, not of the slot it left.
        assert clients[CASE_ACTOR_NAME].base_url == case_actor_url
        assert clients[CASE_ACTOR_NAME].actor_id == case_actor_id_on(
            case_actor_url
        )
        checked.assert_not_called()

    def test_a_member_the_roles_do_not_seat_fails_loudly(self):
        """A scenario whose ``ROLES`` and ``main()`` have drifted apart.

        The member's address comes from its cast slot, so a name the role map
        does not hold has no container at all; raising here names the drift,
        where falling back would health-check somebody else's.
        """
        with pytest.raises(KeyError):
            coordinated_clients(
                _roles(),
                [CastContainer("nobody", "Nobody")],
                skip_health_check=True,
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
            mock_vc.model_validate.return_value = case
            reporter_tells_coordinator(state)

        mock_m1.assert_called_once()
        assert (
            triage.call_args.kwargs["timeout_seconds"] == OWNER_TRIAGE_TIMEOUT
        ), (
            "the Coordinator's RM triage runs on the family's one budget"
            f" (ISSUE-2811); got {triage.call_args.kwargs!r}"
        )
        # The fragment hands the case to the state, which arms the dump as
        # soon as there is something to dump (DEMOMA-23-003).
        assert state.case is case
        cast(MagicMock, state.harness).dump_with.assert_called_once()

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


# ---------------------------------------------------------------------------
# The ledger dump, with the devlogs name separate from the cast name
# ---------------------------------------------------------------------------


class TestDumpCoordinatedLedgers:
    """Whose ledger is dumped, under what name, and from whose client."""

    def test_a_pair_names_the_devlogs_directory_and_the_cast_member(self):
        """``(devlogs name, cast name)`` dumps one member under another name.

        ``rcvcv`` calls its Coordinator ``c1`` in its devlogs, which is where
        its invariant harness loads the ledger from, while the story seats it
        under the family's ``coordinator`` (DEMOMA-19-018).  The route key
        stays the actor's own: it selects the store (ADR-0073), so a key taken
        from the devlogs name would read an actor that does not exist and the
        dump would report an empty ledger.
        """
        state = story_state(*_CAST, case=mock_case())
        _bind_container_actors(state, *_CAST)

        with patch.object(coordinated_story, "dump_case_ledgers") as dump:
            dump_coordinated_ledgers(
                state, replicas=[REPORTER, ("c1", COORDINATOR), VENDOR]
            )

        kwargs = dump.call_args.kwargs
        targets = kwargs["targets"]
        assert [t.actor_name for t in targets] == [
            REPORTER,
            "c1",
            VENDOR,
            CASE_ACTOR_NAME,
        ]
        assert [t.route_key for t in targets] == [
            REPORTER,
            COORDINATOR,
            VENDOR,
            CASE_ACTOR_NAME,
        ]
        assert targets[1].client is state.client(COORDINATOR)
        # The canonical ledger is read on the dedicated case-actor container
        # and nowhere else (DEMOMA-06-005).
        assert targets[-1].client is state.case_actor_client
        assert not kwargs["unreplicated"], (
            "nobody acted in this case without a replica to dump"
        )

    def test_an_unreplicated_member_is_named_but_not_dumped(self):
        """A Vendor that rejected its invite was never a participant (#4248).

        It has no replica to export, so it gets no dump target; it is still
        recorded in the manifest, under its own route key, so its entries'
        recorded actor resolves to a name.
        """
        state = story_state(*_CAST, case=mock_case())
        _bind_container_actors(state, *_CAST)

        with patch.object(coordinated_story, "dump_case_ledgers") as dump:
            dump_coordinated_ledgers(
                state,
                replicas=[REPORTER, COORDINATOR],
                unreplicated=(VENDOR,),
            )

        kwargs = dump.call_args.kwargs
        assert [t.actor_name for t in kwargs["targets"]] == [
            REPORTER,
            COORDINATOR,
            CASE_ACTOR_NAME,
        ]
        # ``{manifest name: route key}``; both are the Vendor's own.
        assert kwargs["unreplicated"] == {VENDOR: VENDOR}


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
            _no_banners(),
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
