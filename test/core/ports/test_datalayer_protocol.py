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

"""Tests for ActorScopedDataLayer protocol conformance (ARCH-13-005).

Verifies that ``SqliteDataLayer`` satisfies ``ActorScopedDataLayer`` and
that ``clone_for_actor()`` returns an actor-scoped instance.
"""

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.ports.datalayer import ActorScopedDataLayer, DataLayer

# ---------------------------------------------------------------------------
# Typed helper — if mypy/pyright can call these with SqliteDataLayer, the
# structural conformance is enforced at static-analysis time.
# ---------------------------------------------------------------------------


def _accept_datalayer(dl: DataLayer) -> DataLayer:
    return dl


def _accept_actor_scoped(dl: ActorScopedDataLayer) -> ActorScopedDataLayer:
    return dl


def test_sqlite_datalayer_satisfies_datalayer_protocol():
    """SqliteDataLayer must satisfy the base DataLayer Protocol."""
    dl = SqliteDataLayer("sqlite:///:memory:")
    result = _accept_datalayer(dl)
    assert result is dl


def test_clone_for_actor_satisfies_actor_scoped_protocol():
    """clone_for_actor() must return an ActorScopedDataLayer.

    This test also validates AC-2 and AC-3 from issue #655: SqliteDataLayer
    satisfies ActorScopedDataLayer and clone_for_actor() return type is
    updated (verified by mypy/pyright via the _accept_actor_scoped helper).
    """
    dl = SqliteDataLayer("sqlite:///:memory:")
    clone = dl.clone_for_actor("https://example.org/actor")
    result = _accept_actor_scoped(clone)
    assert result is clone


def test_actor_scoped_datalayer_exposes_queue_methods():
    """Actor-scoped DataLayer must expose all inbox/outbox queue methods."""
    dl = SqliteDataLayer("sqlite:///:memory:")
    clone = dl.clone_for_actor("https://example.org/actor")
    for method in (
        "inbox_append",
        "inbox_list",
        "inbox_pop",
        "outbox_append",
        "outbox_list",
        "outbox_pop",
    ):
        assert callable(
            getattr(clone, method, None)
        ), f"clone_for_actor() result missing queue method: {method!r}"


def test_base_datalayer_clone_for_actor_return_annotation():
    """DataLayer.clone_for_actor return annotation must be ActorScopedDataLayer."""
    import inspect

    hints = {}
    for cls in (DataLayer,):
        hints.update(
            {
                name: hint
                for name, hint in (getattr(cls, "__annotations__", {}).items())
            }
        )
    # The return type is set on the Protocol method; check via inspect.
    method = getattr(DataLayer, "clone_for_actor", None)
    assert method is not None
    sig = inspect.signature(method)
    return_annotation = sig.return_annotation
    # The annotation is "ActorScopedDataLayer" (forward ref string) or the class
    assert "ActorScopedDataLayer" in str(return_annotation), (
        f"clone_for_actor return annotation should be ActorScopedDataLayer,"
        f" got: {return_annotation!r}"
    )
