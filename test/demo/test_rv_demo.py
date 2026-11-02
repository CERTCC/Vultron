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

"""Unit tests for the rv (Reporter + Vendor) two-actor demo (DEMOMA-06, #5536).

``rv`` is written as composition (ADR-0098,
:mod:`vultron.demo.helpers.story`): its opening is the shared
:data:`~vultron.demo.helpers.vendor_story.REPORTER_TELLS_THE_VENDOR` prefix
every vendor-first scenario starts with, and its own story is the continuation
through the replica checks, the note thread and the Vendor's fix
(DEMOMA-06-007).  The checks that used to sit on its ``_phase_*`` functions
therefore sit here on three things:

* the **story's shape** — the path read off its choices, the identity of the
  stretch it shares with its siblings, and the order of its own fragments;
* each of its **own fragments**, driven against a
  :func:`~test.demo._helpers.story_state` stand-in cast, so a test observes
  what the fragment calls;
* the **surfaces around the story** — the cast opening, the ledger dump, the
  CLI option set and the registry entry.

What the shared opening and the shared continuations do is not re-tested here:
they are one copy of the code, and ``test/demo/test_vendor_story.py`` and
``test/demo/test_coordinated_story.py`` own them.  ``demo_gate`` /
``demo_check`` / ``demo_step`` stay real wherever a test is about control flow
and are stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).

The second half of the module exercises the **shared helpers** the scenario
reaches, end to end against a single TestClient (one FastAPI app standing in
for both containers).  Each helper is imported from its real home: the
scenario module holds only its own story, so there is no ``rv_demo`` re-export
to reach them through.  True multi-container isolation is validated by the
acceptance test runnable via::

    docker compose -f docker/docker-compose-multi-actor.yml up \
        --abort-on-container-exit
"""

import contextlib
import json
import logging
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import httpx2 as httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from fastapi.testclient import TestClient

import vultron.demo.scenario.rv_demo as demo
import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    make_client,
    make_testclient_call,
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    seed_replicas_for_case_participants,
    story_state,
    stub_closure_gate,
)
from test.support.case_owner import CASE_OWNER_ID
from vultron.adapters.utils import strip_id_prefix
from vultron.core.states.cs import CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.demo.actor_session import ActorSession
from vultron.demo.cli import main as cli_main
from vultron.demo.helpers import (
    coordinated_story,
    story as story_module,
    story_cast,
    vendor_story,
)
from vultron.demo.helpers.coordinated_story import REPORTER, REPORTER_LABEL
from vultron.demo.helpers.ledger_commit import trigger_log_commit
from vultron.demo.helpers.milestones import verify_case_active
from vultron.demo.helpers.notes import (
    WORKAROUND_ANSWER,
    WORKAROUND_ANSWER_NAME,
    WORKAROUND_QUESTION,
    participant_adds_note_to_case,
)
from vultron.demo.helpers.polling import (
    case_manager_store,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_state,
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
    wait_for_reporter_case,
    wait_for_reporter_log_entry,
)
from vultron.demo.helpers.seeding import get_actor_by_id, seed_containers
from vultron.demo.helpers.story import Choose, choose, run_story, story
from vultron.demo.helpers.sync import verify_replica_state
from vultron.demo.helpers.vendor_story import (
    REPORTER_TELLS_THE_VENDOR,
    REPORTERS_QUESTION,
    THE_VENDORS_CASE,
    VENDOR,
    VENDOR_LABEL,
    VENDORS_ANSWER,
)
from vultron.demo.helpers.verification import (
    _all_fetchable_participants_rm_closed,
)
from vultron.demo.helpers.workflow import (
    receiver_engages_case,
    receiver_validates_report,
    reporter_submits_report,
)
from vultron.demo.scenario.registry import registered_scenarios
from vultron.demo.utils import (
    DataLayerClient,
    case_actor_id_on,
    demo_step,
    read_received_activity,
    reset_demo_failures,
    seed_actor,
    verify_object_stored,
    verify_received_activity_stored,
)
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: The scenario's two actor cast names, in ``ROLES`` order.
_CAST = (REPORTER, VENDOR)

#: How many items of ``STORY`` are the shared vendor-first opening.
_PREFIX_LEN = len(REPORTER_TELLS_THE_VENDOR.items)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    """The base URL of the single TestClient, with the /api/v2 prefix."""
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def configure_vendor_default_roles():
    """Set ``VULTRON_ACTOR__DEFAULT_CASE_ROLES=["vendor"]`` for this module.

    In Docker the vendor container is started with this env var so the Case
    Owner participant gets ``CVDRole.VENDOR`` alongside
    ``CVDRole.CASE_OWNER``.  TestClient does not inherit Docker env vars, so
    the setting is replicated here (it mirrors the vendor service's config in
    ``docker/docker-compose-multi-actor.yml``).
    """
    from vultron.config.app import reload_config

    mp = MonkeyPatch()
    try:
        mp.setenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", '["vendor"]')
        reload_config()
        yield
    finally:
        mp.undo()
        reload_config()


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    """Route every ``DataLayerClient`` call through the one TestClient.

    Patched on the class, so every client a helper builds for itself routes
    through the single app too.  Module-scoped: the patch is applied once and
    torn down after the last test.
    """
    mp = MonkeyPatch()
    try:
        mp.setattr(DataLayerClient, "call", make_testclient_call(client, base))
        yield
    finally:
        mp.undo()


@pytest.fixture(autouse=True)
def _fresh_failures():
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, so a fragment
    that records a failure would otherwise leave it for the next test to read
    as its own (``notes/testing-pitfalls.md``).
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


@contextlib.contextmanager
def _no_banners():
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(demo, coordinated_story, vendor_story):
        yield


def _two_party_state(*, roster_confirmed: bool = True):
    """A story state seating the Reporter and the Vendor, on an open case.

    Args:
        roster_confirmed: Whether the shared opening's roster gate kept
            :data:`THE_VENDORS_CASE`.  Every fragment past that gate reads it,
            so a test of one needs it (DEMOCI-01-011).
    """
    state = story_state(*_CAST, case=mock_case())
    if roster_confirmed:
        state.keep(THE_VENDORS_CASE, str(state.case.id_))
    return state


def _answered_thread(state) -> tuple[as_Note, as_Note]:
    """Keep the two notes the shared opening's thread posts, and return them."""
    question = as_Note(
        id_="urn:test:note-question",
        name="Question from Reporter",
        content=WORKAROUND_QUESTION,
    )
    answer = as_Note(
        id_="urn:test:note-answer",
        name=WORKAROUND_ANSWER_NAME,
        content=WORKAROUND_ANSWER,
    )
    state.keep(REPORTERS_QUESTION, question)
    state.keep(VENDORS_ANSWER, answer)
    return question, answer


# ---------------------------------------------------------------------------
# The story's shape (DEMOMA-06-007, DEMOCI-11-019, DEMOCI-11-024)
# ---------------------------------------------------------------------------


class TestRvStoryShape:
    """``STORY`` places the scenario on the tree, and nothing else does."""

    #: The path ``rv`` declared as ``@scenario(path=...)`` before it was
    #: composed.  The composed form must walk exactly the same tree ending, or
    #: the recordings, the generated index and the invariant harness all move
    #: with it.
    DECLARED_PATH = (
        ("reporter-whom-to-tell", "vendor"),
        ("vendor-after-answer", "report-fix-ready"),
    )

    def test_the_story_walks_the_path_the_scenario_used_to_declare(self):
        """The path is read off the choices, not typed beside them."""
        assert demo.STORY.path == self.DECLARED_PATH, (
            "the composed rv story must walk the path the scenario declared"
            " by hand, or its recordings move (DEMOCI-11-019)"
        )

    @pytest.mark.spec("DEMOMA-06-007")
    def test_the_story_begins_with_the_shared_vendor_first_opening(self):
        """``rv`` starts with the family's prefix object itself.

        DEMOMA-06-007's named verification.  Identity of the shared stretch,
        not merely a matching sequence: the four vendor-first recordings must
        be byte-identical up to the Vendor's decision (DEMOCI-11-018), which
        only holds while the opening is one copy of the code.  Comparing
        against ``REPORTER_TELLS_THE_VENDOR.items`` is what stops a sibling
        slipping a step in before the branch point.
        """
        assert (
            demo.STORY.items[:_PREFIX_LEN] == REPORTER_TELLS_THE_VENDOR.items
        )
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate compares equal and an equality arm would make this loop a
        # second spelling of the tuple comparison above.
        for mine, theirs in zip(
            demo.STORY.items[:_PREFIX_LEN],
            REPORTER_TELLS_THE_VENDOR.items,
            strict=True,
        ):
            assert mine is theirs, (
                "every item of the shared opening must be the same object in"
                " rv's story (DEMOMA-06-007, DEMOCI-11-018)"
            )

    def test_the_opening_ends_with_the_vendor_holding_the_roster(self):
        """The Reporter's choice, then the submission and the triage.

        Nothing of ``rv``'s own runs before the Vendor holds the case and its
        roster; everything after reads :data:`THE_VENDORS_CASE`.
        """
        assert REPORTER_TELLS_THE_VENDOR.items == (
            choose("reporter-whom-to-tell", "vendor", by=REPORTER),
            vendor_story.the_reporter_tells_the_vendor,
        )

    def test_the_continuation_runs_in_the_declared_order(self):
        """One assertion for the whole continuation, so a reordering shows.

        The order is load-bearing: the M1 roster check and the M2 replica
        check read state the note thread then adds to, the final case check
        reads both notes of that thread, and the Vendor decides only once it
        has answered the Reporter (``notes/demo-scenario-registry.md``).
        """
        assert demo.STORY.items[_PREFIX_LEN:] == (
            demo.the_case_is_active,
            demo.the_reporter_replica_converges,
            vendor_story.the_reporter_asks_about_the_workaround,
            demo.the_vendor_holds_the_final_case,
            choose("vendor-after-answer", "report-fix-ready", by=VENDOR),
            demo.the_vendor_reports_the_fix_ready,
            demo.both_publish,
            demo.both_close,
        )

    def test_the_vendors_decision_follows_its_own_answer(self):
        """The branch point falls after the thread, and the Vendor decides."""
        branch = demo.STORY.items[_PREFIX_LEN + 4]
        assert branch == Choose(
            branch_point="vendor-after-answer",
            choice="report-fix-ready",
            by=VENDOR,
        )
        assert (
            demo.STORY.items[_PREFIX_LEN + 2]
            is vendor_story.the_reporter_asks_about_the_workaround
        ), (
            "the vendor-after-answer decision follows the Vendor's own answer"
            " in the thread (DEMOMA-06-007)"
        )

    def test_the_two_are_seated_under_the_family_cast_names(self):
        """One copy of the vendor-first opening serves all four scenarios."""
        assert demo.REPORTER == REPORTER
        assert demo.VENDOR == vendor_story.VENDOR
        # The devlogs and the CLI keep the scenario's own names and labels:
        # ``rv`` has one Vendor, so its ROLES calls it "Vendor" while the
        # shared opening's step labels say "Vendor1".
        assert [role.name for role in demo.ROLES] == [
            "reporter",
            "vendor",
            "case-actor",
        ]
        assert VENDOR_LABEL == "Vendor1"


# ---------------------------------------------------------------------------
# The run's cast: two containers are seeded, three are reset (DEMOCI-11-018)
# ---------------------------------------------------------------------------


