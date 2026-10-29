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

"""Smoke test: the recorder still runs a scenario end to end.

It records one scenario and checks what the recording is made of: every
replica agrees with the canonical ledger (``record_scenario`` checks that) and
every line is a ``CaseLedgerEntry``.  It does not compare the result with the
committed recording.  A recording may lag ``main`` for a few days; the
scheduled ``demo-recordings`` workflow finds a stale one and files a refresh
Task, so no pull request has to regenerate recordings to pass CI.

This is an integration test, and it lives outside ``test/demo/`` on purpose:
that directory's autouse fixtures stub protocol steps for mock-driven tests
(``stub_full_case_reply`` skips the full-case Invite reply), so a recording made
there would not be the recording the CLI writes.
"""

import json

import pytest

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.demo.recordings.runner import record_scenario
from vultron.demo.scenario.registry import discover_scenarios

pytestmark = pytest.mark.integration

#: The smallest scenario: about 25 seconds of CPU on an idle machine.
_SMOKE_SCENARIO = "rv"


@pytest.mark.timeout(600)
def test_the_recorder_records_a_scenario():
    spec = next(s for s in discover_scenarios() if s.name == _SMOKE_SCENARIO)

    recording = record_scenario(spec)

    entries = [
        CaseLedgerEntry.model_validate(json.loads(line))
        for line in recording.entries
    ]
    assert entries, "the recording is empty"
    assert [entry.log_index for entry in entries] == list(range(len(entries)))
    # The run marked every declared step of the path, within the ledger
    # (record_scenario refuses anything less, DEMOCI-11-017).
    assert [(m.branch_point, m.choice) for m in recording.steps] == list(
        spec.path
    )
