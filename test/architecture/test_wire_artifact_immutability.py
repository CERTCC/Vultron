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
"""Architecture ratchet: wire Activity artifact immutability (VM-08-002, VM-08-003).

Both tests are xfail(strict=True) — they assert the desired end state and will
auto-promote to passing once the implementation issues are resolved.

- VM-08-002 → #2652 (add frozen=True to wire branch + ratchet test)
- VM-08-003 → #2653 (redesign TriggerActivityPort to return frozen wire blob)
"""

import typing

import pytest


@pytest.mark.spec("VM-08-002")
def test_wire_activity_base_is_frozen():
    """as_Object.model_config must have frozen=True (VM-08-002)."""
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    assert as_Object.model_config.get("frozen") is True


@pytest.mark.spec("VM-08-003")
def test_trigger_activity_port_returns_wire_blob_not_dict():
    """TriggerActivityPort activity methods must return frozen wire blobs, not dicts (VM-08-003)."""
    from vultron.core.ports.trigger_activity import TriggerActivityPort

    hints = typing.get_type_hints(TriggerActivityPort.submit_report)
    return_type = hints.get("return")
    assert (
        return_type is not None
    ), "submit_report must have a return type annotation"
    type_args = typing.get_args(return_type)
    assert (
        len(type_args) == 2
    ), "return type must be a 2-tuple (activity_id, payload)"
    payload_type = type_args[1]
    # Currently dict[str, Any]: get_origin returns dict → assertion fails (xfail).
    # After #2653, payload_type is a frozen wire object: get_origin returns None → passes.
    assert typing.get_origin(payload_type) is not dict