class TestRvCast:
    """Every container is reset; the opening seeds the Reporter and Vendor."""

    def _open_the_cast(self, clients, case_actor_client):
        """Run the orchestrator and open its cast, collaborators stubbed.

        ``run_story()`` is what plays the story; the cast opening is the
        callable it is handed, so this runs that and nothing else.
        """
        seeded = [mock_actor(f"urn:test:{name}") for name in _CAST]
        captured = SimpleNamespace()

        with (
            patch.object(demo, "run_story") as run_story,
            patch.object(
                story_cast,
                "reset_datalayer",
                return_value={"status": "ok"},
            ) as reset,
            patch(
                "vultron.demo.helpers.seeding.seed_case_actor_identity"
            ) as reseed,
            patch.object(
                vendor_story, "seed_containers", return_value=tuple(seeded)
            ) as seed_two,
            patch.object(
                story_cast, "get_actor_by_id", side_effect=list(seeded)
            ),
        ):
            demo.run_rv_demo(
                reporter_client=clients[REPORTER],
                vendor_client=clients[VENDOR],
                case_actor_client=case_actor_client,
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
            )
            captured.state = run_story.call_args.args[2](MagicMock())
            captured.run_story = run_story
        return captured, reset, reseed, seed_two

    @pytest.mark.spec("DEMOMA-01-003")
    def test_every_container_is_reset_and_the_case_actor_re_seeded(self):
        """A run starts from a clean baseline on every container it touches.

        The reset wipes the CaseActor identity the Vendor proposes the case
        to, so the dedicated container's identity is re-seeded after its wipe
        (DEMOMA-06-004, #1876).
        """
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()

        _, reset, reseed, _ = self._open_the_cast(clients, case_actor_client)

        assert [c.kwargs["client"] for c in reset.call_args_list] == [
            clients[REPORTER],
            clients[VENDOR],
            case_actor_client,
        ]
        reseed.assert_called_once_with(case_actor_client)

    @pytest.mark.spec("DEMOCI-11-018")
    def test_the_opening_seeds_only_the_reporter_and_vendor_containers(self):
        """Two seats, which is what makes the four recordings match.

        Every actor and peer record the opening writes before the case exists
        is one more read of the recording clock, so a third seeded container
        would move ``rv``'s first ledger entry away from ``rvv``'s and the
        ``rvcv`` pair's (#5532).
        """
        clients = {name: mock_client() for name in _CAST}
        case_actor_client = mock_client()

        captured, _, _, seed_two = self._open_the_cast(
            clients, case_actor_client
        )

        seed_two.assert_called_once()
        seeding = seed_two.call_args.kwargs
        assert seeding["reporter_client"] is clients[REPORTER]
        assert seeding["vendor_client"] is clients[VENDOR]
        assert seeding["case_actor_client"] is case_actor_client
        assert seeding["reporter_actor_id"] == "urn:test:reporter"
        assert seeding["vendor_actor_id"] == "urn:test:vendor"

        state = captured.state
        assert sorted(state.cast) == sorted(_CAST), (
            "the opening seats exactly the Reporter and the Vendor; a third"
            " seat would move the shared recording (DEMOCI-11-018)"
        )
        assert state.unseated == {}, (
            "rv brings in no character actor, so it declares no unseated"
            " container"
        )
        assert state.case_actor_client is case_actor_client

    def test_the_run_plays_this_scenarios_story_under_its_own_name(self):
        """``run_story(name, plot, open_cast)`` names the registered demo."""
        clients = {name: mock_client() for name in _CAST}

        captured, _, _, _ = self._open_the_cast(clients, mock_client())

        run_story = captured.run_story
        assert run_story.call_args.args[0] == "rv"
        assert run_story.call_args.args[1] is demo.STORY

    def test_the_cast_opening_arms_this_scenarios_ledger_dump(self):
        """DEMOMA-23-003: armed when the case opens, and exactly once."""
        clients = {name: mock_client() for name in _CAST}

        captured, _, _, _ = self._open_the_cast(clients, mock_client())
        state = captured.state

        assert state.dump is demo._dump_ledgers
        state.open_case(
            case=mock_case(), report=MagicMock(), offer=MagicMock()
        )
        cast(MagicMock, state.harness.dump_with).assert_called_once()


# ---------------------------------------------------------------------------
# M1: the Reporter and the Vendor are seated (DEMOMA-06-002 step 1)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-06-002")
class TestTheCaseIsActive:
    """``rv`` numbers the shared roster check M1 and names its participants."""

    def test_the_fragment_numbers_the_milestone_m1(self):
        """The reads are the family's; the milestone number is rv's."""
        state = _two_party_state()

        with patch.object(
            demo, "required_participants_are_present"
        ) as present:
            demo.the_case_is_active(state)

        present.assert_called_once()
        assert present.call_args.args == (state,)
        check = present.call_args.kwargs["check"]
        assert check.startswith("M1: "), check
        assert "EM.ACTIVE" in check
        assert "reporter has case replica" in check

    def test_the_check_reads_the_vendor_and_reporter_replicas(self):
        """The real shared continuation runs, so the clients are checked."""
        state = _two_party_state()

        with (
            patch.object(vendor_story, "verify_case_active") as active,
            _no_banners(),
        ):
            demo.the_case_is_active(state)

        active.assert_called_once()
        kwargs = active.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)


# ---------------------------------------------------------------------------
# M2: the replica check this scenario alone tells (DEMOMA-06-004, #1434)
# ---------------------------------------------------------------------------


class TestTheReporterReplicaConverges:
    """The sync phase goes through the one shared coverage helper.

    DEMOMA-23-005 and DEMOMA-23-006: the
    read-authority-tail-then-poll-each-replica loop lives in
    ``vultron/demo/helpers/sync.py`` and nowhere else (#3906).  ``rv`` is the
    only scenario of its family that tells this step, and it tells it between
    the shared opening and the shared note thread: it reads replicas and
    writes nothing, so it moves no byte of the recording its siblings must
    match (DEMOCI-11-018).
    """

    def test_the_vendor_is_the_authority_and_the_reporter_the_one_replica(
        self,
    ):
        """One replica, state-checked against the Vendor's own container."""
        state = _two_party_state()

        with (
            patch.object(demo, "run_sync_verification_phase") as sync,
            patch.object(demo, "verify_case_actor_holds_records"),
            _no_banners(),
        ):
            demo.the_reporter_replica_converges(state)

        sync.assert_called_once()
        kwargs = sync.call_args.kwargs
        assert kwargs["auth_client"] is state.client(VENDOR)
        assert kwargs["auth_label"] == VENDOR_LABEL
        assert kwargs["auth_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)
        assert kwargs["replicas"] == [(state.client(REPORTER), REPORTER_LABEL)]
        assert kwargs["state_checks"] == [
            (state.client(REPORTER), REPORTER_LABEL)
        ]
        assert kwargs["case_id"] == state.case.id_
        # Replication is verified by comparing replica state, never by
        # polling for a synthetic checkpoint entry the canonical ledger
        # excludes (ADR-0019, CLP-07-004, #1434).
        assert "late_joiners" not in kwargs

    @pytest.mark.spec("DEMOMA-06-004")
    def test_the_canonical_records_are_read_on_the_dedicated_container(self):
        """No participant replica holds them, so the read goes there.

        The case-actor read comes after the sync phase: a replica that never
        converged is the earlier failure, and the canonical read would only
        add a second one.
        """
        state = _two_party_state()
        order: list[str] = []

        with (
            patch.object(
                demo,
                "run_sync_verification_phase",
                side_effect=lambda **_kw: order.append("sync"),
            ),
            patch.object(
                demo,
                "verify_case_actor_holds_records",
                side_effect=lambda *a: order.append("canonical"),
            ) as canonical,
            _no_banners(),
        ):
            demo.the_reporter_replica_converges(state)

        assert order == ["sync", "canonical"]
        assert canonical.call_args.args == (
            state.case_actor_client,
            state.case.id_,
        )


# ---------------------------------------------------------------------------
# M3: the final case state, with both notes of the thread on it
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-06-002")
class TestTheVendorHoldsTheFinalCase:
    """The check names the question and the answer, never ``None`` twice."""

    def test_both_notes_of_the_shared_thread_reach_the_case_check(self):
        """The point of the fragment: two kept props, two note ids.

        An earlier version of this check passed ``None`` for both note ids,
        which made ``verify_receiver_case_state`` skip the note assertions
        altogether — so the scenario claimed M3 while proving nothing about
        the thread it had just posted (DEMOCI-11-017).
        """
        state = _two_party_state()
        question, answer = _answered_thread(state)

        with (
            patch.object(demo, "verify_receiver_case_state") as final,
            _no_banners(),
        ):
            demo.the_vendor_holds_the_final_case(state)

        final.assert_called_once()
        kwargs = final.call_args.kwargs
        # Both ids, not None: `_assert_case_notes` skips a note it is given
        # `None` for, so the check would pass over the thread entirely.  The
        # props carry real `as_Note`s, so a non-None id is what each equality
        # below asserts (DEMOCI-11-017).
        assert question.id_ and answer.id_
        assert kwargs["question_note_id"] == question.id_
        assert kwargs["reply_note_id"] == answer.id_

    def test_the_authoritative_case_is_read_on_the_vendors_container(self):
        """The Vendor is CASE_OWNER throughout (DEMOMA-06-002)."""
        state = _two_party_state()
        _answered_thread(state)

        with (
            patch.object(demo, "verify_receiver_case_state") as final,
            _no_banners(),
        ):
            demo.the_vendor_holds_the_final_case(state)

        kwargs = final.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(VENDOR)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["report_id"] == state.report.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(VENDOR)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)

    def test_a_thread_that_never_landed_stops_the_story_here(self):
        """DEMOCI-01-011: no note to name means no M3 claim to make."""
        state = _two_party_state()

        with (
            patch.object(demo, "verify_receiver_case_state") as final,
            pytest.raises(DemoStoryError, match="workaround question"),
            _no_banners(),
        ):
            demo.the_vendor_holds_the_final_case(state)

        final.assert_not_called()


# ---------------------------------------------------------------------------
# M4/M5: the Vendor's fix (CSB-15-002, CSB-18-001)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-06-002")
class TestTheVendorReportsTheFixReady:
    """The Vendor reports fix ready and stops at VFd."""

    def test_the_fragment_names_the_vendor_and_a_follow_on(self):
        """The trigger and its gate are the family's; the casting is rv's."""
        state = _two_party_state()

        with patch.object(demo, "vendor_notifies_fix_ready") as notify:
            demo.the_vendor_reports_the_fix_ready(state)

        notify.assert_called_once()
        assert notify.call_args.args == (state, VENDOR, VENDOR_LABEL)
        assert callable(notify.call_args.kwargs["then"]), (
            "the M4/M5 milestones run inside the trigger's own gate, so a"
            " refused trigger skips them (CSB-18-001, DEMOCI-01-011)"
        )

    def test_the_reporter_replica_is_polled_before_the_milestones(self):
        """The milestones nest inside a gate on the Reporter's replica.

        Both milestone labels are this scenario's; the check they make is the
        family's one copy (``the_fix_ready_reached_the_reporter``), told twice
        under two numbers as the hand-written form told it (DEMOMA-17-002,
        #5607).
        """
        state = _two_party_state()
        order: list[str] = []

        with (
            patch.object(coordinated_story, "wait_for_participant_rm_state"),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(
                ActorSession,
                "notify_fix_ready",
                autospec=True,
                side_effect=lambda _session: order.append("notify"),
            ),
            patch.object(
                demo,
                "wait_for_participant_vf_state",
                side_effect=lambda **kw: order.append("reporter_vf"),
            ) as reporter_vf,
            patch.object(
                demo,
                "the_fix_ready_reached_the_reporter",
                side_effect=lambda *a, **kw: order.append("milestones"),
            ) as milestones,
            _no_banners(),
        ):
            demo.the_vendor_reports_the_fix_ready(state)

        assert order == ["notify", "reporter_vf", "milestones"]
        kwargs = reporter_vf.call_args.kwargs
        assert kwargs["client"] is state.client(REPORTER)
        assert kwargs["actor_id"] == state.actor_id(VENDOR)
        assert kwargs["expected_states"] == {CS_vf.VF}
        assert milestones.call_args.kwargs["milestones"] == (
            "M4: both replicas show CS includes F (fix ready)",
            "M5: both replicas show CS includes F (fix ready) — vendor"
            " stops at VFd",
        )

    def test_a_replica_that_never_catches_up_skips_the_milestones(self):
        """One GATE FAILED, not two CHECK FAILEDs (#2361, ADR-0058).

        The real ``demo_gate`` runs: the milestones read state the Reporter's
        replica never received, so they are skipped rather than compared.
        """
        state = _two_party_state()

        with (
            patch.object(coordinated_story, "wait_for_participant_rm_state"),
            patch.object(coordinated_story, "wait_for_participant_vf_state"),
            patch.object(ActorSession, "notify_fix_ready"),
            patch.object(
                demo,
                "wait_for_participant_vf_state",
                side_effect=AssertionError("Timed out waiting for vfd_state"),
            ),
            patch.object(demo, "the_fix_ready_reached_the_reporter") as later,
        ):
            demo.the_vendor_reports_the_fix_ready(state)

        later.assert_not_called()
        assert len(demo_utils._demo_failures) == 1, (
            "a single replication timeout records one GATE FAILED; more than"
            " one is the cascade #2361 removed"
        )
        assert "GATE FAILED" in demo_utils._demo_failures[0]


