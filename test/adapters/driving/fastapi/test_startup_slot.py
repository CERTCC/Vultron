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

"""Unit tests for ``StartupSlot`` (#3985)."""

import pytest

from vultron.adapters.driving.fastapi.startup_slot import StartupSlot


def test_a_new_slot_holds_nothing():
    assert StartupSlot[object]().value is None


def test_install_replaces_the_held_value():
    slot: StartupSlot[str] = StartupSlot()
    slot.install("first")
    slot.install("second")
    assert slot.value == "second"


def test_clear_forgets_the_held_value():
    slot: StartupSlot[str] = StartupSlot()
    slot.install("held")
    slot.clear()
    assert slot.value is None


def test_monkeypatch_restores_the_held_value(monkeypatch):
    """Tests swap a slot's value with ``monkeypatch``; undo restores it."""
    slot: StartupSlot[str] = StartupSlot()
    slot.install("original")
    monkeypatch.setattr(slot, "value", "replacement")
    assert slot.value == "replacement"
    monkeypatch.undo()
    assert slot.value == "original"


def test_a_slot_accepts_no_other_attributes():
    slot: StartupSlot[str] = StartupSlot()
    with pytest.raises(AttributeError):
        slot.other = "x"  # type: ignore[attr-defined]
