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

"""Drift test: each committed recording equals a fresh run of its scenario.

The comparison is byte for byte, as for ``protocol_states.json``.  A fresh run
is deterministic (seeded ids, a stepping clock), and the committed files were
written by another process, so a pass also shows that the output does not
depend on the process that made it.  No scenario needs a normalized
comparison.  Only the canonical ledger is committed; ``record_scenario`` checks
every replica the run dumped against it, so a replica that disagrees fails here
too.

Each scenario runs for up to two minutes, so this is an integration test.

It lives outside ``test/demo/`` on purpose: that directory's autouse fixtures
stub protocol steps for mock-driven tests (``stub_full_case_reply`` skips the
full-case Invite reply), so a recording made there would not be the recording
the CLI writes.
"""

import pytest

from vultron.demo.recordings import (
    REGENERATE_COMMAND,
    record_scenario,
    recording_path,
)
from vultron.demo.scenario.registry import discover_scenarios

pytestmark = pytest.mark.integration

#: The slowest scenario (rcvcv) runs in about 95 seconds on an idle machine.
_SCENARIO_TIMEOUT_SECONDS = 900


@pytest.mark.timeout(_SCENARIO_TIMEOUT_SECONDS)
@pytest.mark.parametrize("spec", discover_scenarios(), ids=lambda s: s.name)
def test_committed_recording_matches_a_fresh_run(spec):
    fresh = record_scenario(spec)

    committed = recording_path(spec.name).read_text(encoding="utf-8")
    assert committed == fresh, (
        f"the committed recording of {spec.name!r} differs from a fresh run. "
        f"Regenerate it: {REGENERATE_COMMAND} --scenario {spec.name}"
    )