# ---------------------------------------------------------------------------
# M6: publication and embargo teardown (DEMOMA-07-003)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-07-003")
class TestBothPublish:
    """The Vendor, as CASE_OWNER, publishes first; then the Reporter."""

    def test_the_owner_publishes_then_the_reporter_and_the_embargo_ends(self):
        """DEMOMA-07-003(4): the Case Owner's notify-published ends it.

        The embargo termination is read on the Vendor's replica between the
        two publications, because the Reporter's own publication is what the
        final milestone then checks on the Reporter's.
        """
        state = _two_party_state()
        order: list[str] = []

        with (
            patch.object(
                demo,
                "reports_published",
                side_effect=lambda _s, name: order.append(f"published:{name}"),
            ),
            patch.object(
                demo,
                "the_embargo_ends_for",
                side_effect=lambda _s, **kw: order.append(
                    f"em_exited:{kw['watcher']}"
                ),
            ) as embargo,
            patch.object(
                demo,
                "the_disclosure_reached_every_replica",
                side_effect=lambda _s, **kw: order.append("m6"),
            ) as disclosed,
            _no_banners(),
        ):
            demo.both_publish(state)

        assert order == [
            f"published:{VENDOR}",
            f"em_exited:{VENDOR}",
            f"published:{REPORTER}",
            "m6",
        ]
        assert "EM.EXITED" in embargo.call_args.kwargs["check"]
        assert disclosed.call_args.kwargs["check"].startswith("M6: ")

    def test_the_real_order_is_the_vendor_then_the_reporter(self):
        """The shared steps run for real, so the casting is checked by effect.

        A swapped owner would publish the Reporter first and the embargo
        teardown would be awaited after the wrong trigger.
        """
        state = _two_party_state()
        published: list[str] = []

        with (
            patch.object(vendor_story, "wait_for_case_em_terminated"),
            patch.object(vendor_story, "wait_for_participant_vf_state"),
            patch.object(vendor_story, "verify_publicly_disclosed"),
            patch.object(
                ActorSession,
                "notify_published",
                autospec=True,
                side_effect=lambda session: published.append(
                    session.actor.id_
                ),
            ),
            _no_banners(),
        ):
            demo.both_publish(state)

        assert published == [
            state.actor_id(VENDOR),
            state.actor_id(REPORTER),
        ]


# ---------------------------------------------------------------------------
# M7: case closure (CM-23-015)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-23-015")
class TestBothClose:
    """The Reporter leaves; the Vendor, the Case Owner, leaves last."""

    def test_the_vendor_is_the_owner_and_leaves_after_the_reporter(self):
        """A Leave after the case is fully closed records nothing (CM-23-013)."""
        state = _two_party_state()

        with patch.object(demo, "close_the_case") as closure:
            demo.both_close(state)

        closure.assert_called_once()
        assert closure.call_args.args == (state,)
        assert closure.call_args.kwargs == {
            "others": (REPORTER,),
            "owner": VENDOR,
            "milestone": "M7",
        }

    def test_the_departures_are_read_on_the_dedicated_case_actor(self):
        """The owner's ``Leave`` is gated on the CASE_MANAGER's store.

        That store lives on the dedicated case-actor container
        (DEMOMA-06-005), so the authority client must be that one and never
        the Vendor's own.
        """
        state = _two_party_state()

        with (
            patch.object(ActorSession, "leave_case"),
            stub_closure_gate(),
            patch.object(
                coordinated_story, "close_case_owner_last"
            ) as closure,
        ):
            demo.both_close(state)

        kwargs = closure.call_args.kwargs
        assert kwargs["milestone"] == "M7"
        assert kwargs["authority_client"] is state.case_actor_client
        assert [leaver.client for leaver in kwargs["others"]] == [
            state.client(REPORTER)
        ]
        assert kwargs["owner"].client is state.client(VENDOR)
        assert kwargs["owner"].actor is state.actor(VENDOR).actor


# ---------------------------------------------------------------------------
# A roster that never fills stops the story (DEMOCI-01-011, #5536)
# ---------------------------------------------------------------------------


class TestARosterThatNeverFillsStopsTheStory:
    """The guarantee the hand-placed form got from nesting.

    Before composition the M1 check sat inside the roster wait's own
    ``demo_gate``, so a roster that never filled skipped it.  A flat story
    cannot nest, so the roster gate keeps :data:`THE_VENDORS_CASE` and
    ``the_case_is_active`` reads it — and the runner stops the story at the
    unreadable prop.  Driven through the real ``run_story``, the real
    ``demo_gate`` and the real fragments, because every link of that chain is
    load-bearing and a test of any one of them alone is what let the same
    guarantee go missing in the coordinator-first pair (#5535).
    """

    @pytest.fixture
    def marks(self, monkeypatch: MonkeyPatch):
        """Stand in for ``scenario_harness``, which needs a real case."""
        reset_demo_failures()
        harness = MagicMock()
        harness.demo_name = "rv"

        @contextlib.contextmanager
        def stub(_demo_name: str):
            yield harness

        monkeypatch.setattr(story_module, "scenario_harness", stub)
        yield harness
        reset_demo_failures()

    @contextlib.contextmanager
    def _roster(self, case, *, fills: bool):
        """Run the opening with its roster filling or timing out.

        The roster gate in ``vendor_story`` and the prop read in
        ``required_participants_are_present`` are the subject, so both stay
        real.  Everything that talks to a container is stubbed: left real each
        would poll a ``MagicMock`` store for its whole budget and buy no
        assertion.
        """
        with (
            patch.object(
                vendor_story,
                "reporter_submits_report",
                return_value=(
                    MagicMock(id_="urn:test:report"),
                    MagicMock(id_="urn:test:offer"),
                ),
            ),
            patch.object(
                vendor_story, "run_direct_path_rm_triage", return_value=case
            ),
            patch.object(vendor_story, "await_reporter_case_replica"),
            patch.object(
                vendor_story,
                "wait_for_case_participants",
                side_effect=None
                if fills
                else AssertionError("roster never filled"),
            ),
            patch.object(vendor_story, "as_VulnerabilityCase") as mock_vc,
            patch.object(vendor_story, "verify_case_active") as active,
        ):
            mock_vc.model_validate.return_value = case
            yield active

    def _play(self, state) -> None:
        run_story(
            "rv",
            story(
                vendor_story.the_reporter_tells_the_vendor,
                demo.the_case_is_active,
            ),
            lambda _harness: state,
        )

    def test_a_timed_out_roster_leaves_the_m1_check_unmade(self, marks):
        """The M1 check never runs, and the roster is the one failure."""
        state = story_state(*_CAST)
        case = mock_case()

        with self._roster(case, fills=False) as active:
            self._play(state)

        active.assert_not_called()
        with pytest.raises(
            DemoStoryError, match="case whose roster the Vendor confirmed"
        ):
            state.kept(THE_VENDORS_CASE)
        assert len(demo_utils._demo_failures) == 2, (
            "the roster gate records one failure and the stopped fragment"
            " records the stop; a third is a cascade (DEMOCI-01-011)"
        )

    def test_a_filled_roster_lets_the_m1_check_run(self, marks):
        """The counterpart, so the test above is not vacuous."""
        state = story_state(*_CAST)
        case = mock_case()

        with self._roster(case, fills=True) as active:
            self._play(state)

        assert state.kept(THE_VENDORS_CASE) == str(case.id_)
        active.assert_called_once()
        assert active.call_args.kwargs["receiver_client"] is state.client(
            VENDOR
        )


# ---------------------------------------------------------------------------
# The devlogs the invariant harness reads (DEMOMA-06-005, DEMOMA-23-002)
# ---------------------------------------------------------------------------


def _bound_client(slug: str) -> MagicMock:
    """A dump client stub bound to a *generated* actor id, as the real one is.

    ``actor_id`` must be a real string: the dump derives its route key from it
    (``replica_route_key``, ADR-0073) and writes the key into the manifest, so
    a bare ``MagicMock()`` leaves an unserialisable object there.  The ids are
    deliberately *not* the docker-compose seed names — that is the whole point
    of deriving the key, and a stub carrying ``actor_id="reporter"`` would
    pass even if the derivation were dropped.
    """
    client = MagicMock()
    client.actor_id = f"https://example.org/actors/{slug}"
    client.get_list.return_value = [{"logIndex": 0}]
    return client


