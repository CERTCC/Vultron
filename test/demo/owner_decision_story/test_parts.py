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

"""What both ``owner-keep-case`` continuations act on (#5535).

Pins :mod:`vultron.demo.helpers.owner_decision_story.parts`: the
:class:`~vultron.demo.helpers.owner_decision_story.Part` a continuation takes,
the CaseActor's participant address, and the join both continuations
presuppose (DEMOCI-01-011).
"""

from unittest.mock import patch

import pytest

from test.demo.owner_decision_story._support import (
    JOINED,
    JOINER,
    NEWCOMER,
    OWNER,
    SEATED,
    neutral_state,
    no_banners,
)
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import (
    owner_decision_story as ods,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
)
from vultron.demo.helpers.owner_decision_story import (
    Part,
    parts as owner_decision_parts,
)
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


# ---------------------------------------------------------------------------
# Part and the CaseActor's address
# ---------------------------------------------------------------------------


class TestPart:
    """A part is the story name of a cast member plus its scenario label."""

    def test_a_part_carries_the_cast_name_and_the_label(self):
        """The ``(state, name, label)`` pair, bundled (DEMOMA-17-001)."""
        assert (OWNER.name, OWNER.label) == ("owner", "Owner")

    def test_a_part_is_frozen(self):
        """A continuation cannot reseat the cast it was handed.

        Assigned through ``setattr`` under a variable name, because the field
        is read-only and both a direct assignment and a constant-named
        ``setattr`` are refused by the type checker and the linter before the
        test can run.
        """
        field = "name"
        with pytest.raises(AttributeError):
            setattr(OWNER, field, "someone-else")

    def test_the_reporter_is_the_default_witness_part(self):
        """Every scenario of the tree seats its Reporter under that name."""
        assert Part(REPORTER, REPORTER_LABEL) == ods.REPORTER_PART


class TestCaseActorParticipant:
    """The CASE_MANAGER's address is read off a replica, never assumed."""

    def test_the_id_comes_from_the_replica_it_is_handed(self):
        """So the check names the actor actually holding CASE_MANAGER.

        It takes the client and the case id rather than the story's state: it
        is a polling-style helper, not a fragment, and owns no demo context of
        its own.
        """
        state = neutral_state()

        with patch.object(
            owner_decision_parts,
            "find_case_actor_participant_id",
            return_value="urn:test:case-actor-participant",
        ) as lookup:
            found = ods.case_actor_participant(
                state.client(OWNER.name), state.case.id_
            )

        assert found == "urn:test:case-actor-participant"
        assert lookup.call_args.args == (
            state.client(OWNER.name),
            state.case.id_,
        )

    def test_a_replica_naming_no_case_actor_raises_for_its_gate(self):
        """The Accept would have nowhere to route back to (CM-16-006).

        It raises rather than returning ``None``: every caller reads it inside
        a ``demo_gate``, which records the failure and skips the dependents
        (DEMOCI-01-011).
        """
        state = neutral_state()

        with (
            patch.object(
                owner_decision_parts,
                "find_case_actor_participant_id",
                return_value=None,
            ),
            pytest.raises(AssertionError, match="no CaseActor participant"),
        ):
            ods.case_actor_participant(
                state.client(OWNER.name), state.case.id_
            )


# ---------------------------------------------------------------------------
# What each continuation presupposes (DEMOCI-01-011, #5535)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-01-011")
@pytest.mark.spec("DEMOMA-17-002")
class TestAJoinThatNeverLandedStopsTheStory:
    """Both continuations read the joiner's join before anything else.

    Before composition the owner's decision nested inside the roster's own
    ``demo_gate``, so a roster that never filled skipped it. A flat story
    cannot nest, so the gate keeps a prop and each continuation reads it
    first — and the reading raises, which is how ``run_story`` stops the
    story with the roster's failure as the headline (#5535).
    """

    def test_the_suggestion_is_not_made_without_the_join(self):
        """A non-participant may suggest nobody (DEMOMA-13-003)."""
        state = neutral_state(joined=False)

        with (
            patch.object(ActorSession, "suggest_actor_to_case") as suggest,
            no_banners(),
            pytest.raises(DemoStoryError, match="test pair's join"),
        ):
            ods.the_owner_approves_a_suggested_actor(
                state,
                joined=JOINED,
                owner=OWNER,
                suggester=JOINER,
                newcomer=NEWCOMER,
                roles=[CVDRole.VENDOR],
                seated=SEATED,
            )

        suggest.assert_not_called()

    def test_the_case_is_not_offered_without_the_join(self):
        """The transferee must be an active participant (DEMOMA-14-010)."""
        state = neutral_state(joined=False)

        with (
            patch.object(
                ActorSession, "offer_case_ownership_transfer"
            ) as offer,
            no_banners(),
            pytest.raises(DemoStoryError, match="test pair's join"),
        ):
            ods.the_owner_hands_the_case_over(
                state, joined=JOINED, owner=OWNER, new_owner=JOINER
            )

        offer.assert_not_called()
