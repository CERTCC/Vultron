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

"""The replica embargo slots run no lifecycle logic (#4294 AC-3, CM-23-016).

A replica writes the embargo register and consent rows by copying the
CASE_MANAGER's entries through the one apply function (ADR-0124), never by
re-running ``EmbargoLifecycle`` or a consent transition on its own state.
Every slot of ``AnnounceLogEntryReceivedBT`` that writes either is covered:
relay, activation, the owner's rejection, abandonment, expiry, teardown,
withdrawal, the consent-row copy, and the stub Invite answers that carry a
joiner's consent (:data:`_SLOTS`), and
:func:`test_every_replica_embargo_slot_is_checked` keeps that list whole.

The check is per class, over every class in each slot's MRO that this
codebase defines, because ``abandon.py`` and ``withdrawal.py`` also hold the
CASE_MANAGER's own nodes, which decide through ``EmbargoLifecycle`` as they
must.  It also follows every module-level function a slot reaches, however
indirectly, so a slot cannot hand the work to a helper that runs it.

The one tracked deviation is the owner's-rejection slot's skip of a
``Reject`` the CASE_MANAGER answered with ET (#4789): it reads one shared
predicate rather than copying, and
:func:`test_only_the_owner_rejection_slot_decides_a_skip` keeps it the only
one.  The CM-31-010 notice path (``ending_notice_replica.py``) applies no
ledger entry and is outside CM-23-016's scope.
"""

import ast
import functools
import importlib
import inspect
import pkgutil
import sys
import textwrap
import types
from typing import Any, cast

import pytest