class TestRvLedgerDump:
    """Each replica is dumped under this scenario's own name for it."""

    def _state_for_dump(self, case):
        """A story state whose clients are dump-ready, on *case*.

        Built rather than adapted: an ``ActorSession`` is frozen, so a bound
        client has to be the one the session is made with.
        """
        slugs = {REPORTER: "reporter-9f3a", VENDOR: "vendor-8ade"}
        state = story_module.StoryState(
            cast={
                name: ActorSession(
                    client=_bound_client(slug),
                    actor=mock_actor(f"urn:test:{name}"),
                )
                for name, slug in slugs.items()
            },
            case_actor_client=_bound_client("case-actor"),
            harness=MagicMock(demo_name="rv"),
            dump=lambda _state: None,
        )
        state.open_case(case=case, report=MagicMock(), offer=MagicMock())
        return state

    def test_the_dump_names_the_two_replicas_in_order(self):
        """DEMOMA-23-002: the fragment only says whose ledgers to dump."""
        state = _two_party_state()

        with patch.object(vendor_story, "dump_coordinated_ledgers") as dump:
            demo._dump_ledgers(state)

        dump.assert_called_once()
        assert dump.call_args.args == (state,)
        assert dump.call_args.kwargs["replicas"] == [REPORTER, VENDOR]

    def test_the_dump_writes_one_file_per_actor_under_the_demo_name(
        self, tmp_path, monkeypatch
    ):
        """Three devlogs directories, each keyed on its client's actor id."""
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rv-test-case",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        demo._dump_ledgers(self._state_for_dump(case))

        case_slug = "https_example.org_cases_rv-test-case"
        for devlogs_name in (REPORTER, VENDOR, "case-actor"):
            assert (
                tmp_path
                / "rv"
                / devlogs_name
                / f"{case_slug}-case-ledger.jsonl"
            ).exists(), devlogs_name

        # The route key selects the store (ADR-0073), so it must be the
        # client's own actor id — not the seed name the directory is named
        # after.
        manifest = json.loads(
            (tmp_path / "rv" / "dump-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        keys = {r["actorName"]: r["routeKey"] for r in manifest["actors"]}
        assert keys == {
            "reporter": "reporter-9f3a",
            "vendor": "vendor-8ade",
            "case-actor": "case-actor",
        }

    @pytest.mark.spec("DEMOMA-06-005")
    def test_the_canonical_ledger_is_read_on_the_dedicated_container(
        self, tmp_path, monkeypatch
    ):
        """The CaseActor is not a sub-actor of the Vendor's container.

        No fallback to a participant's container: a participant holds a
        replica, and dumping that as ``case-actor`` would hide exactly the
        topology fault this target exists to expose.
        """
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rv-with-ca",
            actor_participant_index={
                "https://example.org/actors/case-actor": (
                    "https://example.org/cases/rv-with-ca"
                    "/participants/case-actor"
                )
            },
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        state = self._state_for_dump(case)

        demo._dump_ledgers(state)

        canonical = cast(MagicMock, state.case_actor_client.get_list)
        vendor_reads = cast(MagicMock, state.client(VENDOR).get_list)
        assert any(
            "/actors/case-actor/demo/cases/rv-with-ca/log" in call.args[0]
            for call in canonical.call_args_list
        )
        assert not any(
            "/actors/case-actor/" in call.args[0]
            for call in vendor_reads.call_args_list
        )

    def test_an_empty_canonical_ledger_is_not_replaced_by_a_replica(
        self, tmp_path, monkeypatch
    ):
        """It is recorded as not captured instead of filled from a replica."""
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/rv-empty-ca",
        )
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        state = self._state_for_dump(case)
        cast(MagicMock, state.case_actor_client.get_list).return_value = []

        demo._dump_ledgers(state)

        manifest = json.loads(
            (tmp_path / "rv" / "dump-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        record = next(
            a for a in manifest["actors"] if a["actorName"] == "case-actor"
        )
        assert record["captured"] is False


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOCI-11-019)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rv --help`` as the generated sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rv", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


class TestRvCliCommand:
    """The generated sub-command offers one option per container."""

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--vendor-url",
            "--case-actor-url",
            "--reporter-id",
            "--vendor-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per actor, plus the health skip."""
        assert option in help_text

    def test_the_case_actor_carries_no_id_option(self, help_text: str):
        """Only ``rccv-handoff`` exposes one (DEMOMA-14-008)."""
        assert "--case-actor-id" not in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in ("reporter", "vendor", "case-actor")
        }

        with (
            patch.object(
                demo, "coordinated_clients", return_value=clients
            ) as built,
            patch.object(demo, "run_rv_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                vendor_url="http://elsewhere:7999/api/v2",
                case_actor_url="http://ca:7999/api/v2",
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
            )

        members = built.call_args.args[1]
        assert [(m.role, m.label) for m in members] == [
            ("reporter", "Reporter"),
            ("vendor", "Vendor"),
        ]
        assert [m.url for m in members] == [
            None,
            "http://elsewhere:7999/api/v2",
        ]
        assert built.call_args.kwargs["skip_health_check"] is True
        # The CaseActor's own container is addressed through its override,
        # never through the Vendor's (DEMOMA-06-004).
        assert (
            built.call_args.kwargs["case_actor_url"] == "http://ca:7999/api/v2"
        )

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["vendor_client"] is clients["vendor"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["reporter_id"] == "urn:test:reporter"
        assert kwargs["vendor_id"] == "urn:test:vendor"

    def test_the_cli_runs_the_demo_with_the_case_actor_override(
        self, base: str
    ):
        """End to end through click, so the option wiring is checked."""
        case_actor_url = f"{base}/case-actor"
        patched_run = MagicMock()

        with patch.object(demo, "run_rv_demo", patched_run):
            result = CliRunner().invoke(
                cli_main,
                [
                    "rv",
                    "--skip-health-check",
                    "--reporter-url",
                    base,
                    "--vendor-url",
                    base,
                    "--case-actor-url",
                    case_actor_url,
                    "--reporter-id",
                    f"{base}/actors/reporter-cli-test",
                    "--vendor-id",
                    f"{base}/actors/vendor-cli-test",
                ],
            )

        assert result.exit_code == 0, result.output
        patched_run.assert_called_once()
        assert (
            patched_run.call_args.kwargs["case_actor_client"].base_url
            == case_actor_url
        )


@pytest.fixture
def spec():
    """The one registry entry named ``rv``."""
    entries = [s for s in registered_scenarios() if s.name == "rv"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRvRegistryEntry:
    """The registry is the sole declaration that ``rv`` exists."""

    def test_the_entry_describes_the_baseline_two_actor_scenario(self, spec):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "rv"
        assert spec.participants == "Reporter + Vendor"
        assert spec.feature == "Baseline two-actor CVD"
        assert spec.in_pr_set is True

    def test_the_path_is_read_off_the_story(self, spec):
        """``composed=True`` is what tells a check it places no step marks."""
        assert spec.composed is True
        assert spec.path == demo.STORY.path

    def test_the_derived_paths_point_at_this_module_and_its_harness(
        self, spec
    ):
        """Every artifact path derives from the name (DEMOCI-11-003)."""
        assert spec.demo_path == "vultron/demo/scenario/rv_demo.py"
        assert spec.harness_path == (
            "test/ci/invariants/test_rv_invariants.py"
        )


def test_cli_help_phases_match_tutorial() -> None:
    """``CLI_HELP`` names the same phases, in order, as the tutorial.

    Guards against the two hand-written step lists drifting apart (#3853).
    """
    import re
    from pathlib import Path

    tutorial = Path(__file__).parents[2] / "docs" / "tutorials" / "rv-demo.md"
    titles = re.findall(
        r"^### Phase \d+ — (.+?) \(M\d+(?:–M\d+)?\)$",
        tutorial.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert len(titles) >= 6, "tutorial phase headings not found"
    positions = [demo.CLI_HELP.find(t) for t in titles]
    assert all(p >= 0 for p in positions), (titles, positions)
    assert positions == sorted(positions)
    assert "invite" not in demo.CLI_HELP.lower().replace("never invited", "")


# ===========================================================================
# The shared helpers the scenario reaches, end to end
# ===========================================================================
# Each is imported from its real home: the scenario module holds only its own
# story, so these are not reached through an ``rv_demo`` re-export (#5536).


def _extract_offer_ids(
    client: DataLayerClient, offer: as_Offer
) -> tuple[str | None, str | None]:
    """Return ``(report_id, reporter_id)`` extracted from *offer*'s raw data.

    The Offer is read from the receiver's archive record, the only copy it
    keeps of a received activity (DL-06-006).
    """
    offer_data = read_received_activity(client, offer.id_)
    if not offer_data:
        return None, None
    report_id = None
    reporter_id = None
    obj_ = offer_data.get("object_") or offer_data.get("object")
    if isinstance(obj_, dict):
        report_id = obj_.get("id_") or obj_.get("id")
    elif isinstance(obj_, str):
        report_id = obj_
    act_ = offer_data.get("actor")
    if isinstance(act_, dict):
        reporter_id = act_.get("id") or act_.get("id_")
    elif isinstance(act_, str):
        reporter_id = act_
    return report_id, reporter_id


def _find_case_for_report(
    client: DataLayerClient, report_id: str | None
) -> str | None:
    """Return the case id linked to *report_id*, or ``None`` if not found."""
    cases_data = client.get(client.dl_path("VulnerabilityCases/"))
    if not cases_data or not report_id:
        return None
    for cid in cases_data:
        case_data = client.get(client.dl_path(cid))
        if not case_data:
            continue
        reports = (
            case_data.get("vulnerabilityReports")
            or case_data.get("vulnerability_reports")
            or []
        )
        for r in reports:
            r_id = r if isinstance(r, str) else (r.get("id_") or r.get("id"))
            if r_id == report_id:
                return str(cid)
    return None


def _create_case_from_offer(
    client: DataLayerClient,
    actor: as_Actor,
    offer: as_Offer,
    dl=None,
) -> as_VulnerabilityCase:
    """Return a case with *actor* as its CASE_OWNER + VENDOR participant.

    Under ADR-0041, validate-report sends a CaseProposal to the CaseActor but
    the round-trip does not always complete here.  This helper creates the
    case via trigger/create-case and then seeds the actor as CASE_OWNER +
    VENDOR participant directly in the DataLayer so that downstream BT nodes
    (CheckVendorRoleNode, ResolveCaseManagerNode, …) find the expected
    participant state.

    This docstring used to blame "nested ASGI delivery is blocked at depth > 0
    to prevent deadlocks".  That is not so: nothing implements such a guard,
    and ``InProcessRouter`` dispatches each POST via
    ``anyio.to_thread.run_sync`` precisely so nested sends cannot deadlock —
    multi-hop deliveries are observably completing with 202s.  What actually
    stops the round-trip is ordinary bugs in what the sender queues, so do not
    treat the incompleteness here as a fixed property of the harness.

    Args:
        client: DataLayerClient for the vendor container.
        actor: The vendor actor that will be the CASE_OWNER.
        offer: The Offer activity whose report id links to the case.
        dl: Store to seed into.  Defaults to *actor*'s own store, which is the
            one the downstream BTs read, since a tree executes against the
            store of the actor it runs as (BT-05-005).  There is no shared
            module-level DataLayer to fall back on any more (ADR-0073), so
            leaving this ``None`` used to seed nothing and fail later with
            ``'NoneType' has no attribute 'read'``.

    Returns:
        The case with *actor* registered as CASE_OWNER + VENDOR.
    """
    from vultron.demo.helpers.seeding import seed_case_participants_for_demo

    if dl is None:
        from vultron.adapters.driven.datalayer_sqlite import get_datalayer

        dl = get_datalayer(actor.id_)

    report_id, reporter_id = _extract_offer_ids(client, offer)

    # Under ADR-0041, validate-report triggers CaseProposal → CaseActor.
    # When delivery works (e.g. InProcessRouter in isolated tests), the case
    # is created by the CaseActor before we get here.  Detect that and skip
    # trigger/create-case to avoid creating a duplicate case.
    case_id = _find_case_for_report(client, report_id)

    if not case_id:
        # The CaseProposal round-trip has not completed.  Not because nested
        # delivery is blocked — no such guard exists, see the note on this
        # helper's docstring — so treat this fallback as covering a *bug*, not
        # a property of the harness.  Create the case manually.
        actor_slug = (
            actor.id_.rstrip("/").rsplit("/", 1)[-1] if actor.id_ else ""
        )
        body: dict[str, Any] = {
            "name": "Test case",
            "content": "Created by _create_case_from_offer for test setup.",
            "report_id": report_id,
        }
        if reporter_id:
            body["to"] = [reporter_id]
        resp = client.post(
            f"/actors/{actor_slug}/trigger/create-case",
            json=body,
        )
        assert resp is not None, "trigger/create-case returned no response"
        case_id = _find_case_for_report(client, report_id)

    if not case_id:
        # Last resort: take the most-recent case (no report linkage found).
        cases_data = client.get(client.dl_path("VulnerabilityCases/"))
        assert cases_data, "No VulnerabilityCases found"
        case_id = next(reversed(cases_data))

    # Seed vendor, reporter and CaseActor participants directly.  Under
    # ADR-0041 the CaseActor normally creates these when it accepts a
    # CaseProposal; the round-trip does not always complete here.
    seed_case_participants_for_demo(
        case_id=case_id,
        vendor_actor_id=actor.id_,
        reporter_actor_id=reporter_id,
        report_id=report_id,
        dl=dl,
    )

    # Give every other participant — the CaseActor above all — its own
    # replica.  A BT runs against the store of the actor executing it
    # (BT-05-005), so the CaseActor cannot commit a ledger entry for a case
    # its own store does not hold: it fails to derive the per-case genesis
    # hash and the commit is refused (CLP-08-005).
    seed_replicas_for_case_participants(dl, str(case_id))

    case_data = client.get(client.dl_path(case_id))
    return as_VulnerabilityCase.model_validate(case_data)


class TestSeedContainers:
    """``seed_containers`` creates the two actors and registers them as peers.

    Imported from ``vultron.demo.helpers.seeding``: the fragment that calls it
    is ``vendor_story.open_vendor_cast``, whose two-seat shape is
    ``TestRvCast``'s subject (DEMOCI-11-018).
    """

    def test_seed_containers_creates_reporter_actor(
        self, client: TestClient, base: str
    ):
        reporter, _vendor = seed_containers(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert reporter.id_ is not None
        assert reporter.name == "Reporter"

    def test_seed_containers_creates_vendor_actor(
        self, client: TestClient, base: str
    ):
        _reporter, vendor = seed_containers(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
        )
        assert vendor.id_ is not None
        assert vendor.name == "Vendor"

    def test_seed_containers_registers_peers(
        self, client: TestClient, base: str
    ):
        reporter_client = make_client(base)

        _reporter, vendor = seed_containers(
            reporter_client=reporter_client,
            vendor_client=make_client(base),
        )

        actors = reporter_client.get("/actors/")
        actor_names = {a.get("name") for a in actors if isinstance(a, dict)}
        assert "Reporter" in actor_names
        assert vendor.name in actor_names

    def test_seed_with_deterministic_ids(self, client: TestClient, base: str):
        """The recordings need the same ids on every run (DEMOCI-11-025)."""
        reporter_id = f"{base}/actors/reporter-det-test"
        vendor_id = f"{base}/actors/vendor-det-test"

        reporter, vendor = seed_containers(
            reporter_client=make_client(base),
            vendor_client=make_client(base),
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
        )

        assert reporter.id_ == reporter_id
        assert vendor.id_ == vendor_id


class TestGetActorById:
    """``get_actor_by_id`` fetches actors by full URI."""

    def test_returns_actor_with_matching_id(
        self, client: TestClient, base: str
    ):
        dc = make_client(base)
        created = seed_actor(
            client=dc,
            name="TestActor",
            actor_type="Organization",
            actor_id=f"{base}/actors/test-get-actor-by-id",
        )
        assert get_actor_by_id(dc, created.id_).id_ == created.id_

    def test_raises_when_actor_not_found(self, client: TestClient, base: str):
        dc = make_client(base)
        with pytest.raises(ValueError, match="not found"):
            get_actor_by_id(dc, "http://nonexistent.example/actors/xyz")


class TestReporterSubmitsReport:
    """``reporter_submits_report`` stores the report and offer on the Vendor."""

    def test_report_and_offer_stored(self, client: TestClient, base: str):
        reporter_client = make_client(base)
        vendor_client = make_client(base)

        reporter, vendor = seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=f"{base}/actors/reporter-sub-test",
            vendor_actor_id=f"{base}/actors/vendor-sub-test",
        )
        vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

        report, offer = reporter_submits_report(
            receiver_client=vendor_client,
            reporter=reporter,
            receiver=vendor_in_vendor,
            reporter_client=reporter_client,
        )

        assert report.id_ is not None
        assert offer.id_ is not None
        verify_object_stored(vendor_client, report.id_)
        verify_received_activity_stored(vendor_client, offer.id_)


class TestReceiverValidatesReport:
    """``receiver_validates_report`` runs the Vendor's validate-report."""

    def test_validate_report_succeeds(self, client: TestClient, base: str):
        reporter_client = make_client(base)
        vendor_client = make_client(base)

        reporter, vendor = seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=f"{base}/actors/reporter-val-test",
            vendor_actor_id=f"{base}/actors/vendor-val-test",
        )
        vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

        _, offer = reporter_submits_report(
            receiver_client=vendor_client,
            reporter=reporter,
            receiver=vendor_in_vendor,
            reporter_client=reporter_client,
        )

        result = receiver_validates_report(
            receiver_client=vendor_client,
            receiver=vendor_in_vendor,
            offer_id=offer.id_,
        )
        assert result is not None

    def test_case_link_written_after_validation(
        self, client: TestClient, base: str
    ):
        """ADR-0041: validate-report writes a pending ``ReportCaseLink``.

        The Vendor defers case creation to the CaseActor, so what proves the
        proposal was sent is the link marker, not a local case (CP-04-001).
        """
        from vultron.core.models.report_case_link import VultronReportCaseLink

        reporter_client = make_client(base)
        vendor_client = make_client(base)

        reporter, vendor = seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=f"{base}/actors/reporter-casen-test",
            vendor_actor_id=f"{base}/actors/vendor-casen-test",
        )
        vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

        _, offer = reporter_submits_report(
            receiver_client=vendor_client,
            reporter=reporter,
            receiver=vendor_in_vendor,
            reporter_client=reporter_client,
        )
        receiver_validates_report(
            receiver_client=vendor_client,
            receiver=vendor_in_vendor,
            offer_id=offer.id_,
        )

        report_id, _ = _extract_offer_ids(vendor_client, offer)
        assert report_id is not None, "Could not extract report_id from offer"
        link_id = VultronReportCaseLink.build_id(report_id)
        assert vendor_client.get(vendor_client.dl_path(link_id)) is not None, (
            f"Expected a VultronReportCaseLink at '{link_id}' after"
            " validate-report (ADR-0041 pending proposal marker, CP-04-001)"
        )


class TestParticipantAddsNoteToCase:
    """The note thread the shared opening posts, helper by helper."""

    def _setup_case_with_two_participants(self, base: str, suffix: str):
        """Seed, submit, validate and open a case; return the pieces."""
        reporter_client = make_client(base)
        vendor_client = make_client(base)

        reporter, vendor = seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=f"{base}/actors/reporter-{suffix}",
            vendor_actor_id=f"{base}/actors/vendor-{suffix}",
        )
        vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

        _, offer = reporter_submits_report(
            receiver_client=vendor_client,
            reporter=reporter,
            receiver=vendor_in_vendor,
            reporter_client=reporter_client,
        )
        receiver_validates_report(
            receiver_client=vendor_client,
            receiver=vendor_in_vendor,
            offer_id=offer.id_,
        )
        case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)
        case_data = vendor_client.get(vendor_client.dl_path(case.id_))
        case = as_VulnerabilityCase(**case_data)
        return reporter_client, vendor_client, case, reporter, vendor

    def test_question_note_stored_in_vendor(
        self, client: TestClient, base: str
    ):
        reporter_client, vendor_client, case, reporter, _vendor = (
            self._setup_case_with_two_participants(base, "qnote-test")
        )

        question_note = participant_adds_note_to_case(
            posting_client=reporter_client,
            watching_client=vendor_client,
            poster=get_actor_by_id(reporter_client, reporter.id_),
            case=case,
            note_name="Question from Reporter",
            note_content=WORKAROUND_QUESTION,
        )

        assert question_note is not None
        assert question_note.id_ is not None
        verify_object_stored(vendor_client, question_note.id_)

    def test_vendor_reply_note_stored(self, client: TestClient, base: str):
        reporter_client, vendor_client, case, reporter, vendor = (
            self._setup_case_with_two_participants(base, "rreply-test")
        )
        vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

        question_note = participant_adds_note_to_case(
            posting_client=reporter_client,
            watching_client=vendor_client,
            poster=get_actor_by_id(reporter_client, reporter.id_),
            case=case,
            note_name="Question from Reporter",
            note_content=WORKAROUND_QUESTION,
        )
        reply_note = participant_adds_note_to_case(
            posting_client=vendor_client,
            watching_client=vendor_client,
            poster=vendor_in_vendor,
            case=case,
            note_name=WORKAROUND_ANSWER_NAME,
            note_content=WORKAROUND_ANSWER,
            in_reply_to=(
                question_note.id_ if question_note is not None else None
            ),
        )

        assert reply_note is not None
        assert reply_note.id_ is not None
        verify_object_stored(vendor_client, reply_note.id_)


