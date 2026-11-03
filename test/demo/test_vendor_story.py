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

"""Unit tests for the vendor-first family's shared story (#5536).

``rv``, ``rvv``, ``rvcv-extension`` and ``rvcv-handoff`` open the same way —
the Reporter submits its report to a Vendor, the Vendor engages the case as
CASE_OWNER, and the Reporter then asks whether a workaround exists and the
Vendor answers — and :mod:`vultron.demo.helpers.vendor_story` is that one copy
of the code: the cast opening, the named prefixes
:data:`~vultron.demo.helpers.vendor_story.REPORTER_TELLS_THE_VENDOR` and
:data:`~vultron.demo.helpers.vendor_story.THE_VENDOR_ANSWERS_THE_REPORTER`,
and every continuation more than one of the four tells (DEMOMA-17-001,
DEMOCI-11-018).

The tests here own what the family shares; each scenario's own module owns its
own fragments, and ``test_vendor_coordinator_story.py`` owns the ``rvcv``
pair's opening, which continues this one.  Every test patches the
collaborators out, so no HTTP happens; ``demo_gate`` / ``demo_check`` /
``demo_step`` stay real wherever the test is about control flow and are
stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).
"""

import contextlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

import vultron.demo.utils as demo_utils
from test.demo._helpers import (
    functions_referencing,
    mock_actor,
    mock_case,
    mock_client,
    no_demo_banners,
    story_state,
)
from vultron.core.states.cs import CS_vf
from vultron.demo.helpers import (
    coordinated_story,
    seeding,
    story_cast,
    vendor_story as family,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    joining as coordinated_joining,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_ANSWER,
    WORKAROUND_ANSWER_NAME,
    WORKAROUND_QUESTION,
    NotePost,
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.polling import LATE_JOINER_TIMEOUT
from vultron.demo.helpers.story import Choose, StoryState, UnseatedContainer
from vultron.demo.helpers.vendor_story import (
    cast as vendor_cast,
    continuations as vendor_continuations,
    opening as vendor_opening,
)
from vultron.demo.utils import reset_demo_failures
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: The two members the shared opening seats, in ``seed_containers`` order.
_SEATED = (REPORTER, family.VENDOR)

#: A cast name the ``rvcv`` pair brings in after the branch point, used here
#: to stand for any container the opening resets but does not seed (#5532).
_JOINER = family.VENDOR2


@pytest.fixture(autouse=True)
def _fresh_failures():
    """Clear the process-global failure accumulator around every test.

    ``vultron.demo.utils._demo_failures`` is process-global, and a gate skips
    its own body once anything is recorded, so a leftover failure changes what
    the next test observes (``notes/testing-pitfalls.md``).
    """
    reset_demo_failures()
    yield
    reset_demo_failures()


def _gate_failures() -> list[str]:
    """Every recorded gate failure, in order."""
    return [f for f in demo_utils._demo_failures if "GATE FAILED" in f]


@contextlib.contextmanager
def _recording_checks() -> Iterator[list[str]]:
    """Stub this module's ``demo_check`` and collect the labels it was given.

    Each milestone's label is the *caller's* — a scenario numbers its own
    milestones — so the labels are what a test of a shared continuation can
    pin, and a mock that only swallows them would prove nothing.
    """
    labels: list[str] = []

    def _check(label: str):
        labels.append(label)
        return contextlib.nullcontext()

    with patch.object(vendor_continuations, "demo_check", side_effect=_check):
        yield labels


@contextlib.contextmanager
def _opening_stubs(
    case: MagicMock,
    *,
    reread: MagicMock | None = None,
    roster=None,
) -> Iterator[SimpleNamespace]:
    """Stub every collaborator of :func:`the_reporter_tells_the_vendor`.

    ``vendor_story``'s own ``demo_gate`` is left **real**: every test of the
    opening is about which steps the roster gate holds, and patching it out
    would make a failing roster's assertion propagate and the test pass while
    proving nothing.  Only the Reporter's replica check opens a banner
    elsewhere, so ``coordinated_story``'s are the ones made transparent.

    Args:
        case: What the Vendor's RM triage returns.
        reread: What the re-read of the Vendor's own store validates to;
            defaults to *case* itself.
        roster: ``side_effect`` for the roster wait, so a test can time it
            out.
    """
    with (
        patch.object(
            vendor_opening,
            "reporter_submits_report",
            return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
        ) as submit,
        patch.object(
            vendor_opening, "run_direct_path_rm_triage", return_value=case
        ) as triage,
        patch.object(
            vendor_opening, "wait_for_case_participants", side_effect=roster
        ) as roster_wait,
        patch.object(
            coordinated_joining, "wait_for_case_on_container"
        ) as replica_wait,
        patch.object(vendor_opening, "as_VulnerabilityCase") as wire_case,
        no_demo_banners(coordinated_story),
    ):
        wire_case.model_validate.return_value = (
            case if reread is None else reread
        )
        yield SimpleNamespace(
            submit=submit,
            triage=triage,
            roster=roster_wait,
            replica=replica_wait,
            wire_case=wire_case,
        )


def _family_state(*extra: str) -> StoryState:
    """A story state seating the two the opening seeds, plus *extra*.

    The roster prop is kept, because every fragment of the family reads it
    before it acts (DEMOCI-01-011) and only the tests about its absence run
    without it.
    """
    state = story_state(*_SEATED, *extra, case=mock_case())
    state.keep(family.THE_VENDORS_CASE, str(state.case.id_))
    return state


# ---------------------------------------------------------------------------
# The family's cast names and budgets
# ---------------------------------------------------------------------------


class TestTheFamilyCastNames:
    """One copy of each fragment serves both halves of the tree."""

    def test_the_reporter_is_seated_under_the_rcv_familys_name(self):
        """So the continuations both halves share can read it (#5536).

        The vendor-first family does not define a Reporter name of its own: it
        imports the coordinator-first family's, which is the name
        :mod:`vultron.demo.helpers.owner_decision_story` reads the Reporter
        under.
        """
        assert vendor_cast.REPORTER is REPORTER
        assert vendor_cast.REPORTER_LABEL is REPORTER_LABEL

    def test_each_part_pairs_a_cast_name_with_this_familys_label(self):
        """A ``Part`` is the ``(name, label)`` a shared continuation needs."""
        assert Part(family.VENDOR, "Vendor1") == family.VENDOR_PART
        assert Part(family.VENDOR2, "Vendor2") == family.VENDOR2_PART

    def test_both_vendors_are_labelled_apart_even_in_rv(self):
        """One authored opening means one label (DEMOMA-17-001).

        ``rv`` has a single Vendor, but three of the four siblings have a
        second one to tell it apart from, so the shared labels number them.
        Each scenario's own ``ROLES`` keeps its own labels, which is what the
        CLI help and the health check read.
        """
        assert (family.VENDOR_LABEL, family.VENDOR2_LABEL) == (
            "Vendor1",
            "Vendor2",
        )

    def test_every_join_of_the_family_takes_the_late_joiner_budget(self):
        """Each join reaches its actor through the CaseActor's outbox.

        A budget only bounds how long a wait may take, so taking the widest
        of the four refuses nothing a shorter one admitted and moves no byte
        of a recording (DEMOCI-11-018).
        """
        assert family.JOIN_TIMEOUT is LATE_JOINER_TIMEOUT


# ---------------------------------------------------------------------------
# The shared opening (DEMOMA-23-003, DEMOCI-01-011)
# ---------------------------------------------------------------------------


class TestTheReporterTellsTheVendor:
    """The opening all four vendor-first scenarios share."""

    def test_the_reporter_submits_through_its_own_container(self):
        """The receiver is the Vendor, which then runs the RM triage.

        A report is submitted from the Reporter's own session into the
        receiver's container, so both clients are named and neither is
        guessed: swapping them would have the Reporter triage its own report.
        """
        state = story_state(*_SEATED)
        case = mock_case()

        with _opening_stubs(case) as stubs:
            family.the_reporter_tells_the_vendor(state)

        kwargs = stubs.submit.call_args.kwargs
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["reporter"] is state.actor(REPORTER).actor
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["receiver"] is state.actor(family.VENDOR).actor
        triage_kwargs = stubs.triage.call_args.kwargs
        assert triage_kwargs["receiver_client"] is state.client(family.VENDOR)
        assert triage_kwargs["receiver"] is state.actor(family.VENDOR).actor
        assert triage_kwargs["offer"] is stubs.submit.return_value[1]
        assert not _gate_failures(), _gate_failures()

    def test_the_triage_runs_on_the_familys_one_budget(self):
        """The four scenarios share one copy, so they share one budget.

        The ``rvcv`` pair set the value — 60 s for a run that brings five
        actor containers up under CI load — and a budget only bounds how long
        a wait may take, so the narrower siblings inherit it without
        admitting or refusing anything differently (DEMOCI-11-018).
        """
        state = story_state(*_SEATED)

        with _opening_stubs(mock_case()) as stubs:
            family.the_reporter_tells_the_vendor(state)

        assert (
            stubs.triage.call_args.kwargs["timeout_seconds"]
            == family.VENDOR_TRIAGE_TIMEOUT
        ), (
            "the Vendor's RM triage runs on the family's one budget"
            f" (DEMOCI-11-018); got {stubs.triage.call_args.kwargs!r}"
        )

    @pytest.mark.spec("DEMOMA-23-003")
    def test_the_case_is_recorded_before_the_roster_gate(self):
        """ISSUE-2239: the dump is armed at the first instant it can be.

        The triage returning the case is that instant, and the roster gate
        that follows is itself a step that can fail — so arming the dump
        after it would cost the ledgers of every run whose roster never
        filled.
        """
        state = story_state(*_SEATED)
        case = mock_case()
        order: list[str] = []
        harness = cast(MagicMock, state.harness)
        harness.dump_with.side_effect = lambda _dump: order.append("armed")

        with _opening_stubs(
            case, roster=lambda **_kwargs: order.append("roster")
        ):
            family.the_reporter_tells_the_vendor(state)

        assert order == ["armed", "roster"], (
            "the ledger dump must be armed before the roster gate runs"
            f" (DEMOMA-23-003, ISSUE-2239); order was {order}"
        )

    @pytest.mark.spec("DEMOMA-23-003")
    def test_a_roster_that_never_fills_still_leaves_the_dump_armed(self):
        """The failing gate is the reason the dump is armed above it.

        The harness runs the dump on the way out whether or not a step failed
        (DEMOMA-23-001), so a run that dies at the roster still exports the
        ledgers the failure has to be read from.
        """
        state = story_state(*_SEATED)
        case = mock_case()

        def _timeout(**_kwargs):
            raise AssertionError("timed out polling for the roster")

        with _opening_stubs(case, roster=_timeout):
            family.the_reporter_tells_the_vendor(state)

        harness = cast(MagicMock, state.harness)
        harness.dump_with.assert_called_once()
        harness.follow_ledger.assert_called_once_with(
            state.case_actor_client, case.id_
        )
        assert _gate_failures(), demo_utils._demo_failures

    @pytest.mark.spec("DEMOCI-01-011")
    def test_the_roster_gate_holds_everything_that_presupposes_it(self):
        """A roster that never arrived skips the three steps behind it.

        The Reporter and the Vendor both being seated is what every later
        step presupposes, so the wait is a ``demo_gate`` and the Reporter's
        replica check, the case re-read and
        :data:`~vultron.demo.helpers.vendor_story.THE_VENDORS_CASE` sit
        inside it; the fragment that runs next then stops the story rather
        than acting on a case the owner cannot vouch for
        (``vultron/demo/AGENTS.md`` § "Never Wrap a Causal Wait in
        demo_check").
        """
        state = story_state(*_SEATED)
        case = mock_case()

        def _timeout(**_kwargs):
            raise AssertionError("timed out polling for the roster")

        with _opening_stubs(case, roster=_timeout) as stubs:
            family.the_reporter_tells_the_vendor(state)

        stubs.replica.assert_not_called()
        stubs.wire_case.model_validate.assert_not_called()
        assert state.case is case, (
            "a gate that failed must leave the case the triage returned"
            f" in place; state holds {state.case!r}"
        )
        with pytest.raises(DemoStoryError, match="roster the Vendor"):
            state.kept(family.THE_VENDORS_CASE)
        assert _gate_failures(), demo_utils._demo_failures

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_inside_the_same_gate(self):
        """Bug #2135: a later step broadcasts the ledger to the Reporter.

        A Reporter without the case has no genesis hash to anchor the chain
        on, so the replica wait runs inside the roster's gate and reads the
        Reporter's own container.
        """
        state = story_state(*_SEATED)

        with _opening_stubs(mock_case()) as stubs:
            family.the_reporter_tells_the_vendor(state)

        assert [c.kwargs["client"] for c in stubs.replica.call_args_list] == [
            state.client(REPORTER)
        ]
        assert stubs.replica.call_args.kwargs["timeout_seconds"] == (
            family.CASE_REPLICA_TIMEOUT
        )

    def test_the_case_is_re_read_from_the_vendors_own_store(self):
        """The triage and the seating have moved on since the trigger.

        The re-read goes through ``restate_case``, not ``open_case``: the
        dump is armed at the first instant there is anything to dump and
        exactly once, so a step that re-reads the case must not re-arm it or
        follow a second ledger (DEMOMA-23-003).
        """
        state = story_state(*_SEATED)
        case = mock_case()
        # A distinct object with the same id, so the re-read is observable:
        # handing back the triage's own case would pass whether or not the
        # fragment restated it.
        reread = mock_case()

        with _opening_stubs(case, reread=reread):
            family.the_reporter_tells_the_vendor(state)

        owner_client = cast(MagicMock, state.client(family.VENDOR))
        assert owner_client.dl_path.call_args.args == (case.id_,)
        assert state.case is reread, (
            "the fragment must re-read the case the Vendor now stores;"
            f" state holds {state.case!r}"
        )
        harness = cast(MagicMock, state.harness)
        harness.dump_with.assert_called_once()
        harness.follow_ledger.assert_called_once_with(
            state.case_actor_client, case.id_
        )
        assert state.kept(family.THE_VENDORS_CASE) == str(case.id_)

    def test_a_re_read_of_a_different_case_is_refused(self):
        """No act of a scenario changes a case's id (CM-21-002, #5535).

        A different id means the fragment read the wrong record, and taking
        it would leave the story acting on one case while the armed dump and
        the followed ledger belong to another.  The refusal lands inside the
        roster's gate, so it is recorded and the prop is never kept.
        """
        state = story_state(*_SEATED)
        case = mock_case()

        with _opening_stubs(case, reread=mock_case("urn:test:another-case")):
            family.the_reporter_tells_the_vendor(state)

        assert state.case is case
        with pytest.raises(DemoStoryError, match="roster the Vendor"):
            state.kept(family.THE_VENDORS_CASE)
        assert _gate_failures(), demo_utils._demo_failures


# ---------------------------------------------------------------------------
# The named prefixes (notes/demo-scenario-tree.md § "Composition")
# ---------------------------------------------------------------------------


class TestTheNamedPrefixes:
    """Two authored prefixes, the second nesting the first."""

    def test_the_opening_prefix_is_the_reporters_choice_then_the_submission(
        self,
    ):
        """One assertion for the whole prefix, so a reordering shows.

        Named rather than assembled from the fragment at each call site,
        because assembling siblings from fragments alone lets one of them
        slip a step in before the branch point (DEMOCI-11-018).
        """
        assert family.REPORTER_TELLS_THE_VENDOR.items == (
            Choose(
                branch_point="reporter-whom-to-tell",
                choice="vendor",
                by=REPORTER,
            ),
            family.the_reporter_tells_the_vendor,
        )

    def test_the_opening_prefix_walks_the_reporters_one_step(self):
        """The path is read off the choices, not typed beside them."""
        assert family.REPORTER_TELLS_THE_VENDOR.path == (
            ("reporter-whom-to-tell", "vendor"),
        )

    def test_the_answer_prefix_nests_the_opening_one(self):
        """Identity of the shared stretch, not a matching sequence.

        All four scenarios share one copy of the report submission and the
        Vendor's triage, which is what makes their recordings byte-identical
        up to ``vendor-after-answer`` (DEMOCI-11-018).  Comparing against
        ``REPORTER_TELLS_THE_VENDOR.items`` is what stops the longer prefix
        restating them and drifting.
        """
        shared = len(family.REPORTER_TELLS_THE_VENDOR.items)
        nested = family.THE_VENDOR_ANSWERS_THE_REPORTER.items[:shared]

        assert nested == family.REPORTER_TELLS_THE_VENDOR.items
        # Identity only: ``Choose`` is a frozen dataclass, so a hand-copied
        # duplicate would compare equal.
        for mine, theirs in zip(
            nested, family.REPORTER_TELLS_THE_VENDOR.items, strict=True
        ):
            assert mine is theirs

    def test_the_answer_prefix_adds_only_the_note_thread(self):
        """It stops where the Vendor's ``vendor-after-answer`` decision falls.

        That decision follows the Vendor's own answer in the thread, so the
        thread is the last thing the prefix tells and the next item of a
        sibling's story is its own choice.
        """
        assert family.THE_VENDOR_ANSWERS_THE_REPORTER.items == (
            *family.REPORTER_TELLS_THE_VENDOR.items,
            family.the_reporter_asks_about_the_workaround,
        )
        assert family.THE_VENDOR_ANSWERS_THE_REPORTER.path == (
            ("reporter-whom-to-tell", "vendor"),
        )


# ---------------------------------------------------------------------------
# The note thread the Reporter opens (DEMOCI-11-017)
# ---------------------------------------------------------------------------


class TestTheReporterAsksAboutTheWorkaround:
    """One thread: the Reporter asks, the Vendor answers, both are kept."""

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_roster_that_never_filled_stops_the_story_first(self):
        """No note is posted into a case the owner cannot vouch for.

        The fragment reads the roster prop before it acts, so the story stops
        here rather than posting into a case whose participants were never
        confirmed.
        """
        state = story_state(*_SEATED, case=mock_case())

        with (
            patch.object(vendor_opening, "reporter_asks") as thread,
            pytest.raises(DemoStoryError, match="roster the Vendor"),
        ):
            family.the_reporter_asks_about_the_workaround(state)

        thread.assert_not_called()

    def test_the_reporter_asks_from_its_own_session_and_the_vendor_answers(
        self,
    ):
        """The shared question and the Vendor's shared answer (DEMOCI-11-017).

        Both notes are the ones every sibling posts, because the four
        recordings must agree byte for byte up to the Vendor's decision; the
        Vendor's container is the one that watches delivery, being the owner's.
        """
        state = _family_state()
        posted = [
            as_Note(
                name="Question from Reporter", content=WORKAROUND_QUESTION
            ),
            as_Note(name=WORKAROUND_ANSWER_NAME, content=WORKAROUND_ANSWER),
        ]

        with patch.object(
            vendor_opening, "reporter_asks", return_value=posted
        ) as thread:
            family.the_reporter_asks_about_the_workaround(state)

        reporter, watching, case, question, replies = thread.call_args.args
        assert reporter is state.actor(REPORTER)
        assert watching is state.client(family.VENDOR)
        assert case is state.case
        assert question == WORKAROUND_QUESTION
        assert [(p.poster, p.name, p.content) for p in replies] == [
            (
                state.actor(family.VENDOR),
                WORKAROUND_ANSWER_NAME,
                WORKAROUND_ANSWER,
            )
        ]

    def test_both_notes_are_kept_for_the_continuations(self):
        """The question *and* the answer, not only the last note.

        ``rv``'s final case check names both, and every sibling's joiners
        reply to the answer rather than opening a thread of their own
        (DEMOCI-11-017).
        """
        state = _family_state()
        question = as_Note(name="Question from Reporter", content="q")
        answer = as_Note(name=WORKAROUND_ANSWER_NAME, content="a")

        with patch.object(
            vendor_opening, "reporter_asks", return_value=[question, answer]
        ):
            family.the_reporter_asks_about_the_workaround(state)

        assert state.kept(family.REPORTERS_QUESTION) is question
        assert state.kept(family.VENDORS_ANSWER) is answer

    @pytest.mark.spec("DEMOCI-01-011")
    def test_a_thread_whose_gate_failed_keeps_neither_note(self):
        """A failed gate posts nothing at all, so there is nothing to keep.

        Fewer notes than props is the recorded-failure case: the fragments
        that read a prop then stop the story rather than replying to a note
        that is not on the case.
        """
        state = _family_state()

        with patch.object(vendor_opening, "reporter_asks", return_value=[]):
            family.the_reporter_asks_about_the_workaround(state)

        for prop in (family.REPORTERS_QUESTION, family.VENDORS_ANSWER):
            with pytest.raises(DemoStoryError):
                state.kept(prop)

    def test_a_failed_answer_keeps_the_question_it_did_post(self):
        """A failed post reads back as ``None`` beside the ones that landed.

        It is kept per note rather than all-or-nothing, so ``rv``'s case
        check still names the question that is on the case while the
        continuations that reply to the answer stop the story.
        """
        state = _family_state()
        question = as_Note(name="Question from Reporter", content="q")

        with patch.object(
            vendor_opening, "reporter_asks", return_value=[question, None]
        ):
            family.the_reporter_asks_about_the_workaround(state)

        assert state.kept(family.REPORTERS_QUESTION) is question
        with pytest.raises(DemoStoryError, match="workaround answer"):
            state.kept(family.VENDORS_ANSWER)


# ---------------------------------------------------------------------------
# Continuations shared by more than one scenario of the family
# ---------------------------------------------------------------------------


class TestRequiredParticipantsArePresent:
    """The roster milestone, read from Vendor1's replica."""

    @pytest.mark.spec("DEMOCI-01-011")
    def test_the_milestone_reads_the_roster_prop_first(self):
        """Participants that were never seated are not worth checking.

        A roster that never arrived stops the story here, rather than failing
        a milestone whose cause is already recorded above it.
        """
        state = story_state(*_SEATED, case=mock_case())

        with (
            patch.object(
                vendor_continuations, "verify_case_active"
            ) as milestone,
            no_demo_banners(family),
            pytest.raises(DemoStoryError, match="roster the Vendor"),
        ):
            family.required_participants_are_present(state, check="M1")

        milestone.assert_not_called()

    @pytest.mark.spec("VP-02-015")
    def test_the_milestone_reads_vendor1s_replica_and_the_reporters(self):
        """Vendor1 holds the case from its own triage, owner or not.

        The reads are the same in all four scenarios; only the label differs,
        because each numbers its own milestones and names the participants it
        expects by then.
        """
        state = _family_state()

        with (
            patch.object(
                vendor_continuations, "verify_case_active"
            ) as milestone,
            _recording_checks() as labels,
        ):
            family.required_participants_are_present(
                state, check="M1: required participants (≥2), EM.ACTIVE"
            )

        assert labels == ["M1: required participants (≥2), EM.ACTIVE"]
        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["case_id"] == state.case.id_
        assert kwargs["receiver_actor_id"] == state.actor_id(family.VENDOR)
        assert kwargs["reporter_actor_id"] == state.actor_id(REPORTER)


class TestTheFixReadyReachedTheReporter:
    """One copy of the check every scenario of the family makes twice."""

    @pytest.mark.spec("DEMOMA-17-002")
    def test_each_milestone_label_repeats_the_same_check(self):
        """A consolidation must not change what a scenario passes on.

        The second milestone asserts exactly what the first does — ``rv``'s
        M4 and M5, ``rvcv-extension``'s M5 and M6 — so the repetition is kept
        as it was and #5607 tracks making the pair say two different things.
        """
        state = _family_state()

        with (
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(
                vendor_continuations, "verify_fix_ready"
            ) as milestone,
            _recording_checks() as labels,
        ):
            family.the_fix_ready_reached_the_reporter(
                state, milestones=("M4", "M5")
            )

        assert labels == ["M4", "M5"]
        assert milestone.call_count == 2
        # Vendor1's own VF state, read on its replica and on the Reporter's,
        # once per milestone.
        assert [c.kwargs["client"] for c in vf_wait.call_args_list] == [
            state.client(family.VENDOR),
            state.client(REPORTER),
            state.client(family.VENDOR),
            state.client(REPORTER),
        ]
        assert all(
            c.kwargs["actor_id"] == state.actor_id(family.VENDOR)
            and c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )
        kwargs = milestone.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["receiver_actor_id"] == state.actor_id(family.VENDOR)


class TestBothVendorsReportTheFixReady:
    """Both vendors stop at VFd, each gated on its own RM state."""

    @pytest.mark.spec("CSB-15-002")
    def test_vendor1_notifies_then_vendor2_then_the_milestones_run(self):
        """The order is the one every two-vendor sibling told.

        Each trigger is refused until that vendor's own participant record is
        out of triage, which is the gate inside ``vendor_notifies_fix_ready``
        (CSB-18-001); the milestones that read both follow the two triggers.
        """
        state = _family_state(family.VENDOR2)
        order: list[str] = []

        with (
            patch.object(
                vendor_continuations,
                "vendor_notifies_fix_ready",
                side_effect=lambda _s, name, label: order.append(
                    f"notified:{name}:{label}"
                ),
            ),
            patch.object(
                vendor_continuations,
                "the_fix_ready_reached_the_reporter",
                side_effect=lambda _s, milestones: order.append(
                    f"milestones:{list(milestones)}"
                ),
            ),
        ):
            family.both_vendors_report_the_fix_ready(
                state, milestones=("M4", "M5")
            )

        assert order == [
            f"notified:{family.VENDOR}:{family.VENDOR_LABEL}",
            f"notified:{family.VENDOR2}:{family.VENDOR2_LABEL}",
            "milestones:['M4', 'M5']",
        ], order


class TestTheJoinersAddTheirNotes:
    """The actors that joined after the opening answer its thread."""

    @pytest.mark.spec("DEMOCI-11-017")
    def test_the_posts_thread_onto_the_vendors_answer(self):
        """The thread the opening shares with every sibling stays one thread.

        The joiners reply to the Vendor's answer rather than opening a thread
        of their own, and post through Vendor1's replica, which every
        scenario of the family watches.
        """
        state = _family_state(family.VENDOR2)
        answer = as_Note(
            name=WORKAROUND_ANSWER_NAME, content=WORKAROUND_ANSWER
        )
        state.keep(family.VENDORS_ANSWER, answer)
        updates = [
            NotePost(state.actor(family.VENDOR2), "Vendor2 Update", "ours")
        ]

        with patch.object(vendor_continuations, "add_note_thread") as thread:
            family.the_joiners_add_their_notes(state, updates)

        watching, case, posts = thread.call_args.args
        assert watching is state.client(family.VENDOR)
        assert case is state.case
        assert posts is updates
        assert thread.call_args.kwargs["in_reply_to"] is answer

    @pytest.mark.spec("DEMOCI-01-011")
    def test_an_answer_that_never_landed_stops_the_story(self):
        """A thread whose answer never landed has nothing to reply to.

        Posting anyway would put an unthreaded note on the case that the
        scenario's own note assertions do not describe.
        """
        state = _family_state(family.VENDOR2)

        with (
            patch.object(vendor_continuations, "add_note_thread") as thread,
            pytest.raises(DemoStoryError, match="workaround answer"),
        ):
            family.the_joiners_add_their_notes(state, [])

        thread.assert_not_called()


class TestTheEmbargoEndsFor:
    """The termination is read on the replica the next step depends on."""

    @pytest.mark.spec("DEMOMA-07-003")
    def test_only_the_named_watchers_replica_is_read(self):
        """The Case Owner's ``notify-published`` is what ends the embargo.

        Each scenario reads the termination on the replica its own next step
        depends on, so both the label and the watcher are the caller's and
        nothing else is read.
        """
        state = _family_state(family.VENDOR2)

        with (
            patch.object(
                vendor_continuations, "wait_for_case_em_terminated"
            ) as em_wait,
            _recording_checks() as labels,
        ):
            family.the_embargo_ends_for(
                state, check="Embargo terminated", watcher=family.VENDOR2
            )

        assert labels == ["Embargo terminated"]
        assert [c.kwargs["client"] for c in em_wait.call_args_list] == [
            state.client(family.VENDOR2)
        ]
        assert em_wait.call_args.kwargs["case_id"] == state.case.id_


class TestTheDisclosureReachedEveryReplica:
    """The final publication milestone: EM.EXITED, VF and CS.VFdPxa."""

    def test_the_embargo_watch_defaults_to_the_reporter_alone(self):
        """Three of the four scenarios publish as the owner first.

        Their Reporter is the last to be told, so its replica reading
        ``EM.EXITED`` is what the milestone turns on; a scenario whose owner
        publishes last names every participant instead.
        """
        state = _family_state()

        with (
            patch.object(
                vendor_continuations, "wait_for_case_em_terminated"
            ) as em_wait,
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_publicly_disclosed"),
            _recording_checks() as labels,
        ):
            family.the_disclosure_reached_every_replica(state, check="M7")

        assert labels == ["M7"]
        assert [c.kwargs["client"] for c in em_wait.call_args_list] == [
            state.client(REPORTER)
        ]

    def test_every_named_watcher_is_read_in_the_handoff_order(self):
        """``rvcv-handoff``'s owner publishes last, so all four are read.

        The watchers are read in the order given and no other replica is
        touched: the milestone reports what the caller declared, not a set it
        derived.
        """
        state = _family_state("coordinator", family.VENDOR2)
        watchers = ("coordinator", family.VENDOR, family.VENDOR2, REPORTER)

        with (
            patch.object(
                vendor_continuations, "wait_for_case_em_terminated"
            ) as em_wait,
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ),
            patch.object(vendor_continuations, "verify_publicly_disclosed"),
            no_demo_banners(family),
        ):
            family.the_disclosure_reached_every_replica(
                state, check="M7", em_watchers=watchers
            )

        assert [c.kwargs["client"] for c in em_wait.call_args_list] == [
            state.client(who) for who in watchers
        ]

    @pytest.mark.spec("DEMOMA-15-001")
    def test_the_vf_and_disclosure_checks_name_vendor1(self):
        """Vendor1 is the participant with the fix path in all four.

        Its VF state is read on its own replica and on the Reporter's,
        whatever the embargo watch named.
        """
        state = _family_state()

        with (
            patch.object(vendor_continuations, "wait_for_case_em_terminated"),
            patch.object(
                vendor_continuations, "wait_for_participant_vf_state"
            ) as vf_wait,
            patch.object(
                vendor_continuations, "verify_publicly_disclosed"
            ) as disclosed,
            no_demo_banners(family),
        ):
            family.the_disclosure_reached_every_replica(state, check="M7")

        assert [c.kwargs["client"] for c in vf_wait.call_args_list] == [
            state.client(family.VENDOR),
            state.client(REPORTER),
        ]
        assert all(
            c.kwargs["actor_id"] == state.actor_id(family.VENDOR)
            and c.kwargs["expected_states"] == {CS_vf.VF}
            for c in vf_wait.call_args_list
        )
        kwargs = disclosed.call_args.kwargs
        assert kwargs["receiver_client"] is state.client(family.VENDOR)
        assert kwargs["reporter_client"] is state.client(REPORTER)
        assert kwargs["receiver_actor_id"] == state.actor_id(family.VENDOR)


