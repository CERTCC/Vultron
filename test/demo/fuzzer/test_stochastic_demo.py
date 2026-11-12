#!/usr/bin/env python
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
"""Tests for the in-process STOCHASTIC bundle demo scenario (issue #1672 AC-4).

Verifies that :func:`run_stochastic_demo` runs without error and produces
outcome log lines in the expected format.
"""

import logging


def test_stochastic_demo_runs_without_error():
    """run_stochastic_demo() completes without raising an exception (AC-4)."""
    from vultron.demo.fuzzer.stochastic_demo import run_stochastic_demo

    run_stochastic_demo(n_ticks=2)


def test_stochastic_demo_produces_outcome_log_lines(caplog):
    """run_stochastic_demo() emits call-out point outcome lines (AC-2, AC-4).

    Each outcome line must contain:
    - the literal string 'call-out point outcome'
    - a node= segment
    - a result= segment with SUCCESS, FAILURE, or INVALID
    """
    from vultron.demo.fuzzer.stochastic_demo import run_stochastic_demo

    with caplog.at_level(
        logging.INFO, logger="vultron.demo.fuzzer.stochastic_demo"
    ):
        run_stochastic_demo(n_ticks=2)

    outcome_lines = [
        r.message
        for r in caplog.records
        if "call-out point outcome" in r.message
    ]
    assert len(outcome_lines) > 0, "Expected at least one outcome log line"

    for line in outcome_lines:
        assert "node=" in line, f"Missing node= in: {line}"
        assert "result=" in line, f"Missing result= in: {line}"
        result_value = line.split("result=")[-1].strip()
        assert result_value in {
            "SUCCESS",
            "FAILURE",
            "INVALID",
        }, f"Unexpected result value in: {line}"


def test_stochastic_demo_covers_all_three_domains(caplog):
    """Outcome lines span validation, prioritization, and embargo domains (AC-1)."""
    from vultron.demo.fuzzer.stochastic_demo import run_stochastic_demo

    with caplog.at_level(
        logging.INFO, logger="vultron.demo.fuzzer.stochastic_demo"
    ):
        run_stochastic_demo(n_ticks=1)

    messages = " ".join(r.message for r in caplog.records)

    # Validation domain nodes
    assert "EvaluateReportCredibility" in messages
    assert "EvaluateReportValidity" in messages

    # Prioritization domain nodes
    assert "OnAccept" in messages or "OnDefer" in messages

    # Embargo domain nodes
    assert "ExitEmbargoWhenDeployed" in messages
    assert "WantToProposeEmbargo" in messages


def test_stochastic_demo_module_importable():
    """Module is importable as vultron.demo.fuzzer.stochastic_demo (AC-3)."""
    import importlib

    mod = importlib.import_module("vultron.demo.fuzzer.stochastic_demo")
    assert hasattr(mod, "run_stochastic_demo")
    assert callable(mod.run_stochastic_demo)


def test_each_embargo_tree_tick_is_one_act(monkeypatch):
    """Each full-tree tick reads the act clock once, inside the tree lock,
    and hands that instant to its bridge run as ``at`` (ADR-0176)."""
    from datetime import UTC, datetime

    from test.support.act_clock import CountingClock
    from vultron.adapters.driven.clock import install_act_clock
    from vultron.core.behaviors.bridge import BTBridge
    from vultron.demo.fuzzer import stochastic_demo

    first = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    second = datetime(2026, 3, 1, 12, 1, tzinfo=UTC)
    clock = CountingClock(first, second)

    seen: list[object] = []
    original = BTBridge.execute_with_setup

    def recording(self, *args, **kwargs):
        seen.append(kwargs.get("at"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BTBridge, "execute_with_setup", recording)

    with install_act_clock(clock):
        stochastic_demo._run_embargo_full_tree(n_ticks=2)

    assert clock.reads == 2
    assert clock.locked_at_read == [True, True]
    assert seen == [first, second]