# ---------------------------------------------------------------------------
# Polling helpers (D5-6-DEMOAUDIT)
# ---------------------------------------------------------------------------


def _setup_case_with_3_participants(base: str):
    """Seed, submit, create the case and run the RM triage.

    Returns ``(reporter_client, vendor_client, reporter, vendor, case)`` with
    three participants (Vendor + Reporter + CaseActor) and the Vendor's RM
    state at ``RM.ACCEPTED``, the minimum for a fix-ready claim (CSB-18-001).
    """
    reporter_client = make_client(base)
    vendor_client = make_client(base)

    reporter, vendor = seed_containers(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
    )
    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)
    _, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter_client=reporter_client,
        reporter=reporter,
        receiver=vendor_in_vendor,
    )
    # validate-report requires a live case (EnsureEmbargoExists needs an
    # active embargo for an embargo-eligible case), so the case comes first
    # and the RM triage follows.
    case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)
    receiver_validates_report(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer_id=offer.id_,
    )
    receiver_engages_case(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        case_id=case.id_,
    )
    return reporter_client, vendor_client, reporter, vendor_in_vendor, case


class TestWaitForReporterCase:
    """``wait_for_reporter_case``, the opening's case-replica wait."""

    def test_succeeds_when_case_already_present(
        self, client: TestClient, base: str
    ):
        """Returns at once when the case id is already in the DataLayer.

        In single-server tests both actors share the one node, so after the
        case is created the Reporter can read it immediately.
        """
        reporter_client, _vendor_client, _reporter, _vendor, case = (
            _setup_case_with_3_participants(base)
        )

        wait_for_reporter_case(
            reporter_client=reporter_client,
            case_id=case.id_,
            timeout_seconds=2.0,
        )

    def test_raises_when_case_never_arrives(
        self, client: TestClient, base: str
    ):
        """Raises when the case does not appear within the timeout."""
        with pytest.raises(AssertionError, match="Timed out"):
            wait_for_reporter_case(
                reporter_client=make_client(base),
                case_id="https://example.org/non-existent-case-wfc",
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestTriggerLogCommit:
    """``trigger_log_commit``, the ledger-replication probe."""

    def test_returns_entry_hash_string(self, client: TestClient, base: str):
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )

        entry_hash = trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
        )

        assert isinstance(entry_hash, str)
        assert len(entry_hash) > 0

    def test_sequential_commits_return_different_hashes(
        self, client: TestClient, base: str
    ):
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )

        h1 = trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            object_id=f"{case.id_}#event-a",
        )
        h2 = trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
            object_id=f"{case.id_}#event-b",
        )

        assert h1 != h2