# ---------------------------------------------------------------------------
# The shared cast opening (DEMOCI-11-018, #5532)
# ---------------------------------------------------------------------------


class TestVendorSeats:
    """Two seats, whatever else a scenario runs."""

    def test_the_seats_are_the_two_the_opening_seeds_in_seeder_order(self):
        """The order is ``seed_containers``' return order.

        That is what binds each session to its own container
        (:func:`~vultron.demo.helpers.story_cast.open_story_cast`), so a
        swapped pair would have the Reporter's session talking to the
        Vendor's store.
        """
        reporter_client = mock_client()
        vendor_client = mock_client()

        seats = family.vendor_seats(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_id="urn:test:reporter",
            vendor_id="urn:test:vendor",
        )

        assert [(s.name, s.label) for s in seats] == [
            (REPORTER, REPORTER_LABEL),
            (family.VENDOR, family.VENDOR_LABEL),
        ]
        assert [s.client for s in seats] == [reporter_client, vendor_client]
        assert [s.actor_id for s in seats] == [
            "urn:test:reporter",
            "urn:test:vendor",
        ]

    @pytest.mark.spec("DEMOCI-11-018")
    def test_only_the_cast_opening_seeds_this_familys_containers(self):
        """Nothing a fragment reaches may seed before the case exists.

        Every actor and peer record written then is one more read of the
        recording clock, so a second call site — in particular one reachable
        from a fragment — is how the four recordings would drift apart
        (#5532).  Read from the source, so the claim holds for the code as
        written and not only for the path a test drives.

        The two cast-opening entry points are named as a set rather than a
        list: whether the ``open_cast`` closure seeds through
        :func:`~vultron.demo.helpers.vendor_story.open_vendor_cast` or
        repeats its arguments is a question of duplication, not of when the
        seeding runs, and both answers satisfy this rule.
        """
        seeders = functions_referencing(family, "seed_containers")

        assert seeders, (
            "the source walk found no caller of the seeding — the check is"
            " vacuous"
        )
        assert set(seeders) <= {"open_vendor_cast", "vendor_open_cast"}, (
            "only the cast opening may seed this family's containers;"
            f" {sorted(set(seeders) - {'open_vendor_cast', 'vendor_open_cast'})}"
            " also does (DEMOCI-11-018, #5532)"
        )


