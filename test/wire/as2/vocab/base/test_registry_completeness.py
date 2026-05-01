#!/usr/bin/env python
"""Registration completeness tests for the Vultron ActivityStreams vocabulary.

Verifies that importing vultron.wire.as2.vocab populates the vocabulary
registry with the types it needs and that dynamic-discovery imports all
vocab modules.

Ref: VOCAB-REG-1.2 — dynamic discovery; BUG-26040902 fix.

Design note
-----------
Not every vocab module contributes new type_ names to the registry.
Some modules define only "semantic alias" classes — subclasses that inherit
their parent's type_ value without overriding it (e.g. _RmCreateReportActivity
inherits type_="Create" from as_Create).  These are NOT registered separately
because the vocabulary is keyed by type_ value, not class name.  Testing that
every single module contributes a registry entry would be wrong.

What we DO test here:
- All important domain and AS2 types are reachable in VOCABULARY.
- Object modules that define classes with their own type_ annotation register
  at least one type (catches accidental omissions in discovery).
- Dynamic discovery causes all activity and object modules to be imported
  (reachable via sys.modules) even if they add no new type keys.
"""

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

import importlib
import pkgutil
import sys

import pytest

import vultron.wire.as2.vocab  # noqa: F401 — triggers dynamic discovery
from vultron.wire.as2.vocab.base.registry import VOCABULARY

# ---------------------------------------------------------------------------
# Module-level discovery helpers
# ---------------------------------------------------------------------------


def _collect_modules(*package_names: str) -> list[str]:
    """Return fully-qualified names for all sibling modules in each package."""
    result: list[str] = []
    for pkg_name in package_names:
        pkg = importlib.import_module(pkg_name)
        for mod_info in pkgutil.iter_modules(pkg.__path__):
            result.append(f"{pkg_name}.{mod_info.name}")
    return result


_OBJECT_MODULES = _collect_modules("vultron.wire.as2.vocab.objects")
_ACTIVITY_MODULES = _collect_modules("vultron.wire.as2.vocab.activities")
_BASE_OBJECT_MODULES = _collect_modules(
    "vultron.wire.as2.vocab.base.objects",
    "vultron.wire.as2.vocab.base.objects.activities",
)


# ---------------------------------------------------------------------------
# Dynamic-discovery import check: all modules must be importable after
# importing the top-level vocab package.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", _OBJECT_MODULES)
def test_object_module_imported_by_dynamic_discovery(module_name):
    """Dynamic discovery imports every vocab/objects/ module."""
    assert module_name in sys.modules, (
        f"Module '{module_name}' was NOT imported by dynamic discovery. "
        "Check vocab/objects/__init__.py discovery loop."
    )


@pytest.mark.parametrize("module_name", _ACTIVITY_MODULES)
def test_activity_module_imported_by_dynamic_discovery(module_name):
    """Dynamic discovery imports every vocab/activities/ module."""
    assert module_name in sys.modules, (
        f"Module '{module_name}' was NOT imported by dynamic discovery. "
        "Check vocab/activities/__init__.py discovery loop."
    )


# ---------------------------------------------------------------------------
# Per-module registration check: object modules that define their own
# type_ annotation must contribute ≥1 type to VOCABULARY.
# Modules with only semantic-alias classes (inheriting parent type_) are
# expected to contribute zero entries and are skipped automatically.
# ---------------------------------------------------------------------------


def _module_defines_own_type_annotation(module_name: str) -> bool:
    """Return True if any class in this module defines type_ in its own __annotations__."""
    mod = importlib.import_module(module_name)
    for name in dir(mod):
        obj = getattr(mod, name, None)
        if not isinstance(obj, type):
            continue
        if getattr(obj, "__module__", None) != module_name:
            continue
        if "type_" in obj.__dict__.get("__annotations__", {}):
            return True
    return False


def _module_contributes_registered_type(module_name: str) -> bool:
    """Return True if any class defined in this module is in VOCABULARY."""
    mod = importlib.import_module(module_name)
    for name in dir(mod):
        obj = getattr(mod, name, None)
        if obj is None or not isinstance(obj, type):
            continue
        if getattr(obj, "__module__", None) != module_name:
            continue
        if any(vocab_cls is obj for vocab_cls in VOCABULARY.values()):
            return True
    return False


@pytest.mark.parametrize("module_name", _OBJECT_MODULES + _BASE_OBJECT_MODULES)
def test_object_module_with_own_type_contributes_to_registry(module_name):
    """Object modules that declare their own type_ annotation must register it."""
    if not _module_defines_own_type_annotation(module_name):
        pytest.skip(
            f"Module {module_name} has no own type_ annotation — "
            "semantic alias or abstract module, skip"
        )
    assert _module_contributes_registered_type(module_name), (
        f"Module '{module_name}' has a class with own type_ annotation "
        "but none are in VOCABULARY. Check __init_subclass__ or explicit "
        "registration."
    )


# ---------------------------------------------------------------------------
# Specific expected types: all key domain types must be present
# ---------------------------------------------------------------------------

_EXPECTED_TYPES = [
    # Core AS2 activity types
    "Create",
    "Update",
    "Delete",
    "Accept",
    "Reject",
    "Offer",
    "Invite",
    "Add",
    "Remove",
    "Undo",
    "Announce",
    "Arrive",
    "Travel",
    # AS2 object types
    "Note",
    "Document",
    "Article",
    "Event",
    # AS2 actor types
    "Actor",
    "Person",
    "Organization",
    "Service",
    "Application",
    "Group",
    # Vultron domain objects (types that need faithful round-trips through TinyDB)
    "VulnerabilityReport",
    "VulnerabilityCase",
    "VulnerabilityRecord",
    "CaseParticipant",
    "EmbargoPolicy",
    "CaseStatus",
    "CaseReference",
    # Note: EmbargoEvent intentionally NOT listed here — it inherits
    # type_="Event" from as_Event and is stored/retrieved as as_Event.
    # Its embargo-specific fields (start_time, end_time) are preserved
    # via name field; see embargo_event.py for rationale.
]


@pytest.mark.parametrize("type_name", _EXPECTED_TYPES)
def test_expected_type_is_registered(type_name):
    """Each expected type name is present in the vocabulary."""
    assert type_name in VOCABULARY, (
        f"Expected type '{type_name}' not found in VOCABULARY. "
        f"Available keys: {sorted(VOCABULARY.keys())}"
    )