class TestWaitForReporterLogEntry:
    """``wait_for_reporter_log_entry``, the per-entry replication wait."""

    def test_returns_when_entry_present(self, client: TestClient, base: str):
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )

        entry_hash = trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
        )

        wait_for_reporter_log_entry(
            reporter_client=vendor_client,
            case_id=case.id_,
            entry_hash=entry_hash,
            timeout_seconds=2.0,
        )

    def test_raises_when_entry_never_arrives(
        self, client: TestClient, base: str
    ):
        with pytest.raises(AssertionError, match="Timed out"):
            wait_for_reporter_log_entry(
                reporter_client=make_client(base),
                case_id="https://example.org/non-existent-case",
                entry_hash="deadbeef" * 8,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestVerifyReplicaState:
    """``verify_replica_state`` against a live TestClient."""

    def test_passes_when_replica_matches(self, client: TestClient, base: str):
        """Passes when authority and replica share the one node."""
        _reporter_client, vendor_client, reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )

        trigger_log_commit(
            client=vendor_client,
            actor_id=vendor.id_,
            case_id=case.id_,
        )

        verify_replica_state(
            auth_client=vendor_client,
            replica_client=vendor_client,
            case_id=case.id_,
            vendor_actor_id=vendor.id_,
            reporter_actor_id=reporter.id_,
        )

    def test_raises_when_replica_case_missing(
        self, client: TestClient, base: str
    ):
        """Raises naming the *replica*, not the authority.

        The two clients are distinct here — the authority holds the case, the
        replica's store has never seen it — so a helper that swapped its two
        client arguments would fail this test.
        """
        _reporter_client, vendor_client, reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        replica_client = make_client(
            base, actor_id="https://example.org/never-received-the-case"
        )

        with pytest.raises(AssertionError, match="Replica does not have"):
            verify_replica_state(
                auth_client=vendor_client,
                replica_client=replica_client,
                case_id=case.id_,
                vendor_actor_id=vendor.id_,
                reporter_actor_id=reporter.id_,
            )

    def test_raises_when_vendor_case_missing(
        self, client: TestClient, base: str
    ):
        """Raises when the authority has no record of the given case id."""
        # The client needs an actor for the read to be *addressable* at all;
        # the point is that the case is absent from that actor's store, not
        # that the read cannot be formed.
        vendor_actor_id = "https://example.org/vendor"
        vendor_client = make_client(base, actor_id=vendor_actor_id)

        with pytest.raises(AssertionError):
            verify_replica_state(
                auth_client=vendor_client,
                replica_client=vendor_client,
                case_id="https://example.org/non-existent-case-vrfs",
                vendor_actor_id=vendor_actor_id,
                reporter_actor_id="https://example.org/reporter",
            )


class TestActorSessionFixAndPublicationVerbs:
    """The triggers the fix and publication fragments drive."""

    def test_notify_fix_ready_returns_a_response(
        self, client: TestClient, base: str
    ):
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        result = (
            ActorSession(client=vendor_client, actor=vendor)
            .with_case(case)
            .notify_fix_ready()
        )
        assert result is not None

    def test_notify_fix_ready_on_a_missing_case_records_a_failure(
        self, client: TestClient, base: str
    ):
        """Accumulate, never re-raise (DEMOCI-01-003)."""
        _reporter_client, vendor_client, _reporter, vendor, _case = (
            _setup_case_with_3_participants(base)
        )

        with demo_step("vendor notifies fix ready on a missing case"):
            ActorSession(client=vendor_client, actor=vendor).with_case(
                as_VulnerabilityCase(
                    attributed_to=CASE_OWNER_ID,
                    id_="https://example.org/does-not-exist",
                )
            ).notify_fix_ready()

        assert any(
            "does-not-exist" in f or "404" in f or "STEP FAILED" in f
            for f in demo_utils._demo_failures
        )

    @pytest.mark.spec("CSB-15-002")
    def test_a_vendor_only_actor_is_blocked_from_vfd(
        self, client: TestClient, base: str
    ):
        """``CheckDeployerRoleNode`` refuses d→D for a non-DEPLOYER."""
        from vultron.demo.utils import post_to_trigger

        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        ActorSession(client=vendor_client, actor=vendor).with_case(
            case
        ).notify_fix_ready()
        # post_to_trigger directly, so the 4xx propagates; demo_step would
        # swallow it.  The double raises HTTPStatusError like the real client,
        # so the status is asserted structurally.
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            post_to_trigger(
                client=vendor_client,
                actor_id=vendor.id_,
                behavior="notify-fix-deployed",
                body={"case_id": case.id_},
                path_prefix="demo",
            )
        assert exc_info.value.response.status_code == 422, (
            "Expected HTTP 422 when a vendor-only actor attempts the VFD"
            f" transition; got {exc_info.value.response.status_code}"
        )
        assert "DEPLOYER" in exc_info.value.response.text, (
            "the refusal must name the missing role (CSB-15-002), otherwise a"
            " reader cannot tell this 422 from any other validation failure"
        )

    def test_notify_published_returns_a_response(
        self, client: TestClient, base: str
    ):
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        result = (
            ActorSession(client=vendor_client, actor=vendor)
            .with_case(case)
            .notify_published()
        )
        assert result is not None

    def test_leave_case_returns_a_leave_once_the_embargo_ends(
        self, client: TestClient, base: str
    ):
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        session = ActorSession(client=vendor_client, actor=vendor).with_case(
            case
        )
        session.terminate_embargo()
        wait_for_case_em_state(
            vendor_client, case.id_, EM.EXITED, dl_actor_id=vendor.id_
        )
        result = session.leave_case()
        assert result.activity is not None
        assert result.activity["type"] == "Leave"

    @pytest.mark.spec("TRIG-13-003")
    def test_the_case_owner_under_embargo_is_refused(
        self, client: TestClient, base: str
    ):
        """While the embargo is active the Case Owner's leave-case is a 409."""
        _reporter_client, vendor_client, _reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        with pytest.raises(httpx.HTTPStatusError, match="409"):
            ActorSession(client=vendor_client, actor=vendor).with_case(
                case
            ).leave_case()


