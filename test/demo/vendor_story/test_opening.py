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

"""The vendor-first family's shared opening and its prefixes (#5536).

Pins :mod:`vultron.demo.helpers.vendor_story.opening`: the Reporter tells
the Vendor (DEMOMA-23-003, DEMOCI-01-011), the named prefixes
(``notes/demo-scenario-tree.md`` § "Composition") and the note thread the
Reporter opens (DEMOCI-11-017).
"""

import contextlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from test.demo._helpers import (
    gate_failures,
    mock_case,
    no_demo_banners,
    story_state,
)
from test.demo.vendor_story._support import SEATED, family_state
from test.support.objects import make
from vultron.demo.helpers import (
    coordinated_story,
    vendor_story as family,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    joining as coordinated_joining,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_ANSWER,
    WORKAROUND_ANSWER_NAME,
    WORKAROUND_QUESTION,
)
from vultron.demo.helpers.story import Choose
from vultron.demo.helpers.vendor_story import (
    opening as vendor_opening,
)
from vultron.demo.utils.failures import _demo_failures
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


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
        state = story_state(*SEATED)
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
        assert not gate_failures(), gate_failures()

    def test_the_triage_runs_on_the_familys_one_budget(self):
        """The four scenarios share one copy, so they share one budget.

        The ``rvcv`` pair set the value — 60 s for a run that brings five
        actor containers up under CI load — and a budget only bounds how long
        a wait may take, so the narrower siblings inherit it without
        admitting or refusing anything differently (DEMOCI-11-018).
        """
        state = story_state(*SEATED)

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
        state = story_state(*SEATED)
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
        state = story_state(*SEATED)
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
        assert gate_failures(), _demo_failures

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
        state = story_state(*SEATED)
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
        assert gate_failures(), _demo_failures

    @pytest.mark.spec("CLP-08-005")
    def test_the_reporter_holds_the_case_inside_the_same_gate(self):
        """Bug #2135: a later step broadcasts the ledger to the Reporter.

        A Reporter without the case has no genesis hash to anchor the chain
        on, so the replica wait runs inside the roster's gate and reads the
        Reporter's own container.
        """
        state = story_state(*SEATED)

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
        state = story_state(*SEATED)
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
        state = story_state(*SEATED)
        case = mock_case()

        with _opening_stubs(case, reread=mock_case("urn:test:another-case")):
            family.the_reporter_tells_the_vendor(state)

        assert state.case is case
        with pytest.raises(DemoStoryError, match="roster the Vendor"):
            state.kept(family.THE_VENDORS_CASE)
        assert gate_failures(), _demo_failures


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
        state = story_state(*SEATED, case=mock_case())

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
        state = family_state()
        posted = [
            make(
                as_Note,
                name="Question from Reporter",
                content=WORKAROUND_QUESTION,
            ),
            make(
                as_Note, name=WORKAROUND_ANSWER_NAME, content=WORKAROUND_ANSWER
            ),
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
        state = family_state()
        question = make(as_Note, name="Question from Reporter", content="q")
        answer = make(as_Note, name=WORKAROUND_ANSWER_NAME, content="a")

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
        state = family_state()

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
        state = family_state()
        question = make(as_Note, name="Question from Reporter", content="q")

        with patch.object(
            vendor_opening, "reporter_asks", return_value=[question, None]
        ):
            family.the_reporter_asks_about_the_workaround(state)

        assert state.kept(family.REPORTERS_QUESTION) is question
        with pytest.raises(DemoStoryError, match="workaround answer"):
            state.kept(family.VENDORS_ANSWER)
