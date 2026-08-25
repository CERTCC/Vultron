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

"""Tests for third-party log-noise suppression (SL-04-007).

The ``transitions`` library logs ``"<Machine> Finished processing state X
enter/exit callbacks."`` at INFO on every RM/EM/CS/PEC state machine step.
Those are FSM internals, so SL-04-007 requires they stay off the INFO channel.
"""

import logging

import pytest

from vultron.logging_setup import (
    NOISY_INFO_LOGGERS,
    restore_third_party_log_levels,
    suppress_third_party_info_noise,
)


@pytest.fixture(autouse=True)
def _restore_logger_levels():
    """Restore the noisy loggers' levels so tests do not leak configuration."""
    saved = {
        name: logging.getLogger(name).level for name in NOISY_INFO_LOGGERS
    }
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def test_transitions_is_in_the_noisy_logger_list():
    """The `transitions` FSM library is the SL-04-007 target."""
    assert "transitions" in NOISY_INFO_LOGGERS


def test_info_app_level_pins_noisy_loggers_to_warning():
    """At app INFO, the FSM callback chatter is suppressed."""
    suppress_third_party_info_noise(logging.INFO)

    transitions_logger = logging.getLogger("transitions")
    assert transitions_logger.level == logging.WARNING
    assert not transitions_logger.isEnabledFor(logging.INFO)


def test_debug_app_level_keeps_noisy_loggers_available():
    """At app DEBUG the library output is still available for debugging."""
    suppress_third_party_info_noise(logging.DEBUG)

    transitions_logger = logging.getLogger("transitions")
    assert transitions_logger.level == logging.DEBUG
    assert transitions_logger.isEnabledFor(logging.INFO)


def test_warning_app_level_also_suppresses():
    """Levels above INFO also suppress the library chatter."""
    suppress_third_party_info_noise(logging.WARNING)

    assert logging.getLogger("transitions").level == logging.WARNING


def test_em_machine_callbacks_produce_no_info_records(caplog):
    """An EM state transition emits no `transitions` INFO record."""
    from vultron.core.states.em import EM_Trigger, create_em_machine

    suppress_third_party_info_noise(logging.INFO)

    class _Model:
        pass

    model = _Model()
    machine = create_em_machine()
    machine.add_model(model)

    with caplog.at_level(logging.INFO):
        getattr(model, str(EM_Trigger.PROPOSE))()

    fsm_records = [
        r
        for r in caplog.records
        if r.name.startswith("transitions") and r.levelno == logging.INFO
    ]
    assert not fsm_records, (
        "transitions FSM callback lines must not reach INFO (SL-04-007);"
        f" got {[r.getMessage() for r in fsm_records]}"
    )


def test_restore_returns_loggers_to_their_prior_level():
    """Suppression is undoable so it does not leak out of an entry point.

    The FastAPI lifespan calls this on shutdown; without it, one TestClient
    lifetime silently reconfigured `transitions` for every test that followed.
    """
    transitions_logger = logging.getLogger("transitions")
    transitions_logger.setLevel(logging.NOTSET)

    suppress_third_party_info_noise(logging.INFO)
    assert transitions_logger.level == logging.WARNING

    restore_third_party_log_levels()
    assert transitions_logger.level == logging.NOTSET


def test_restore_is_idempotent_and_safe_without_suppression():
    """Calling restore with nothing suppressed is a no-op, not an error."""
    transitions_logger = logging.getLogger("transitions")
    transitions_logger.setLevel(logging.ERROR)

    restore_third_party_log_levels()
    restore_third_party_log_levels()

    assert transitions_logger.level == logging.ERROR


def test_restore_preserves_the_original_level_across_repeat_suppression():
    """Repeat suppression must not overwrite the saved original level."""
    transitions_logger = logging.getLogger("transitions")
    transitions_logger.setLevel(logging.NOTSET)

    suppress_third_party_info_noise(logging.INFO)
    suppress_third_party_info_noise(logging.INFO)
    restore_third_party_log_levels()

    assert transitions_logger.level == logging.NOTSET


def test_server_lifespan_does_not_leak_suppression(monkeypatch):
    """A TestClient lifetime restores third-party levels on shutdown."""
    from fastapi.testclient import TestClient

    from vultron.adapters.driving.fastapi.app import app_v2

    transitions_logger = logging.getLogger("transitions")
    transitions_logger.setLevel(logging.NOTSET)

    with TestClient(app_v2):
        pass

    assert transitions_logger.level == logging.NOTSET, (
        "configure_logging() pinned `transitions` globally; the lifespan"
        " shutdown must restore it"
    )


def test_configure_logging_wires_up_suppression(monkeypatch):
    """AC-6 wire-up: configure_logging() calls the suppression helper.

    The call is a one-liner a refactor could silently drop while every
    unit test of the helper itself stayed green.
    """
    from vultron.adapters.driving.fastapi import app as app_module

    calls: list[int] = []
    monkeypatch.setattr(
        "vultron.logging_setup.suppress_third_party_info_noise",
        lambda level: calls.append(level),
    )

    app_module.configure_logging()

    assert calls, "configure_logging() must suppress third-party INFO noise"


def test_demo_cli_wires_up_suppression(monkeypatch):
    """AC-6 wire-up: the demo CLI calls the suppression helper."""
    import click

    import vultron.demo.cli as cli_module

    calls: list[int] = []
    monkeypatch.setattr(
        cli_module, "suppress_third_party_info_noise", calls.append
    )

    # Invoke the group callback directly: `--help` short-circuits before it.
    # The callback is @click.pass_context-decorated, so it needs an active
    # context rather than one passed positionally.
    with click.Context(cli_module.main):
        cli_module.main.callback(debug=False, log_file=None)  # type: ignore[misc]

    assert calls, "demo CLI main() must suppress third-party INFO noise"
    assert calls == [logging.INFO]