@contextlib.contextmanager
def _cast_stubs(seeded, *, seed_error=None) -> Iterator[SimpleNamespace]:
    """Stub the container reset, the seeding and the actor read-back.

    ``open_vendor_cast`` delegates to
    :func:`~vultron.demo.helpers.story_cast.open_story_cast`, so the reset and
    the read-back are looked up on **that** module while the seeder closure
    is looked up on ``vendor_story``: patching all three on one module would
    stub nothing the code under test calls.
    """
    with (
        patch.object(
            story_cast, "reset_datalayer", return_value={"status": "ok"}
        ) as reset,
        patch.object(seeding, "seed_case_actor_identity") as reseed,
        patch.object(
            story_cast, "get_actor_by_id", side_effect=list(seeded)
        ) as lookup,
        patch.object(
            vendor_cast,
            "seed_containers",
            return_value=tuple(seeded),
            side_effect=seed_error,
        ) as seed,
    ):
        yield SimpleNamespace(
            reset=reset, reseed=reseed, lookup=lookup, seed=seed
        )


class TestOpenVendorCast:
    """One reset and one seeding for every scenario of the family."""

    @pytest.mark.spec("DEMOMA-01-003")
    def test_the_reset_covers_every_container_and_reseeds_the_case_actor(self):
        """A run starts clean on every container it will touch.

        The unseated ones included: they are reset here and seeded later
        (#5532).  The dedicated case-actor container is reset last and its
        CaseActor identity re-seeded, because the wipe clears it and every
        proposal is addressed to it (#1876 AC-2, DEMOMA-06-004).
        """
        reporter_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        joiner_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in _SEATED]

        with _cast_stubs(seeded) as stubs:
            family.open_vendor_cast(
                MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
                unseated={
                    _JOINER: UnseatedContainer(
                        family.VENDOR2_LABEL, joiner_client, "urn:test:vendor2"
                    )
                },
            )

        assert [c.kwargs["client"] for c in stubs.reset.call_args_list] == [
            reporter_client,
            vendor_client,
            joiner_client,
            case_actor_client,
        ]
        stubs.reseed.assert_called_once_with(case_actor_client)

    @pytest.mark.spec("DEMOCI-11-018")
    def test_only_the_two_seats_are_seeded_and_the_rest_wait(self):
        """The opening seeds the containers *every* sibling uses.

        A further actor's container is left as an
        :class:`~vultron.demo.helpers.story.UnseatedContainer` with its
        deterministic id, for the fragment that brings that actor into the
        case (#5532).
        """
        reporter_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        joiner_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in _SEATED]

        with _cast_stubs(seeded) as stubs:
            state = family.open_vendor_cast(
                MagicMock(),
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
                reporter_id="urn:test:reporter",
                vendor_id="urn:test:vendor",
                unseated={
                    _JOINER: UnseatedContainer(
                        family.VENDOR2_LABEL, joiner_client, "urn:test:vendor2"
                    )
                },
            )

        kwargs = stubs.seed.call_args.kwargs
        assert kwargs["reporter_client"] is reporter_client
        assert kwargs["vendor_client"] is vendor_client
        assert kwargs["case_actor_client"] is case_actor_client
        assert kwargs["reporter_actor_id"] == "urn:test:reporter"
        assert kwargs["vendor_actor_id"] == "urn:test:vendor"
        assert joiner_client not in kwargs.values(), (
            "a container only some siblings use must not be seeded by the"
            " shared opening (DEMOCI-11-018, #5532)"
        )
        # Each seeded actor is read back from its own container, which is the
        # form a trigger session binds to (ADR-0073).
        assert [c.args[0] for c in stubs.lookup.call_args_list] == [
            reporter_client,
            vendor_client,
        ]
        assert sorted(state.cast) == sorted(_SEATED)
        assert state.case_actor_client is case_actor_client
        assert _JOINER not in state.cast
        assert state.container(_JOINER).client is joiner_client
        assert state.container(_JOINER).actor_id == "urn:test:vendor2"

    def test_a_failed_seeding_leaves_no_cast_to_tell_the_story_with(self):
        """The failure is recorded by ``demo_step``; the story stops here."""
        seeded = [mock_actor(f"urn:test:{name}") for name in _SEATED]

        with (
            _cast_stubs(seeded, seed_error=RuntimeError("unreachable")),
            pytest.raises(DemoStoryError, match="could not be seeded"),
        ):
            family.open_vendor_cast(
                MagicMock(),
                reporter_client=mock_client(),
                vendor_client=mock_client(),
                case_actor_client=mock_client(),
                dump=lambda _state: None,
            )

    def test_the_open_cast_closure_opens_the_same_cast(self):
        """``run_story`` takes a closure, so the harness is bound late.

        Every scenario of the family hands ``run_story`` the same one, which
        is what puts a seeding failure inside the harness that dumps and
        reports it (DEMOMA-17-001).
        """
        reporter_client = mock_client()
        vendor_client = mock_client()
        case_actor_client = mock_client()
        seeded = [mock_actor(f"urn:test:{name}") for name in _SEATED]
        harness = MagicMock()

        with _cast_stubs(seeded) as stubs:
            open_cast = family.vendor_open_cast(
                reporter_client=reporter_client,
                vendor_client=vendor_client,
                case_actor_client=case_actor_client,
                dump=lambda _state: None,
            )
            # Nothing is reset or seeded until ``run_story`` calls it.
            stubs.reset.assert_not_called()
            stubs.seed.assert_not_called()
            state = open_cast(harness)

        assert state.harness is harness
        assert sorted(state.cast) == sorted(_SEATED)
        assert state.client(REPORTER) is reporter_client
        assert state.client(family.VENDOR) is vendor_client


