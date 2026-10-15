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
"""Architecture guard: no trigger executes a BT as an actor its node does not host.

A container executes trees, and enqueues activities, only as actors it hosts
(CM-24-004, ADR-0109).  A trigger that ran a tree under an ``actor_id`` at
another authority than its DataLayer's own was the shape of the retired
delegated emit: the case owner's container emitted in a remote CaseActor's
name, kept the tree in the owner's store, and mailed the CaseActor a ``cc:``
copy so it could learn of its own emission (#2996, #3821, #3822).

**Choice: a runtime assertion, not a static scan** (ARCH-18).  The executing
actor of a trigger is resolved at run time — from the request, or from the
case's roster (``resolve_case_manager_id``, ``_find_case_actor_id``) — so no
scan of ``_prepare()`` source can tell a hosted actor from a foreign one.  The
assertion is ``BTBridge._store_for_actor`` raising
``VultronUnhostedActorError`` (BT-05-005), reached from
``BTBridge.execute_with_setup`` before any node ticks, and
``SvcBTTriggerBase.execute`` turning that internal error into
``VultronBTInternalError`` (a 500, never the client's 422).  It holds for every
trigger by construction, because every BT-backed trigger runs its tree through
that one template method; the second test pins that no subclass overrides it.
The set of overriders is empty and terminal, so this guard keeps no baseline.
"""

import importlib
import pkgutil

import py_trees
import pytest
from py_trees.common import Status

import vultron.core.use_cases.triggers as triggers_pkg
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.use_cases.triggers._base import (
    SvcActivityTriggerBase,
    SvcBTTriggerBase,
)
from vultron.errors import VultronBTInternalError

_HOSTED = "https://vendor.example/api/v2/actors/vendor"
_CO_HOSTED = "https://vendor.example/api/v2/actors/case-actor"
_FOREIGN = "https://case-actor.example/api/v2/actors/case-actor"


class _Recorder(py_trees.behaviour.Behaviour):
    """A leaf that records that it ticked."""

    def __init__(self, ticked: list[str]) -> None:
        super().__init__(name="Recorder")
        self._ticked = ticked

    def update(self) -> Status:
        self._ticked.append(self.name)
        return Status.SUCCESS


class _ExecuteAs(SvcActivityTriggerBase):
    """A trigger whose ``_prepare`` resolves the executing actor it is given."""

    _requires_trigger_activity = False

    def __init__(self, dl, executing_actor_id: str, ticked: list[str]):
        super().__init__(dl=dl, request=None)
        self._executing_actor_id = executing_actor_id
        self._ticked = ticked

    def _prepare(self) -> None:
        self._actor_id = self._executing_actor_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return _Recorder(self._ticked)

    def _handle_result(self) -> None:
        return None


@pytest.fixture
def dl():
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_HOSTED)
    yield store
    store.close()


@pytest.mark.spec("BT-05-005")
@pytest.mark.spec("CM-24-004")
@pytest.mark.spec("ARCH-18-001")
def test_a_trigger_cannot_execute_as_a_foreign_authority(dl):
    """The tree never ticks, nothing is queued, and the trigger raises."""
    ticked: list[str] = []

    with pytest.raises(VultronBTInternalError, match="VultronUnhostedActor"):
        _ExecuteAs(dl, _FOREIGN, ticked).execute()

    assert ticked == []
    assert dl.outbox_list() == []


@pytest.mark.spec("BT-05-005")
@pytest.mark.parametrize("actor_id", [_HOSTED, _CO_HOSTED])
def test_a_trigger_executes_as_a_hosted_actor(dl, actor_id):
    """The guard is about authority, not identity: co-hosted actors run."""
    ticked: list[str] = []

    result = _ExecuteAs(dl, actor_id, ticked).execute()

    assert isinstance(result, ActivityResult)
    assert result.emitting_actor_id == actor_id
    assert ticked == ["Recorder"]


def _all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    pending: list[type] = [cls]
    while pending:
        sub: type
        for sub in pending.pop().__subclasses__():
            if sub not in found:
                found.add(sub)
                pending.append(sub)
    return found


@pytest.mark.spec("ARCH-18-001")
def test_no_bt_trigger_bypasses_the_template_method():
    """Every BT-backed trigger runs its tree through ``SvcBTTriggerBase.execute``.

    That method is where the runtime assertion is reached, so an override would
    be a trigger the guard above does not cover.
    """
    for module in pkgutil.walk_packages(
        triggers_pkg.__path__, prefix=f"{triggers_pkg.__name__}."
    ):
        importlib.import_module(module.name)

    overriders = {
        f"{sub.__module__}.{sub.__qualname__}"
        for sub in _all_subclasses(SvcBTTriggerBase)
        if "execute" in vars(sub) and sub.__module__.startswith("vultron.")
    }
    assert len(_all_subclasses(SvcBTTriggerBase)) > 10  # the scan found them
    assert overriders == set()
