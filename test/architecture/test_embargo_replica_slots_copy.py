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

"""The copying replica slots run no lifecycle logic (#4715 AC-4, CM-23-016).

A replica writes the embargo register and consent rows by copying the
CASE_MANAGER's entries through the one apply function (ADR-0124), never by
re-running ``EmbargoLifecycle`` or a consent transition on its own state.
The check is per class, over every class in each slot's MRO that this
codebase defines, because ``abandon.py`` and ``withdrawal.py`` also hold the
CASE_MANAGER's own nodes, which decide through ``EmbargoLifecycle`` as they
must (#4717 added the withdrawal slot; #4784 the owner's activation and
rejection slots).
"""

import ast
import functools
import importlib
import inspect
import pkgutil
import textwrap

import pytest

import vultron.core.behaviors.embargo.nodes as embargo_nodes
from test.architecture import _corpus
from vultron.core.behaviors.embargo.nodes.abandon import (
    ApplyEmbargoAbandonmentFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.activation_effect import (
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    ApplyEmbargoWithdrawalFromLedgerNode,
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

_SLOTS = [
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
    ApplyEmbargoAbandonmentFromLedgerNode,
    ApplyEmbargoWithdrawalFromLedgerNode,
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
]


def _names_used(cls: type) -> set[str]:
    tree = _corpus.parse_inline(textwrap.dedent(inspect.getsource(cls)))
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
