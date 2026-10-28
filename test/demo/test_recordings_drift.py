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
comparison.

Each scenario runs for up to two minutes, so this is an integration test.
"""

import pytest

from vultron.demo.recordings import (
    RECORDINGS_DIR,
    REGENERATE_COMMAND,
    record_scenario,
    recording_path,
)
from vultron.demo.scenario.registry import discover_scenarios

#: The slowest scenario (rcvcv) runs in about 95 seconds on an idle machine.
_SCENARIO_TIMEOUT_SECONDS = 900


@pytest.mark.timeout(_SCENARIO_TIMEOUT_SECONDS)
@pytest.mark.parametrize("spec", discover_scenarios(), ids=lambda s: s.name)
def test_committed_recording_matches_a_fresh_run(spec):
    regenerate = f"{REGENERATE_COMMAND} --scenario {spec.name}"
    fresh = record_scenario(spec)

    committed = sorted(
        path.stem for path in (RECORDINGS_DIR / spec.name).glob("*.jsonl")
    )
    assert committed == sorted(fresh), (
        f"the committed recording of {spec.name!r} holds ledgers for "
        f"{committed}, but a fresh run dumps {sorted(fresh)}. "
        f"Regenerate it: {regenerate}"
    )
    stale = [
        actor
        for actor, text in fresh.items()
        if recording_path(spec.name, actor).read_text(encoding="utf-8") != text
    ]
    assert not stale, (
        f"the committed recording of {spec.name!r} differs from a fresh run "
        f"for {stale}. Regenerate it: {regenerate}"
    )
