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
"""The 5-party scenario suggests Vendor 2 from its declared table (BT-24-007).

Runs ``rcvcv`` end to end in this process, one isolated app per container
slot, with the static participant-suggestion adapter it declares, and checks
that the suggestion C2 makes is the one that adapter answered: V2, as Vendor
and Deployer, read from C2's own replica through the core service.  The
fragment tests in ``test/demo/rcvcv_demo/`` check the same answer against a
stand-in cast; this run is where it meets real containers, the trap the
in-process and Docker harnesses differ on (``notes/testing-pitfalls.md``).

An integration test outside ``test/demo/``, for the reason
``test_recorder_smoke.py`` gives: that directory's autouse fixtures stub
protocol steps.
"""

import json
from unittest.mock import patch

import pytest

from vultron.demo.helpers.participant_suggestion import (
    SuggestedActor,
    ask_who_else_belongs,
)
from vultron.demo.recordings.runner import record_scenario
from vultron.demo.scenario.rcvcv_demo import fragments
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils.check_tree import CheckOutcome, walk
from vultron.enums import CVDRole

pytestmark = pytest.mark.integration


@pytest.mark.timeout(900)
@pytest.mark.spec("BT-24-007")
@pytest.mark.spec("DEMOMA-19-009")
def test_rcvcv_suggests_vendor2_from_its_declared_table():
    spec = next(s for s in discover_scenarios() if s.name == "rcvcv")
    answers: list[tuple[SuggestedActor, ...]] = []

    def _recording_ask(*args, **kwargs):
        answer = ask_who_else_belongs(*args, **kwargs)
        answers.append(answer)
        return answer

    with patch.object(
        fragments, "ask_who_else_belongs", side_effect=_recording_ask
    ):
        run = record_scenario(spec)

    # C2 asked once, and the adapter named V2 in both of its table rows.
    assert len(answers) == 1
    (suggested,) = answers[0]
    assert suggested.part.name == fragments.V2
    assert suggested.roles == (CVDRole.VENDOR, CVDRole.DEPLOYER)

    # The ask's gate passed in the real run.
    asks = [
        node
        for node in walk(run.checks)
        if "participant suggester" in node.label
    ]
    assert [node.outcome for node in asks] == [CheckOutcome.PASSED]

    # The Offer(CaseParticipant) the CaseActor ledgered names the actor the
    # adapter answered, so the suggestion came from the answer (AC-2).
    offers = [
        json.loads(line)
        for line in run.recording.entries
        if json.loads(line)["semanticType"] == "offer_case_participant"
    ]
    assert [
        o["payloadSnapshot"]["object"]["attributedTo"] for o in offers
    ] == [suggested.actor_id]
