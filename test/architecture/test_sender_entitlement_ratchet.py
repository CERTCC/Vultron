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

"""Architecture ratchet: sender entitlement declarations (ADR-0115).

Enforces:
1. Every received use case in SEMANTIC_REGISTRY declares ``sender_entitlement``.
2. No ``SenderEntitlementConditionNode`` subclass is defined outside
   ``vultron.core.behaviors.sender_entitlement``.
3. Old node names no longer live in their former modules.
"""

import importlib
import inspect
import sys
from types import ModuleType

import pytest

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementConditionNode,
    SenderEntitlementKind,
    SenderExemption,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _received_entries():
    """Yield (semantics, use_case_class) for every non-UNKNOWN registry entry."""
    unknown_names = {
        MessageSemantics.UNKNOWN.name,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT.name,
    }
    for entry in SEMANTIC_REGISTRY:
        if entry.semantics.name not in unknown_names:
            yield entry.semantics, entry.use_case_class


# ---------------------------------------------------------------------------
# AC-1: every received use case declares sender_entitlement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "semantics,use_case_class",
    list(_received_entries()),
    ids=[
        e.semantics.name
        for e in SEMANTIC_REGISTRY
        if e.semantics.name
        not in {
            MessageSemantics.UNKNOWN.name,
            MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT.name,
        }
    ],
)
def test_use_case_has_sender_entitlement_declared(semantics, use_case_class):
    """Every received use case must declare ``sender_entitlement``."""
    assert hasattr(use_case_class, "sender_entitlement"), (
        f"{use_case_class.__name__} (semantics={semantics.name}) "
        f"is missing the ``sender_entitlement`` ClassVar. "
        f"Add one to {inspect.getfile(use_case_class)} — "
        f"use SenderEntitlementKind.<KIND> or exempt('#NNNN', 'reason')."
    )
    declaration = use_case_class.sender_entitlement
    assert isinstance(declaration, (SenderEntitlementKind, SenderExemption)), (
        f"{use_case_class.__name__}.sender_entitlement must be "
        f"SenderEntitlementKind or SenderExemption, got {type(declaration)!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: no SenderEntitlementConditionNode subclass defined outside the module
# ---------------------------------------------------------------------------


def _all_loaded_modules() -> list[ModuleType]:
    """Return all currently loaded vultron modules."""
    return [
        mod
        for name, mod in sys.modules.items()
        if name.startswith("vultron") and isinstance(mod, ModuleType)
    ]


def _import_vultron_behaviors() -> None:
    """Pre-import the BT behaviors package to ensure subclasses are loaded."""
    prefixes = [
        "vultron.core.behaviors",
        "vultron.core.use_cases",
    ]
    for prefix in prefixes:
        try:
            importlib.import_module(prefix)
        except ImportError:
            pass


def test_no_sender_condition_node_outside_sender_entitlement_module():
    """No SenderEntitlementConditionNode subclass may live outside sender_entitlement.py."""
    _import_vultron_behaviors()

    MODULE = "vultron.core.behaviors.sender_entitlement"
    violations = []
    for mod in _all_loaded_modules():
        if mod.__name__ == MODULE:
            continue  # the canonical home — all good
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, SenderEntitlementConditionNode)
                and obj is not SenderEntitlementConditionNode
                and obj.__module__ != MODULE
            ):
                violations.append(f"{obj.__module__}.{obj.__name__}")
    assert not violations, (
        "SenderEntitlementConditionNode subclasses found outside "
        f"'{MODULE}':\n" + "\n".join(f"  - {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# AC-3: old node names no longer live at their former module paths
# ---------------------------------------------------------------------------


OLD_NAMES = [
    (
        "vultron.core.behaviors.status.nodes.conditions",
        "VerifySenderIsParticipantNode",
    ),
    (
        "vultron.core.behaviors.case.nodes.vfd_role_guards",
        "CheckIsCaseOwnerNode",
    ),
    (
        "vultron.core.behaviors.report.nodes.ack_conditions",
        "CheckSenderIsExecutingActorNode",
    ),
    (
        "vultron.core.behaviors.sync.nodes.conditions",
        "VerifySenderIsCaseActorNode",
    ),
    (
        "vultron.core.behaviors.sync.nodes.conditions",
        "VerifySenderIsOwnIdNode",
    ),
]


@pytest.mark.parametrize(
    "module_path,class_name",
    OLD_NAMES,
    ids=[f"{m}.{c}" for m, c in OLD_NAMES],
)
def test_old_node_name_removed_from_former_module(module_path, class_name):
    """Old sender-check node names must no longer exist in their former module."""
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        pytest.skip(f"Module {module_path!r} not importable")
    assert not hasattr(mod, class_name), (
        f"{module_path}.{class_name} still exists — "
        f"it has been consolidated into "
        f"vultron.core.behaviors.sender_entitlement (ADR-0115, AC-2). "
        f"Remove the definition and update any importers."
    )
