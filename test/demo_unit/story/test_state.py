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

"""What a running story carries: its state, its props, its seats.

Pins :mod:`vultron.demo.helpers.story.state`: :class:`StoryState`, the
:class:`StoryProp` artifacts kept on it, and a character actor seated
mid-story.

The rules *about* the declared props — one name per declaration, a keep site
and a read site each, and a required keyword on the step that reads one — are
enumerated from the declaration sites in
``test/architecture/test_story_props_have_readers.py`` (DEMOMA-22-019,
DEMOMA-22-014 and DEMOMA-22-016 respectively).  One enumeration serves them
all, so this module pins the behaviour of a single prop on a single state and
nothing walks the demo packages twice.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from test.demo_unit.story._support import (
    KEPT_ID,
    make_session,
    make_state,
)
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
    UnseatedContainer,
)
from vultron.errors import (
    DemoStoryError,
)

# ---------------------------------------------------------------------------
# StoryState
# ---------------------------------------------------------------------------


class TestStoryState:
    def test_an_unseated_actor_names_the_cast_it_is_missing_from(self) -> None:
        state = make_state(reporter=make_session("urn:test:reporter"))
        with pytest.raises(DemoStoryError, match=r"it seats \['reporter'\]"):
            state.actor("vendor")

    def test_reading_the_case_before_it_opens_raises(self) -> None:
        state = make_state(reporter=make_session("urn:test:reporter"))
        with pytest.raises(DemoStoryError, match="has not opened a case"):
            _ = state.case
        with pytest.raises(DemoStoryError, match="no report yet"):
            _ = state.report
        with pytest.raises(DemoStoryError, match="no report Offer yet"):
            _ = state.offer

    def test_opening_the_case_arms_the_dump_and_follows_the_ledger(
        self,
    ) -> None:
        """DEMOMA-23-003: the dump is registered the moment there is a case."""
        state = make_state(reporter=make_session("urn:test:reporter"))
        case = MagicMock(id_="urn:test:case")
        dumped: list[StoryState] = []
        state.dump = dumped.append

        state.open_case(case=case, report=MagicMock(), offer=MagicMock())

        assert state.case is case
        harness = cast(MagicMock, state.harness)
        harness.follow_ledger.assert_called_once_with(
            state.case_actor_client, "urn:test:case"
        )
        harness.dump_with.assert_called_once()
        harness.dump_with.call_args.args[0]()
        assert dumped == [state]

    @pytest.mark.spec("DEMOMA-23-003")
    def test_restating_the_case_replaces_it_without_re_arming_the_dump(
        self,
    ) -> None:
        """For a step that re-reads the case after an act changed it.

        The dump is armed at the first instant there is anything to dump and
        exactly once (ISSUE-2239), so a restate must not arm a second one or
        follow a second ledger — including when an ownership transfer moves
        the case to another owner mid-story (#5535).
        """
        state = make_state()
        opened = MagicMock(id_="urn:test:case")
        state.open_case(case=opened, report=MagicMock(), offer=MagicMock())
        harness = cast(MagicMock, state.harness)
        harness.reset_mock()

        restated = MagicMock(id_="urn:test:case")
        state.restate_case(restated)

        assert state.case is restated
        harness.dump_with.assert_not_called()
        harness.follow_ledger.assert_not_called()

    def test_restating_a_case_the_story_never_opened_raises(self) -> None:
        """Restating first would arm no dump and follow no ledger."""
        with pytest.raises(DemoStoryError, match="no case to restate"):
            make_state().restate_case(MagicMock(id_="urn:test:case"))

    @pytest.mark.spec("DEMOMA-23-003")
    def test_restating_a_different_case_is_refused(self) -> None:
        """A restate is about the case the story opened, never another one.

        No act of a scenario changes a case's id — an ownership transfer moves
        ``attributed_to`` and leaves the id alone (CM-21-024) — so a different
        id means the fragment read the wrong record.  Taking it would leave
        every later fragment acting on one case while the armed dump and the
        followed ledger still belong to the first (#5535).
        """
        state = make_state()
        state.open_case(
            case=MagicMock(id_="urn:test:case"),
            report=MagicMock(),
            offer=MagicMock(),
        )

        with pytest.raises(DemoStoryError, match="asked to restate it as"):
            state.restate_case(MagicMock(id_="urn:test:other-case"))

        assert state.case.id_ == "urn:test:case"

    @pytest.mark.spec("DEMOMA-23-003")
    def test_opening_a_second_case_is_refused(self) -> None:
        """Re-opening would arm a second dump, which is what restate avoids."""
        state = make_state()
        state.open_case(
            case=MagicMock(id_="urn:test:case"),
            report=MagicMock(),
            offer=MagicMock(),
        )
        with pytest.raises(DemoStoryError, match="opened a case already"):
            state.open_case(
                case=MagicMock(id_="urn:test:case"),
                report=MagicMock(),
                offer=MagicMock(),
            )
        cast(MagicMock, state.harness).dump_with.assert_called_once()

    def test_a_delivered_invite_is_read_back_by_cast_name(self) -> None:
        state = make_state(vendor=make_session("urn:test:vendor"))
        assert state.delivered_invite("vendor") is None
        state.invited("vendor", "urn:test:invite")
        assert state.delivered_invite("vendor") == "urn:test:invite"

    def test_an_undelivered_invite_clears_the_slot(self) -> None:
        """``None`` is what the answer fragment refuses in its own gate."""
        state = make_state(vendor=make_session("urn:test:vendor"))
        state.invited("vendor", "urn:test:invite")
        state.invited("vendor", None)
        assert state.delivered_invite("vendor") is None

    def test_an_invite_for_an_unseated_actor_raises(self) -> None:
        state = make_state(vendor=make_session("urn:test:vendor"))
        with pytest.raises(DemoStoryError, match="does not seat"):
            state.invited("coordinator", "urn:test:invite")
        with pytest.raises(DemoStoryError, match="does not seat"):
            state.delivered_invite("coordinator")

    def test_an_actor_with_no_id_cannot_decide_a_step(self) -> None:
        session = make_session("urn:test:reporter")
        cast(MagicMock, session.actor).id_ = None
        state = make_state(reporter=session)
        with pytest.raises(DemoStoryError, match="has no actor id"):
            state.actor_id("reporter")


# ---------------------------------------------------------------------------
# run_story
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOMA-17-001")
class TestStoryProps:
    """What one family passes between its own steps (#5534).

    A prop rather than a field on the state or a per-family subclass: a
    fragment is typed ``Callable[[StoryState], None]``, so a subclass of the
    state is not assignable to it.
    """

    def test_a_kept_prop_is_read_back_by_the_later_fragment(self) -> None:
        state = make_state()
        state.keep(KEPT_ID, "urn:uuid:embargo-1")
        assert state.kept(KEPT_ID) == "urn:uuid:embargo-1"

    def test_a_prop_no_fragment_kept_raises(self) -> None:
        """The accessor raises rather than handing back a ``None``.

        That is what lets ``run_story`` stop a story whose earlier step failed
        instead of acting on a stand-in.
        """
        with pytest.raises(DemoStoryError, match="embargo in force"):
            make_state().kept(KEPT_ID)

    def test_a_value_of_the_wrong_type_is_refused_where_it_is_kept(
        self,
    ) -> None:
        """A helper that records its own failure returns ``None``.

        Keeping that would leave the dependent fragment reading a stand-in, so
        the refusal happens on the way in, not on the way out.
        """
        state = make_state()
        with pytest.raises(DemoStoryError, match="is not one"):
            state.keep(KEPT_ID, cast(Any, None))
        with pytest.raises(DemoStoryError):
            state.kept(KEPT_ID)

    def test_two_props_of_the_same_type_do_not_collide(self) -> None:
        """A second revision keeps a second prop, never overwrites the first.

        Overwriting would leave the previous id in place when a revision
        failed, and the steps that presuppose the new one would run against
        the old embargo instead of stopping.

        This is the half of the name rule a single state can show: two
        different names are two artifacts.  The other half, that no two
        *declarations* spell one name, is enumerated from the declaration
        sites in ``test/architecture/test_story_props_have_readers.py``
        (``test_every_prop_name_is_declared_once``), which reads every module
        under ``vultron/demo/`` including a package's ``__init__``.
        """
        revised: StoryProp[str] = StoryProp("revised embargo", str)
        state = make_state()
        state.keep(KEPT_ID, "first")
        state.keep(revised, "second")
        assert (state.kept(KEPT_ID), state.kept(revised)) == (
            "first",
            "second",
        )


@pytest.mark.spec("DEMOCI-11-018")
class TestSeatingACharacterActor:
    """Containers the shared opening leaves for a later step to seed.

    The opening seeds only the containers every sibling of the family uses:
    each actor and peer record it writes is one more read of the recording
    clock, so one extra container moves the first ledger entry's timestamp
    away from the siblings whose bytes it must match (#5532, #5534).
    """

    def test_a_waiting_container_carries_its_client_and_deterministic_id(
        self,
    ) -> None:
        client = MagicMock(base_url="v2")
        state = make_state(
            unseated={"v2": UnseatedContainer("V2", client, "urn:test:v2")}
        )
        waiting = state.container("v2")
        assert (waiting.client, waiting.actor_id) == (client, "urn:test:v2")

    def test_seating_moves_the_name_from_waiting_to_the_cast(self) -> None:
        state = make_state(
            unseated={"v2": UnseatedContainer("V2", MagicMock(), None)}
        )
        session = make_session("urn:test:v2")
        state.seat("v2", session)
        assert state.actor("v2") is session
        assert "v2" not in state.unseated

    def test_seating_a_name_twice_is_refused(self) -> None:
        """Re-seating would redirect every later fragment that names it."""
        state = make_state(
            unseated={"v2": UnseatedContainer("V2", MagicMock(), None)}
        )
        state.seat("v2", make_session("urn:test:v2"))
        with pytest.raises(DemoStoryError, match="already seats"):
            state.seat("v2", make_session("urn:test:other"))

    def test_seating_a_name_no_container_waited_for_is_refused(self) -> None:
        with pytest.raises(DemoStoryError, match="no container waiting"):
            make_state().seat("v2", make_session("urn:test:v2"))

    def test_an_unseated_actor_says_the_container_is_still_waiting(
        self,
    ) -> None:
        """The message tells a reader which half of the handover is missing."""
        state = make_state(
            unseated={"v2": UnseatedContainer("V2", MagicMock(), None)}
        )
        with pytest.raises(DemoStoryError, match="does not seat yet"):
            state.actor("v2")