class TestWaitForParticipantVfState:
    """``wait_for_participant_vf_state``, the fix-ready replica wait."""

    def test_times_out_for_unknown_actor(self, client: TestClient, base: str):
        _reporter_client, vendor_client, _reporter, _vendor, case = (
            _setup_case_with_3_participants(base)
        )

        with pytest.raises(AssertionError, match="Timed out"):
            wait_for_participant_vf_state(
                client=vendor_client,
                case_id=case.id_,
                actor_id="https://example.org/non-existent-actor",
                expected_states={CS_vf.VF},
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestWaitForCaseEmTerminated:
    """``wait_for_case_em_terminated``, the embargo-teardown wait."""

    def test_times_out_when_not_terminated(
        self, client: TestClient, base: str
    ):
        _, vendor_client, _, _vendor, case = _setup_case_with_3_participants(
            base
        )

        with pytest.raises(AssertionError, match="Timed out"):
            wait_for_case_em_terminated(
                client=vendor_client,
                case_id=case.id_,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )


class TestWaitForAllParticipantsRmClosed:
    """``wait_for_all_participants_rm_closed``, the closure gate's wait."""

    def test_times_out_when_participants_not_closed(
        self, client: TestClient, base: str
    ):
        _, vendor_client, _, _vendor, case = _setup_case_with_3_participants(
            base
        )

        with pytest.raises(AssertionError, match="Timed out"):
            wait_for_all_participants_rm_closed(
                client=vendor_client,
                case_id=case.id_,
                timeout_seconds=0.1,
                poll_interval=0.05,
            )

    def test_case_manager_does_not_block_rm_closure_check(
        self, client: TestClient, base: str
    ):
        """The CASE_MANAGER does not block the check in its own store.

        Close Vendor and Reporter; the Case Actor (CASE_MANAGER role) closes
        on the owner's Leave (CM-23-005), so it does not block
        ``_all_fetchable_participants_rm_closed`` from returning True.  The
        check reads the CASE_MANAGER's own store: a closed participant's
        replica is sent nothing after its own closure (CM-23-004), so the
        Vendor's replica never learns the CASE_MANAGER closed.
        """
        reporter_client, vendor_client, reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        # CM-23-011: the Case Actor declines an owner close while an embargo
        # is live.  The setup leaves an active embargo (validate-report needs
        # one), so the owner publishes first, which drives embargo teardown.
        ActorSession(client=vendor_client, actor=vendor).with_case(
            case
        ).notify_published()
        # The Reporter leaves before the owner: a Leave after the owner's
        # close records nothing (CM-23-013, CM-23-015).
        ActorSession(client=reporter_client, actor=reporter).with_case(
            case
        ).leave_case()
        ActorSession(client=vendor_client, actor=vendor).with_case(
            case
        ).leave_case()
        store_client, store_id = case_manager_store(vendor_client, case.id_)
        assert store_id is not None, "the CaseActor is co-hosted in this test"
        manager_client = store_client.model_copy(update={"actor_id": store_id})
        case_data = manager_client.get(manager_client.dl_path(case.id_))
        refreshed_case = as_VulnerabilityCase.model_validate(case_data)

        assert (
            _all_fetchable_participants_rm_closed(
                manager_client, refreshed_case
            )
            is True
        )

    def test_url_based_actor_keys_handled_gracefully(
        self, client: TestClient, base: str
    ):
        """URL-based keys in ``actor_participant_index`` stay fetchable.

        Regression test for #610.  The Case Actor's actor id (index key) is an
        HTTP URL; its participant record is stored under a ``urn:uuid:`` id
        (index value).  After the fix (``/{key:path}`` catch-all route) both
        are fetchable via the DataLayer endpoint, and
        ``_all_fetchable_participants_rm_closed`` must handle the layout.
        """
        from urllib.parse import quote

        _reporter_client, vendor_client, _reporter, _vendor, case = (
            _setup_case_with_3_participants(base)
        )
        case_data = vendor_client.get(vendor_client.dl_path(case.id_))
        fetched_case = as_VulnerabilityCase.model_validate(case_data)

        url_based_actor_ids = [
            actor_id
            for actor_id in fetched_case.actor_participant_index
            if actor_id.startswith("http")
        ]
        assert url_based_actor_ids, (
            "Expected at least one URL-based actor ID (Case Actor) in the"
            " index keys"
        )

        actor_id = url_based_actor_ids[0]
        encoded = quote(actor_id, safe="")
        result = vendor_client.get(vendor_client.dl_path(encoded))
        assert isinstance(result, dict) and result.get("id") == actor_id, (
            f"Expected Service record for URL-format ID {actor_id!r}, got"
            f" {result!r}"
        )

        try:
            _all_fetchable_participants_rm_closed(vendor_client, fetched_case)
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3989
            pytest.fail(
                f"_all_fetchable_participants_rm_closed crashed on URL-based"
                f" actor ID {actor_id!r}: {exc}"
            )


class TestVerifyCaseActive:
    """``verify_case_active``, the milestone ``the_case_is_active`` names."""

    def test_passes_with_3_participants(self, client: TestClient, base: str):
        """Passes when both DataLayers share 3 participants and EM.ACTIVE."""
        reporter_client, vendor_client, reporter, vendor, case = (
            _setup_case_with_3_participants(base)
        )
        wait_for_case_participants(
            vendor_client=vendor_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )
        wait_for_reporter_case(
            reporter_client=reporter_client,
            case_id=case.id_,
        )

        verify_case_active(
            receiver_client=vendor_client,
            reporter_client=vendor_client,
            case_id=case.id_,
            receiver_actor_id=vendor.id_,
            reporter_actor_id=reporter.id_,
        )

    def test_raises_when_participant_missing(
        self, client: TestClient, base: str
    ):
        _, vendor_client, _, vendor, case = _setup_case_with_3_participants(
            base
        )

        with pytest.raises(AssertionError):
            verify_case_active(
                receiver_client=vendor_client,
                reporter_client=vendor_client,
                case_id=case.id_,
                receiver_actor_id=vendor.id_,
                reporter_actor_id=(
                    "https://example.org/non-existent-reporter"
                ),
            )


# ---------------------------------------------------------------------------
# The whole story, played in process
# ---------------------------------------------------------------------------


# The full rv workflow runs every fragment through report submission, case
# activation, embargo, fix development and case closure — including several
# polling waits on asynchronous background-task replication.  It takes ~50 s
# locally, so a 30 s bound expired mid-run and presented as a hang rather than
# a failure.  180 s leaves headroom for slower CI runners without masking a
# genuine deadlock.
@pytest.mark.timeout(180)
class TestRunRvDemo:
    """The complete rv workflow through ``run_rv_demo``."""

    def test_full_workflow_succeeds(
        self, client: TestClient, base: str, caplog, tmp_path, monkeypatch
    ):
        reporter_client = make_client(base)
        vendor_client = make_client(base)
        # In process the CaseActor shares the one TestClient node; the Docker
        # topology gives it its own container (DEMOMA-06-004).
        case_actor_client = make_client(base, actor_id=case_actor_id_on(base))

        reporter_id = f"{base}/actors/reporter-full-test"
        vendor_id = f"{base}/actors/vendor-full-test"

        # run_story() always dumps the ledgers (ISSUE-2239), so point it at a
        # temp directory so the dump does not land in the repo-root devlogs/.
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        # No substitution for `run_direct_path_rm_triage`: the real
        # CaseProposal round-trip completes now, so the demo exercises the
        # actual protocol path rather than a hand-built stand-in.
        #
        # It used to be replaced by a fallback that created the case directly
        # via `trigger/create-case`.  Two defects were keeping the real path
        # from completing, and the fallback hid both.  #2482: the proposal
        # lost its inline report on the store round-trip.  #1872: the proposal
        # was addressed to a per-case `case-actor-<slug>` identity that the
        # sender derived and no container hosted, so delivery 404'd
        # permanently — and, once the identity became the container's, the
        # record still had to be written to the *CaseActor's own* store to
        # make it resolvable at all (ADR-0073).
        #
        # If this test starts failing at the case-activation milestone, check
        # the CaseActor's inbox for a 404 before assuming the harness is at
        # fault.  There is no depth-based delivery guard — that claim was
        # folklore and is retired.
        with caplog.at_level(logging.ERROR):
            demo.run_rv_demo(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                reporter_id=reporter_id,
                vendor_id=vendor_id,
            )

        assert "ERROR SUMMARY" not in caplog.text, (
            "Expected demo to succeed, but got errors:\n" + caplog.text
        )

        # AC-5 of #4511: the Reporter's replica came from the Vendor's
        # introduction (ADR-0132), not from a hand-seeded copy: its own link
        # records the Vendor as introducer and the CaseActor as CASE_MANAGER.
        from vultron.adapters.driven.datalayer_sqlite import get_datalayer
        from vultron.core.models.report_case_link import VultronReportCaseLink

        reporter_links = [
            link
            for link in get_datalayer(reporter_id).list_objects(
                "ReportCaseLink"
            )
            if isinstance(link, VultronReportCaseLink)
        ]
        assert [
            (link.case_creator_id, link.case_manager_id)
            for link in reporter_links
        ] == [(vendor_id, case_actor_id_on(base))]
        assert reporter_links[0].case_id is not None


# ---------------------------------------------------------------------------
# DataLayer isolation tests (#530)
# ---------------------------------------------------------------------------


class TestDeliveryIsolation:
    """Per-actor DataLayer isolation: state crosses only via outbox→inbox.

    These tests use two isolated FastAPI app instances (created via
    ``create_isolated_actor_app()``) each with their own in-memory
    ``SqliteDataLayer``.  An ``InProcessRouter`` replaces each app's HTTP
    fallback emitter so that outbound deliveries are routed to the correct
    actor's TestClient inbox in process rather than making real HTTP requests.

    Passing these tests confirms that:

    - the Reporter's DataLayer is empty before the Vendor delivers via the
      outbox path;
    - after the Vendor processes the Reporter's report and delivers the case
      announcement, the Reporter's DataLayer contains the case — received via
      inbox delivery, not through shared DataLayer state.
    """

    @pytest.fixture
    def delivery_setup(self):
        """Two isolated actor apps wired with cross-app TestClient delivery.

        Patches ``VULTRON_SERVER__BASE_URL`` and
        ``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`` to the Vendor's routable
        base URL so that ``WritePendingReportCaseLinkNode`` builds the
        CaseActor id correctly (ADR-0041, CP-04-002) and ASGI delivery routes
        to the Vendor app's inbox endpoints.

        Uses an explicit ``MonkeyPatch`` (not the pytest fixture) so that
        ``reload_config()`` in teardown runs AFTER ``undo()`` — the fixture
        auto-undoes after the explicit yield teardown block, which would leave
        the config stale for the next test class.
        """
        from vultron.adapters.driving.fastapi.outbox_handler import (
            configure_default_emitter,
            get_default_emitter,
        )
        from vultron.config import get_config, reload_config
        from vultron.demo.in_process import (
            InProcessRouter,
            create_isolated_actor_app,
        )

        _VENDOR_BASE = "http://vendor.test"
        mp = MonkeyPatch()
        mp.setenv("VULTRON_SERVER__BASE_URL", f"{_VENDOR_BASE}/api/v2")
        mp.setenv(
            "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", f"{_VENDOR_BASE}/api/v2"
        )
        reload_config()

        router = InProcessRouter()
        reporter_isolated = create_isolated_actor_app(
            base_url="http://reporter.test",
            router=router,
        )
        vendor_isolated = create_isolated_actor_app(
            base_url=_VENDOR_BASE,
            router=router,
        )

        config_base_url = get_config().server.base_url.rstrip("/")
        router.register(config_base_url, vendor_isolated.client)

        previous_emitter = get_default_emitter()
        configure_default_emitter(router)  # type: ignore[arg-type]

        with reporter_isolated.client as reporter_tc:
            with vendor_isolated.client as vendor_tc:
                yield (
                    reporter_isolated,
                    vendor_isolated,
                    reporter_tc,
                    vendor_tc,
                )

        configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
        reporter_isolated.close()
        vendor_isolated.close()
        mp.undo()
        reload_config()

    def test_reporter_dl_empty_before_delivery(self, delivery_setup):
        """The Reporter holds no case before any delivery occurs."""
        reporter_isolated, _vendor_isolated, reporter_tc, _vendor_tc = (
            delivery_setup
        )

        reporter_base = reporter_isolated.base_url + "/api/v2"
        reporter_id = f"{reporter_base}/actors/reporter-isolation-test"
        resp = reporter_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Reporter",
                "id": reporter_id,
            },
        )
        assert resp.status_code in (200, 201)

        # `store_for(reporter_id)`, not `dl`: the fixture builds this app
        # under the default "primary" slug, so `dl` belongs to no actor this
        # test creates and nothing ever writes to it.  Asserting *that* store
        # is empty could not fail, whatever isolation did.
        cases = reporter_isolated.store_for(reporter_id).get_all(
            "VulnerabilityCase"
        )
        assert cases == [], (
            f"Expected no cases in the Reporter's own store before delivery,"
            f" but found: {cases}"
        )

    def test_vendor_dl_isolated_from_reporter(self, delivery_setup):
        """Objects in the Vendor's store are not visible in the Reporter's."""
        reporter_isolated, vendor_isolated, _reporter_tc, vendor_tc = (
            delivery_setup
        )

        vendor_base = vendor_isolated.base_url + "/api/v2"
        vendor_id = f"{vendor_base}/actors/vendor-isolation-test"
        resp = vendor_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Vendor",
                "id": vendor_id,
            },
        )
        assert resp.status_code in (200, 201)

        # Establish the positive half first, otherwise "not visible in the
        # Reporter's store" is satisfied by the record not existing anywhere —
        # which is how a read on the unwritten "primary" store used to pass no
        # matter what isolation did.
        assert (
            vendor_isolated.store_for(vendor_id).read(vendor_id) is not None
        ), "the Vendor's actor must be in its own store to begin with"

        reporter_id = (
            f"{reporter_isolated.base_url}/api/v2/actors/"
            "reporter-isolation-peer"
        )
        actor_in_reporter = reporter_isolated.store_for(reporter_id).read(
            vendor_id
        )
        assert actor_in_reporter is None, (
            "the Vendor's actor must not be visible in the Reporter's own"
            " store, but it was found."
        )

    def test_case_delivered_to_reporter_via_inbox(self, delivery_setup):
        """The Reporter receives the case via the delivery path.

        The core delivery-path test for #530.  Without the fix the Reporter's
        DataLayer would remain empty because delivery was never exercised.
        With it the outbox→inbox chain runs in process via
        ``InProcessRouter`` and the Reporter's isolated DataLayer receives the
        case announcement.
        """
        import types

        reporter_isolated, vendor_isolated, reporter_tc, vendor_tc = (
            delivery_setup
        )

        reporter_base = reporter_isolated.base_url + "/api/v2"
        vendor_base = vendor_isolated.base_url + "/api/v2"

        reporter_id = f"{reporter_base}/actors/reporter-delivery-test"
        vendor_id = f"{vendor_base}/actors/vendor-delivery-test"

        r = reporter_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Reporter",
                "id": reporter_id,
            },
        )
        assert r.status_code in (200, 201)
        r = vendor_tc.post(
            "/api/v2/actors/",
            json={"type": "Organization", "name": "Vendor", "id": vendor_id},
        )
        assert r.status_code in (200, 201)

        # Build DataLayerClient wrappers routed to their respective apps.
        # Bound to their own actors: a DataLayer read has to say whose store
        # it is about (ADR-0073), and each of these apps hosts its actor plus
        # any CaseActor it self-hosts (CP-08-003), so the container alone is
        # not enough.  Unbound, `dl_path` refuses rather than guessing.
        reporter_dc = DataLayerClient(
            base_url=reporter_base, actor_id=reporter_id
        )
        vendor_dc = DataLayerClient(base_url=vendor_base, actor_id=vendor_id)
        object.__setattr__(
            reporter_dc,
            "call",
            types.MethodType(
                make_testclient_call(reporter_tc, reporter_base), reporter_dc
            ),
        )
        object.__setattr__(
            vendor_dc,
            "call",
            types.MethodType(
                make_testclient_call(vendor_tc, vendor_base), vendor_dc
            ),
        )

        reporter_actor = get_actor_by_id(reporter_dc, reporter_id)
        vendor_actor = get_actor_by_id(vendor_dc, vendor_id)

        # Each registers the other as a peer so the report offer can be
        # constructed with the correct actor reference.  409 is fine — the
        # peer may already be registered.
        reporter_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Vendor",
                "id": vendor_id,
            },
        )
        vendor_tc.post(
            "/api/v2/actors/",
            json={
                "type": "Organization",
                "name": "Reporter",
                "id": reporter_id,
            },
        )

        _report, offer = reporter_submits_report(
            receiver_client=vendor_dc,
            reporter=reporter_actor,
            receiver=vendor_actor,
            reporter_client=reporter_dc,
        )
        assert offer.id_ is not None

        # Under ADR-0041 this writes a VultronReportCaseLink and sends
        # Create(CaseProposal) to the CaseActor.
        vendor_actor_fresh = get_actor_by_id(vendor_dc, vendor_id)
        receiver_validates_report(
            receiver_client=vendor_dc,
            receiver=vendor_actor_fresh,
            offer_id=offer.id_,
        )

        # In this two-app setup the CaseActor runs on the Vendor app, so the
        # proposal round-trip may complete synchronously.
        # `store_for(vendor_id)`, not `vendor_isolated.dl`: the fixture builds
        # both apps with the default "primary" slug, so `dl` is a store
        # belonging to no actor this test creates.
        case = _create_case_from_offer(
            vendor_dc,
            vendor_actor_fresh,
            offer,
            dl=vendor_isolated.store_for(vendor_id),
        )
        assert case is not None, (
            "Expected a VulnerabilityCase after validate-report or"
            " trigger/create-case"
        )

        # The case announcement should have been delivered to the Reporter's
        # inbox via the outbox→InProcessRouter→inbox chain, into the
        # Reporter's own store.
        reporter_case = reporter_isolated.store_for(reporter_id).read(case.id_)
        assert reporter_case is not None, (
            f"Expected case '{case.id_}' to be delivered to the Reporter's"
            f" isolated DataLayer via the outbox→inbox path, but the"
            f" Reporter's DataLayer has no record of it.  This indicates the"
            f" delivery path is broken or the DataLayers are incorrectly"
            f" shared (#530)."
        )


