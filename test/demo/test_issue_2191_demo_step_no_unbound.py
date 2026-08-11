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

"""Ratchet signal for issue #2191.

``demo_step`` in ``vultron/demo/utils.py`` swallows exceptions by design (it
records the failure on ``_demo_failures`` and does *not* re-raise).  Several
demo helpers assign a result variable *inside* the ``with demo_step(...)``
block and then dereference / ``return`` it *after* the block::

    with demo_step("... accepts case ownership transfer ..."):
        accept_result = post_to_trigger(...)     # raises -> swallowed
    accept_ownership = accept_result["activity"]  # UnboundLocalError!

When the wrapped call raises, ``accept_result`` is never bound, so the line
after the block raises ``UnboundLocalError``.  That masks the real, accumulated
failure that should have surfaced cleanly via ``assert_demo_success()`` at the
end of the scenario.

APPROACH — shape-replica (see module docstring note below).
The prompt named ``receiver_validates_report`` as an affected site, but reading
``vultron/demo/helpers/workflow.py`` shows it already pre-initialises
``result: dict = {}`` *before* the ``with demo_step(...)`` block (line ~189), so
it is NOT affected — monkeypatching its ``post_to_trigger`` to raise returns
``{}`` cleanly.  The genuinely-affected sites are the ``accept_result``
assignments in the handoff scenarios:

  * ``vultron/demo/scenario/fvcv_handoff_demo.py`` ~399-410 (``accept_result``)
  * ``vultron/demo/scenario/fccv_handoff_demo.py`` ~392-401 (``accept_result``)

Neither pre-initialises ``accept_result``.  Both live inside large,
Docker/HTTP-orchestrated scenario functions that cannot be driven in isolation
without a live multi-container topology.  This test therefore faithfully
replicates the *exact* buggy code shape from those two sites using the REAL
``demo_step`` / ``_demo_failures`` / ``assert_demo_success`` from
``vultron.demo.utils`` and the REAL ``post_to_trigger`` (monkeypatched to
raise), so no Docker or live HTTP is required.
"""

import pytest

import vultron.demo.utils as demo_utils
from vultron.demo.utils import (
    assert_demo_success,
    demo_step,
    reset_demo_failures,
)
from vultron.errors import DemoFailureError


def _accept_ownership_transfer_shape() -> dict:
    """Faithful replica of the ``accept_result`` site in the handoff demos.

    Mirrors ``fvcv_handoff_demo.py`` (~399-410) / ``fccv_handoff_demo.py``
    (~392-401): assign ``accept_result`` inside the ``with demo_step(...)``
    block, then dereference it after the block.  ``post_to_trigger`` is looked
    up on the ``demo_utils`` module so the test can monkeypatch it to raise —
    reproducing the real "trigger endpoint returned an error" failure path
    without any container or HTTP call.
    """
    with demo_step(
        "Coordinator accepts case ownership transfer (TRIG-11-002)"
    ):
        accept_result = demo_utils.post_to_trigger(
            client=None,
            actor_id="https://vultron.example/actors/coordinator",
            behavior="accept-case-ownership-transfer",
            body={"offer_id": "https://vultron.example/offers/1"},
        )
    # In the real helpers this is: as_TransitiveActivity.model_validate(
    #     accept_result["activity"])
    accept_ownership = accept_result["activity"]
    return accept_ownership


@pytest.mark.xfail(
    strict=True,
    reason="#2191 — result var unbound when demo_step swallows exception; "
    "xfail removed once hoisted/initialised",
)
def test_demo_step_swallow_does_not_leave_result_unbound(monkeypatch):
    """demo_step swallowing an exception must not strand an unbound result var.

    With the bug present, ``_accept_ownership_transfer_shape`` raises
    ``UnboundLocalError`` (the ``return``/dereference references a variable the
    swallowed ``with`` block never bound), so the first assertion fails and the
    test resolves to ``xfailed`` — proving the bug.

    Once the source hoists/initialises the result variable ahead of the
    ``with`` block (as ``receiver_validates_report`` already does), no
    ``UnboundLocalError`` is raised and the swallowed failure surfaces cleanly
    via ``assert_demo_success()`` — the test then passes, ``strict=True`` turns
    that into an ``xpass``-failure, and the marker should be removed.
    """
    reset_demo_failures()

    def _boom(*args, **kwargs):
        raise RuntimeError(
            "simulated accept-case-ownership-transfer trigger HTTP 500"
        )

    monkeypatch.setattr(demo_utils, "post_to_trigger", _boom)

    raised_unbound = False
    try:
        _accept_ownership_transfer_shape()
    except UnboundLocalError:
        # The bug: demo_step swallowed the RuntimeError, leaving the result
        # variable unbound, so the post-block dereference blew up with a
        # misleading UnboundLocalError instead of a recorded demo failure.
        raised_unbound = True

    assert not raised_unbound, (
        "demo_step swallowed the trigger error but the post-block code "
        "dereferenced an unbound result variable (UnboundLocalError), masking "
        "the real failure (#2191)"
    )

    # The swallowed failure must instead be recorded and surface via
    # assert_demo_success() at the end of the scenario.
    assert demo_utils._demo_failures, (
        "demo_step should have recorded the swallowed trigger failure on "
        "_demo_failures"
    )
    with pytest.raises(DemoFailureError):
        assert_demo_success()
