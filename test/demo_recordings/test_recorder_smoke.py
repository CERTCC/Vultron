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
(``stub_full_case_reply`` and ``stub_summary_seed``), and a recording made
there could pick up any stub added to them later, so it would not reliably be
the recording the CLI writes.
"""

import json

import pytest

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.demo.helpers.cast import ALL_SLOTS
from vultron.demo.recordings.runner import record_scenario
from vultron.demo.recordings.traces import normalize_run
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.utils.check_tree import walk

pytestmark = pytest.mark.integration

#: The smallest scenario: about 25 seconds of CPU on an idle machine.
_SMOKE_SCENARIO = "rv"


@pytest.mark.timeout(600)
def test_the_recorder_records_a_scenario():
    spec = next(s for s in discover_scenarios() if s.name == _SMOKE_SCENARIO)

    run = record_scenario(spec)

    recording = run.recording
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
    # The same run left a check tree, which nothing commits (DEMOCI-11-056).
    # Its shape is tested in test/demo_unit/; what a real run adds is that the
    # three context managers and the routed client really are the only paths,
    # so every node carries a label and a gate or step that polled a container
    # names the cast member it read (DEMOCI-11-057).
    nodes = list(walk(run.checks))
    assert nodes, "the run entered no demo_step, demo_check or demo_gate"
    assert all(node.label for node in nodes)
    assert {name for node in nodes for name in node.reads} <= {
        slot.name for slot in ALL_SLOTS
    }
    assert any(node.reads for node in nodes), (
        "no check was attributed a container read"
    )


@pytest.mark.timeout(900)
@pytest.mark.spec("DEMOCI-11-055")
def test_two_runs_of_one_unchanged_tree_compare_equal():
    """The determinism the comparison rests on, against real runs.

    ``compare-demo-runs`` with no directory option records each selected
    scenario twice in this process and compares the pair, so two runs of one
    unchanged tree must differ in nothing once normalized.  Every CLI test of
    that form stubs ``record_scenario`` out, so this is the only place the
    claim is made against the real recorder: a process-global the recorder
    forgets to reset would otherwise break the command with no failing test
    (the class of defect ``_scenario_nodes``' blackboard reset exists for).
    """
    spec = next(s for s in discover_scenarios() if s.name == _SMOKE_SCENARIO)

    before = normalize_run(record_scenario(spec).traces)
    after = normalize_run(record_scenario(spec).traces)

    # Guards against an equality that holds because both sides are empty.
    assert before.ledger, "the first run normalized to no ledger"
    assert before.checks, "the first run normalized to no check tree"
    assert before.ledger == after.ledger
    assert before.checks == after.checks
