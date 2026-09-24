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
- Dynamic discovery causes all activity and object modules to be imported
  (reachable via sys.modules) even if they add no new type keys.

Per-class registration completeness (VM-01-007) lives in
``test_registry.py::TestWireTypeValues``.  It replaced a per-module check here
whose skip predicate — "the module declares no own ``type_`` annotation" — is
exactly what an unregistered module looks like, so it skipped the modules it
existed to catch (ISSUE-3564).
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
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    find_in_vocabulary,
)

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
    """Each expected type name is findable via the vocabulary."""
    try:
        cls = find_in_vocabulary(type_name)
    except KeyError:
        cls = None
    assert cls is not None, (
        f"Expected type '{type_name}' not findable in vocabulary. "
        f"VOCABULARY keys: {sorted(VOCABULARY.keys())}"
    )
