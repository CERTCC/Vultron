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

"""Tests of :mod:`vultron.demo.helpers.owner_decision_story.parts`."""

from unittest.mock import patch

import pytest

from test.demo.owner_decision_story._support import (
    OWNER,
    continuation_state,
)
from vultron.demo.helpers import (
    owner_decision_story as ods,
)
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
)
from vultron.demo.helpers.owner_decision_story import (
    Part,
    parts as owner_parts,
)

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
        state = continuation_state()

        with patch.object(
            owner_parts,
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
        state = continuation_state()

        with (
            patch.object(
                owner_parts,
                "find_case_actor_participant_id",
                return_value=None,
            ),
            pytest.raises(AssertionError, match="no CaseActor participant"),
        ):
            ods.case_actor_participant(
                state.client(OWNER.name), state.case.id_
            )
