#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Regression guard for issue #2191.

``demo_step`` swallows exceptions by design (records on ``_demo_failures``,
does *not* re-raise — DEMOCI-01-003/004).  Several demo helpers previously
assigned a result variable *inside* a ``with demo_step(...)`` block and then
dereferenced it *after* the block::

    with demo_step("... accepts case ownership transfer ..."):
        accept_result = post_to_trigger(...)     # raises -> swallowed
    accept_ownership = accept_result["activity"]  # UnboundLocalError!

The fix (PR #2196): move the dereference *inside* the ``with demo_step(...)``
block so that a swallowed trigger failure leaves the variable as ``None``
(initialised before the block) rather than unbound::

    accept_ownership = None
    with demo_step("... accepts case ownership transfer ..."):
        accept_result = post_to_trigger(...)      # raises -> swallowed
        accept_ownership = accept_result["activity"]  # never reached -> fine
    # accept_ownership is None; failure surfaces via assert_demo_success()

This test is a shape-replica of the affected sites
(``fvcv_handoff_demo.py``, ``fccv_handoff_demo.py``) using the REAL
``demo_step`` / ``_demo_failures`` / ``assert_demo_success`` from
``vultron.demo.utils`` and REAL ``post_to_trigger`` (monkeypatched to raise),
so no Docker or live HTTP is required.
"""

from typing import cast

import pytest

import vultron.demo.utils as demo_utils
from vultron.demo.utils import (
    DataLayerClient,
    assert_demo_success,
    demo_step,
    reset_demo_failures,
)
from vultron.errors import DemoFailureError


def _accept_ownership_transfer_shape() -> dict | None:
    """Fixed replica of the ``accept_result`` site in the handoff demos.

    Mirrors the fix applied to ``fvcv_handoff_demo.py`` and
    ``fccv_handoff_demo.py``: the result dereference is moved *inside* the
    ``with demo_step(...)`` block so that a swallowed trigger failure leaves
    ``accept_ownership`` as ``None`` (initialised before the block) rather than
    raising ``UnboundLocalError``.
    """
    accept_ownership: dict | None = None
    with demo_step(
        "Coordinator accepts case ownership transfer (TRIG-11-002)"
    ):
        accept_result = demo_utils.post_to_trigger(
            # The client is never dereferenced: the only caller monkeypatches
            # post_to_trigger to raise before it would be used.
            client=cast(DataLayerClient, None),
            actor_id="https://vultron.example/actors/coordinator",
            behavior="accept-case-ownership-transfer",
            body={"offer_id": "https://vultron.example/offers/1"},
        )
        accept_ownership = accept_result["activity"]
    return accept_ownership


def test_demo_step_swallow_does_not_leave_result_unbound(monkeypatch):
    """demo_step swallowing an exception must not strand an unbound result var.

    When ``post_to_trigger`` raises inside the ``with demo_step(...)`` block,
    the dereference is now inside the block too, so the swallowed exception
    leaves ``accept_ownership`` as ``None`` rather than raising
    ``UnboundLocalError``.  The accumulated failure surfaces cleanly via
    ``assert_demo_success()``.  Regression for #2191.
    """
    reset_demo_failures()

    def _boom(*args, **kwargs):
        raise RuntimeError(
            "simulated accept-case-ownership-transfer trigger HTTP 500"
        )

    monkeypatch.setattr(demo_utils, "post_to_trigger", _boom)

    raised_unbound = False
    try:
        result = _accept_ownership_transfer_shape()
    except UnboundLocalError:
        raised_unbound = True

    assert not raised_unbound, (
        "demo_step swallowed the trigger error but post-block code "
        "dereferenced an unbound result variable (UnboundLocalError), masking "
        "the real failure (#2191)"
    )

    # accept_ownership must be None (the block was swallowed), not an error.
    assert result is None

    # The swallowed failure must be recorded and surface via assert_demo_success().
    assert demo_utils._demo_failures, (
        "demo_step should have recorded the swallowed trigger failure on "
        "_demo_failures"
    )
    with pytest.raises(DemoFailureError):
        assert_demo_success()