# ---------------------------------------------------------------------------
# In-process case-ledger invariant helpers (#950)
# ---------------------------------------------------------------------------


def _log_semantic_type(entry: dict) -> str:
    """Return ``semanticType`` from a log entry dict (camelCase alias ok)."""
    return str(entry.get("semanticType", entry.get("semantic_type", "")))


def _log_payload(entry: dict) -> dict:
    """Return ``payloadSnapshot`` from a log entry dict."""
    snap = entry.get("payloadSnapshot", entry.get("payload_snapshot", {}))
    return snap if isinstance(snap, dict) else {}


def _participant_id_and_rm(
    snapshot: dict,
) -> tuple[str | None, str | None]:
    """Extract participant id and RM state from a participant-status snapshot.

    Historical logs may encode ``ParticipantStatus`` directly in the snapshot
    or nest it under an ``Add`` activity's ``object``.  Accepts both camelCase
    (wire) and snake_case field names.
    """
    p_id = snapshot.get("attributedTo") or snapshot.get("attributed_to")
    rm_state = snapshot.get("rmState") or snapshot.get("rm_state")
    if p_id and rm_state:
        return str(p_id), str(rm_state)

    nested = snapshot.get("object")
    if isinstance(nested, dict):
        nested_id = nested.get("attributedTo") or nested.get("attributed_to")
        nested_rm = nested.get("rmState") or nested.get("rm_state")
        if nested_id and nested_rm:
            return str(nested_id), str(nested_rm)

    return None, None


def _fetch_case_log(
    client: DataLayerClient,
    case: as_VulnerabilityCase,
) -> list[dict]:
    """Return case ledger entries from the demo DataLayer API endpoint.

    Calls ``GET /actors/{route_key}/demo/cases/{case_key}/log``.  In the
    single-DataLayer test environment the endpoint returns all
    ``CaseLedgerEntry`` objects for *case* regardless of which actor route key
    is supplied (``actor_id`` is ignored server-side; see
    ``demo_triggers.demo_get_case_ledger``).  The case-actor route key is
    preferred when available so that the path is realistic, but the returned
    entries represent the *combined* case log, not a per-actor replica.

    Returns an empty list when no case-actor participant can be located.
    """
    case_key = strip_id_prefix(case.id_ or "")
    case_actor_route_key = next(
        (
            strip_id_prefix(actor_id)
            for actor_id in (case.actor_participant_index or {})
            if strip_id_prefix(actor_id).startswith("case-actor")
        ),
        None,
    )
    if case_actor_route_key is None:
        return []
    log_path = f"/actors/{case_actor_route_key}/demo/cases/{case_key}/log"
    return client.get_list(log_path)


@pytest.fixture
def completed_workflow(
    client: TestClient, base: str
) -> tuple[DataLayerClient, as_VulnerabilityCase]:
    """Run the rv lifecycle by hand and return ``(vendor_client, case)``.

    Uses deterministic actor ids (``reporter-ledger-inv`` /
    ``vendor-ledger-inv``) to avoid collisions with other test classes.

    **Per-test, not per-class.**  This fixture's value is store state, and
    ``_dispose_actor_stores_between_tests`` in ``test/conftest.py`` is autouse
    and per-test: it calls ``reset_datalayer()``, which disposes every
    per-actor engine and so destroys the named in-memory databases (ADR-0073).
    A class-scoped workflow therefore survived only until the first test
    finished — the second and third read a case-actor store that no longer
    existed and got ``404 Case not found``, which looked like a fan-out defect
    rather than a fixture-lifetime one.  Any fixture holding store state must
    not outlive the disposal that guarantees test isolation.
    """
    reporter_client = make_client(base)
    vendor_client = make_client(base)

    reporter_id = f"{base}/actors/reporter-ledger-inv"
    vendor_id = f"{base}/actors/vendor-ledger-inv"

    reporter, vendor = seed_containers(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        reporter_actor_id=reporter_id,
        vendor_actor_id=vendor_id,
    )
    vendor_in_vendor = get_actor_by_id(vendor_client, vendor.id_)

    _, offer = reporter_submits_report(
        receiver_client=vendor_client,
        reporter=reporter,
        receiver=vendor_in_vendor,
        reporter_client=reporter_client,
    )
    receiver_validates_report(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        offer_id=offer.id_,
    )

    case = _create_case_from_offer(vendor_client, vendor_in_vendor, offer)
    assert case is not None, "Expected a case after trigger/create-case"
    # Refresh the case to get actor_participant_index populated.
    case_data = vendor_client.get(vendor_client.dl_path(case.id_))
    case = as_VulnerabilityCase(**case_data)

    # Engage the case so the Vendor reaches RM.ACCEPTED before any
    # fix-readiness claim.  Without this the fixture went straight from case
    # creation to `notify_fix_ready`, which the cross-machine entailment rule
    # refuses with HTTP 422 — VFD='VFd' requires RM ∈ {ACCEPTED, DEFERRED,
    # CLOSED} and RM was still VALID (rm_em_cs.md § Fix Readiness).
    # `demo_step` logs that 🔴 and swallows it, so the fixture reported
    # success while its entire fix-lifecycle half had not run.
    receiver_engages_case(
        receiver_client=vendor_client,
        receiver=vendor_in_vendor,
        case_id=case.id_,
    )
    wait_for_participant_rm_state(
        client=vendor_client,
        case_id=case.id_,
        actor_id=vendor_in_vendor.id_,
        expected_states={RM.ACCEPTED},
    )

    # Fix lifecycle: a vendor-only actor stops at VFd (CSB-15-002).
    vendor_session = ActorSession(
        client=vendor_client, actor=vendor_in_vendor
    ).with_case(case)
    with demo_step("vendor reports fix ready"):
        vendor_session.notify_fix_ready()
    with demo_step("vendor reports publication"):
        vendor_session.notify_published()

    # Case closure — both actors must close so RM=CLOSED for all.  The
    # Reporter leaves first: a Leave after the owner's close records nothing
    # (CM-23-013, CM-23-015).
    reporter_in_reporter = get_actor_by_id(reporter_client, reporter.id_)
    with demo_step("reporter closes case"):
        ActorSession(
            client=reporter_client, actor=reporter_in_reporter
        ).with_case(case).leave_case()
    with demo_step("vendor closes case"):
        vendor_session.leave_case()

    # Final refresh to pick up any post-closure case-actor state.
    case_data = vendor_client.get(vendor_client.dl_path(case.id_))
    case = as_VulnerabilityCase(**case_data)

    return vendor_client, case


class TestCaseLedgerInvariants:
    """In-process case-ledger invariant checks for the rv scenario.

    Adapts invariants 5 and 7 from ``test/ci/test_case_ledger_invariants.py``
    to run against the live in-process DataLayer state rather than parsed
    JSONL files.  Tests run in sub-second time without any Docker
    requirement.

    Each assertion carries a comment pointing to the corresponding CI
    invariant number (AC: issue #950 acceptance criteria item 4).

    Auto-marked ``integration`` by the demo conftest hook.
    Spec: CLP-07.
    """

    #: Baseline semantic types that must appear in the combined case log after
    #: a complete rv CVD run.  These are the types observed in the
    #: single-DataLayer in-process test environment and do not correspond
    #: directly to CI invariant 5 (whose full set requires CaseActor
    #: commit-path completeness — see issue #789).
    _REQUIRED_SEMANTIC_TYPES: frozenset[str] = frozenset(
        {
            # participant tracking — CI invariant 7.
            "add_participant_status_to_participant",
            # offer_case_manager_role removed: ADR-0041 removes
            # SendOfferCaseManagerRoleNode; the CaseActor self-assigns
            # CASE_MANAGER natively without the offer/accept round-trip.
        }
    )

    def test_add_participant_status_entries_present(
        self,
        completed_workflow: tuple[DataLayerClient, as_VulnerabilityCase],
    ) -> None:
        """At least one ``add_participant_status`` entry is in the log.

        Checks the combined case log (all actors share one DataLayer in this
        test environment).  Corresponds to the presence pre-condition of CI
        invariant 7 from ``test/ci/test_case_ledger_invariants.py``.
        Spec: CLP-07.
        """
        vendor_client, case = completed_workflow
        entries = _fetch_case_log(vendor_client, case)

        # CI invariant 7 — presence of add_participant_status entries.
        status_entries = [
            e
            for e in entries
            if _log_semantic_type(e) == "add_participant_status_to_participant"
        ]
        assert status_entries, (
            "Expected at least one add_participant_status_to_participant entry"
            " in the combined case log, but none were found. "
            f"(total entries: {len(entries)}, semantic types: "
            f"{sorted({_log_semantic_type(e) for e in entries})})"
        )

    def test_all_participants_rm_closed_at_scenario_end(
        self,
        completed_workflow: tuple[DataLayerClient, as_VulnerabilityCase],
    ) -> None:
        """Every tracked participant ends in RM=CLOSED.

        Scans ``add_participant_status`` and ``close_case`` entries in the
        combined case log to determine the final RM state per participant.
        ``add_participant_status_to_participant`` entries carry the RM state
        explicitly; ``close_case`` entries signal RM=CLOSED for the departing
        actor recorded in ``payloadSnapshot.actor`` (ADR-0050,
        CM-23-002/003).  Corresponds to CI invariant 7 (terminal RM state
        check).

        The CASE_MANAGER reaches ``RM.CLOSED`` here through its own
        ``add_participant_status_to_participant`` entry, committed by
        ``CommitRMClosureEntriesNode`` on the owner-Leave path (CM-23-005).
        Spec: CLP-07.
        """
        vendor_client, case = completed_workflow
        entries = _fetch_case_log(vendor_client, case)

        # CI invariant 7 — last RM state per participant must be CLOSED.
        latest_rm: dict[str, str] = {}
        for entry in entries:
            semantic_type = _log_semantic_type(entry)
            payload = _log_payload(entry)
            if semantic_type == "add_participant_status_to_participant":
                p_id, rm_state = _participant_id_and_rm(payload)
                if p_id and rm_state:
                    latest_rm[p_id] = rm_state
            elif semantic_type == "close_case":
                # close_case entries signal RM=CLOSED for the departing actor
                # (ADR-0050: Leave(VulnerabilityCase) is the canonical path).
                actor_id = payload.get("actor") or payload.get("attributedTo")
                if isinstance(actor_id, dict):
                    actor_id = actor_id.get("id")
                if actor_id:
                    latest_rm[str(actor_id)] = "CLOSED"

        assert latest_rm, (
            "No add_participant_status_to_participant or close_case entries"
            " found in the combined case log; cannot verify terminal RM"
            " states."
        )

        not_closed = {
            p: s
            for p, s in latest_rm.items()
            if s.upper() not in ("CLOSED", "RM.CLOSED")
        }
        assert not not_closed, (
            f"Participants not in RM=CLOSED at scenario end: {not_closed}"
        )

    def test_required_semantic_types_present_in_case_actor_log(
        self,
        completed_workflow: tuple[DataLayerClient, as_VulnerabilityCase],
    ) -> None:
        """The combined case log carries the required baseline types.

        Verifies a baseline set of semantic types observed in the
        single-DataLayer in-process test environment.  This does not directly
        correspond to CI invariant 5 (whose full ``EXPECTED_SEMANTIC_TYPES``
        set requires CaseActor commit-path completeness per issue #789); it
        confirms that the participant-tracking and report-intake paths produce
        log entries.
        Spec: CLP-07.
        """
        vendor_client, case = completed_workflow
        entries = _fetch_case_log(vendor_client, case)

        found = {_log_semantic_type(e) for e in entries}
        missing = self._REQUIRED_SEMANTIC_TYPES - found
        assert not missing, (
            f"Required semanticTypes missing from the combined case log:"
            f" {sorted(missing)}\nFound: {sorted(found)}"
        )
