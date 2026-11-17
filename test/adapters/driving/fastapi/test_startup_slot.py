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

from vultron.adapters.driving.fastapi.startup_slot import StartupSlot


def test_a_new_slot_holds_nothing():
    assert StartupSlot[object]().value is None


def test_install_replaces_the_held_value():
    slot: StartupSlot[str] = StartupSlot()
    slot.install("first")
    slot.install("second")
    assert slot.value == "second"


def test_undo_puts_back_the_value_held_before_the_install():
    """The undo restores the previous value, not a cleared slot (#5874)."""
    slot: StartupSlot[str] = StartupSlot()
    slot.install("first")
    undo = slot.install("second")
    undo()
    assert slot.value == "first"


def test_undo_of_a_first_install_leaves_the_slot_empty():
    slot: StartupSlot[str] = StartupSlot()
    undo = slot.install("only")
    undo()
    assert slot.value is None


def test_nested_undos_unwind_in_reverse_order():
    slot: StartupSlot[str] = StartupSlot()
    undo_outer = slot.install("outer")
    undo_inner = slot.install("inner")
    undo_inner()
    assert slot.value == "outer"
    undo_outer()
    assert slot.value is None


def test_monkeypatch_restores_the_held_value(monkeypatch):
    """Tests swap a slot's value with ``monkeypatch``; undo restores it."""
    slot: StartupSlot[str] = StartupSlot()
    slot.install("original")
    monkeypatch.setattr(slot, "value", "replacement")
    assert slot.value == "replacement"
    monkeypatch.undo()
    assert slot.value == "original"