# ---------------------------------------------------------------------------
# The devlogs the invariant harnesses read (DEMOMA-23-002)
# ---------------------------------------------------------------------------


class TestDumpVendorLedgers:
    """Each replica is dumped under the cast name the harness loads."""

    def _dump(self, state, replicas):
        for name in state.cast:
            state.client(name).actor_id = f"http://{name}:7999/actors/{name}"
        state.case_actor_client.actor_id = (
            "http://case-actor:7999/actors/case-actor"
        )
        with patch.object(story_cast, "dump_case_ledgers") as dump:
            family.dump_vendor_ledgers(state, replicas)
        return dump.call_args.kwargs["targets"]

    def test_every_seated_replica_is_dumped_plus_the_canonical_ledger(self):
        """One cast name serves all four: each names its actors the same.

        The canonical ledger is read on the dedicated case-actor container,
        never from a participant's replica (DEMOMA-06-005).
        """
        state = _family_state(family.VENDOR2)
        targets = self._dump(state, (REPORTER, family.VENDOR, family.VENDOR2))

        assert [t.actor_name for t in targets] == [
            REPORTER,
            family.VENDOR,
            family.VENDOR2,
            "case-actor",
        ]
        assert targets[-1].client is state.case_actor_client

    @pytest.mark.spec("DEMOMA-23-003")
    def test_a_cast_name_the_run_never_seated_is_left_out(self):
        """A failure before the seeding must not 404 the dump.

        The dump runs on the way out whether or not an earlier step failed,
        and an unseated container holds no replica to read — so the name is
        dropped rather than dumped as an error.
        """
        state = _family_state()
        targets = self._dump(
            state, (REPORTER, family.VENDOR, "coordinator", family.VENDOR2)
        )

        assert [t.actor_name for t in targets] == [
            REPORTER,
            family.VENDOR,
            "case-actor",
        ]