import vultron.core.behaviors.embargo.nodes as embargo_nodes
import vultron.core.behaviors.sync.nodes as sync_nodes
from test.architecture import _corpus
from vultron.core.behaviors.embargo.nodes.abandon import (
    ApplyEmbargoAbandonmentFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.activation_effect import (
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    ApplyHonourLateAcceptFromLedgerNode,
    ApplyInviteExpiryFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    ApplyEmbargoWithdrawalFromLedgerNode,
)
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
    ApplyEmbargoConsentFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.stub_reply_effect import (
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
)

#: Names a copying slot must never reach for (CM-23-016, CM-18-005).
#: ``TransitionMode`` catches a slot that passes a lifecycle mode on; a
#: slot that hands off to a lifecycle-running node is caught by
#: :func:`_lifecycle_nodes`, as the owner's-rejection slot did before #4784.
_LIFECYCLE_NAMES = frozenset(
    {
        "EmbargoLifecycle",
        "TransitionMode",
        "apply_pec_transition",
        "write_uninvited_rows",
    }
)

#: Every replica slot that writes the embargo register or a consent row.
_SLOTS = [
    # relay (EP-09-007)
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
    # the owner's activation and rejection (ADR-0122)
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
    # abandonment (EMB-16-001)
    ApplyEmbargoAbandonmentFromLedgerNode,
    # expiry and late Accepts (CM-28-014, EMB-17)
    ApplyInviteExpiryFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
    ApplyHonourLateAcceptFromLedgerNode,
    # teardown (EP-08-004)
    ApplyEmbargoTeardownNode,
    # withdrawal (MSM-07-010)
    ApplyEmbargoWithdrawalFromLedgerNode,
    # the CASE_MANAGER's own consent-row entries (ADR-0124)
    ApplyEmbargoConsentFromLedgerNode,
    # the stub Invite answers, which carry a joiner's consent (CM-11-016)
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
]


def _names_used(obj: object) -> set[str]:
    """Every bare name and attribute name *obj*'s source uses."""
    source = inspect.getsource(cast(Any, obj))
    tree = _corpus.parse_inline(textwrap.dedent(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _own_classes(slot: type) -> list[type]:
    return [c for c in slot.__mro__ if c.__module__.startswith("vultron.")]


def _uses_lifecycle(cls: type) -> bool:
    used = set().union(*(_names_used(c) for c in _own_classes(cls)))
    return bool(used & _LIFECYCLE_NAMES)


def _functions_reached(cls: type) -> dict[str, set[str]]:
    """Each codebase function *cls* reaches by name, and the names it uses.

    Follows every name a class body or function body uses that resolves, in
    its module, to a module-level function this codebase defines, and so on
    from there.  Classes are not followed: a slot's own classes are walked by
    MRO, and a lifecycle-running node class is forbidden by name.
    """
    reached: dict[str, set[str]] = {}
    pending: list[object] = list(_own_classes(cls))
    seen: set[int] = set()
    while pending:
        obj = pending.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        names = _names_used(obj)
        if isinstance(obj, types.FunctionType):
            reached[f"{obj.__module__}.{obj.__qualname__}"] = names
        module_globals = vars(sys.modules[cast(Any, obj).__module__])
        for name in names:
            value = module_globals.get(name)
            if isinstance(
                value, types.FunctionType
            ) and value.__module__.startswith("vultron."):
                pending.append(value)
    return reached


@functools.cache
def _lifecycle_nodes() -> frozenset[str]:
    """Every embargo node class that itself runs lifecycle logic.

    Delegating to one of them is running lifecycle logic too, whatever mode
    it is given.
    """
    names: set[str] = set()
    for info in pkgutil.iter_modules(embargo_nodes.__path__):
        module = importlib.import_module(
            f"{embargo_nodes.__name__}.{info.name}"
        )
        for name, value in vars(module).items():
            if (
                inspect.isclass(value)
                and value.__module__ == module.__name__
                and _uses_lifecycle(value)
            ):
                names.add(name)
    return frozenset(names)


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("EP-09-007")
@pytest.mark.parametrize("slot", _SLOTS, ids=lambda c: c.__name__)
def test_a_copying_replica_slot_runs_no_lifecycle_logic(slot: type) -> None:
    forbidden = _LIFECYCLE_NAMES | _lifecycle_nodes()
    used = set().union(*(_names_used(c) for c in _own_classes(slot)))
    assert not used & forbidden, (
        f"{slot.__name__} reaches {sorted(used & forbidden)}"
    )


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("slot", _SLOTS, ids=lambda c: c.__name__)
def test_no_function_a_slot_reaches_runs_lifecycle_logic(slot: type) -> None:
    """A slot cannot run the lifecycle through a helper it calls."""
    forbidden = _LIFECYCLE_NAMES | _lifecycle_nodes()
    offenders = {
        function: sorted(names & forbidden)
        for function, names in _functions_reached(slot).items()
        if names & forbidden
    }
    assert not offenders, f"{slot.__name__} reaches {offenders}"


def test_the_walk_follows_a_slots_helpers() -> None:
    """The walk is not vacuous: it reaches the one apply function."""
    reached = _functions_reached(ApplyEmbargoConsentFromLedgerNode)

    assert "vultron.core.models.embargo_apply.apply_embargo_change" in reached


def _tree_slot_classes() -> set[type]:
    """Every apply node class ``AnnounceLogEntryReceivedBT`` runs."""
    return {
        type(node)
        for node in create_announce_log_entry_tree().iterate()
        if type(node).__name__.startswith("Apply")
    }


def _writes_embargo_state(cls: type) -> bool:
    """A slot that copies an embargo change, or lives with the embargo nodes."""
    return issubclass(cls, ApplyEmbargoChangeFromLedgerNode) or (
        cls.__module__.startswith(f"{embargo_nodes.__name__}.")
    )


@pytest.mark.spec("CM-23-016")
def test_every_replica_embargo_slot_is_checked() -> None:
    """A new embargo slot in the announce tree joins the ratchet."""
    embargo_slots = {
        c for c in _tree_slot_classes() if _writes_embargo_state(c)
    }

    assert embargo_slots, "the announce tree runs no embargo slot"
    missing = sorted(c.__name__ for c in embargo_slots - set(_SLOTS))
    assert not missing, f"add {missing} to _SLOTS"
    absent = sorted(c.__name__ for c in set(_SLOTS) - _tree_slot_classes())
    assert not absent, f"{absent} no longer run in the announce tree"


def test_the_check_sees_a_lifecycle_node() -> None:
    """Handing off to a lifecycle-running node is caught, with no mode."""
    assert {
        "DecideRejectedEmbargoProposalNode",
        "RejectEmbargoProposalLifecycleNode",
        "_EmbargoLifecycleNode",
    } <= _lifecycle_nodes()
    assert not _lifecycle_nodes() & {c.__name__ for c in _SLOTS}


def test_the_check_sees_a_lifecycle_call() -> None:
    """The detector is not vacuous: it finds a call where one is."""

    class _Replays:
        def update(self) -> None:
            EmbargoLifecycle(persistence=None).propose_embargo()  # type: ignore[name-defined]  # noqa: F821

    assert "EmbargoLifecycle" in _names_used(_Replays)


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    direct: list[type] = cls.__subclasses__()
    for sub in direct:
        found |= {sub} | _subclasses(sub)
    return found


def _slots_overriding(attr: str) -> set[str]:
    """Every copying-frame subclass that defines *attr* itself."""
    for package in (embargo_nodes, sync_nodes):
        for info in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"{package.__name__}.{info.name}")
    return {
        sub.__name__
        for sub in _subclasses(ApplyEmbargoChangeFromLedgerNode)
        if attr in vars(sub) and sub.__module__.startswith("vultron.")
    }


@pytest.mark.spec("CM-23-016")
def test_only_the_owner_rejection_slot_decides_a_skip() -> None:
    """The one tracked deviation from copy-only stays contained (#4789).

    ``_left_to_a_later_entry`` lets a slot decide, on the replica, that an
    entry changes nothing.  Only the owner's-rejection slot may, for the
    ``Reject`` the CASE_MANAGER answered with ET (EMB-04-002); a new
    override is a new deviation and needs its own decision.
    """
    assert _slots_overriding("_left_to_a_later_entry") == {
        ApplyEmbargoProposalRejectionFromLedgerNode.__name__
    }
