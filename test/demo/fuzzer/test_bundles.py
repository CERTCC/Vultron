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
"""Bundle-level tests for all call-out backend domain bundles (BT-23-003).

Verifies:
- BT-23-004: CallOutBackendFactory is a runtime-checkable Protocol; each
  bundle field satisfies isinstance checks at runtime.
- BT-23-003: Bundle classes are frozen @dataclasses with the expected fields.
- BT-23-001: DETERMINISTIC and STOCHASTIC singletons are exported from each
  bundle module and from the top-level bundles/__init__.py.
- Singletons are immutable (FrozenInstanceError on mutation attempt).
- All bundle classes and singletons are re-exported from the top-level
  vultron.demo.fuzzer.bundles package.
"""

import dataclasses

import pytest

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_frozen(instance):
    """Assert that frozen=True prevents field mutation."""
    fields = dataclasses.fields(instance)
    if not fields:
        return
    first = fields[0].name
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        setattr(instance, first, None)


# ---------------------------------------------------------------------------
# Protocol conformance (BT-23-004)
# ---------------------------------------------------------------------------


def test_call_out_backend_factory_protocol_is_runtime_checkable():
    """CallOutBackendFactory is @runtime_checkable — isinstance() usable at runtime."""
    from vultron.core.behaviors.call_out_point import CallOutBackendFactory
    from vultron.demo.fuzzer.base import AlwaysSucceed

    def _factory(name):
        return AlwaysSucceed(name)

    assert isinstance(_factory, CallOutBackendFactory)


def test_bundle_fields_satisfy_protocol():
    """Each field default of DETERMINISTIC satisfies the CallOutBackendFactory Protocol."""
    from vultron.core.behaviors.call_out_point import CallOutBackendFactory
    from vultron.demo.fuzzer.bundles.validation import VALIDATION_DETERMINISTIC

    for f in dataclasses.fields(VALIDATION_DETERMINISTIC):
        val = getattr(VALIDATION_DETERMINISTIC, f.name)
        assert isinstance(
            val, CallOutBackendFactory
        ), f"Field {f.name!r} default does not satisfy CallOutBackendFactory: {val!r}"


# ---------------------------------------------------------------------------
# Roster discovery (AGENTS.md: prefer extracting shared logic over duplicating)
# ---------------------------------------------------------------------------
#
# The roster is discovered, never hand-listed.  Four hard-coded lists used to
# police it, so adding a bundle took four hand edits and forgetting one of them
# failed nothing — the roster silently stopped covering the new bundle.  Two of
# the fourteen modules (``actor_discovery``, ``develop_fix``) were in fact
# already missing when this was reflective-ised (#3429).  The security-defaults
# guard already discovers bundles this way; this mirrors it.


def _bundle_modules():
    """Return every non-private module in ``vultron.demo.fuzzer.bundles``."""
    import importlib
    import pkgutil

    import vultron.demo.fuzzer.bundles as pkg

    mods = []
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        mods.append(
            (
                f"{pkg.__name__}.{info.name}",
                importlib.import_module(f"{pkg.__name__}.{info.name}"),
            )
        )
    assert mods, "discovery found no bundle modules — the walk is broken"
    return mods


def _discovered_bundle_classes():
    """Return ``(module_path, class_name)`` for every bundle dataclass."""
    from vultron.core.behaviors.call_out.bundles.base import CallOutBundle

    found = []
    for path, mod in _bundle_modules():
        for name, obj in vars(mod).items():
            if (
                isinstance(obj, type)
                and issubclass(obj, CallOutBundle)
                and obj is not CallOutBundle
                and dataclasses.is_dataclass(obj)
            ):
                found.append((path, name))
    assert found, "discovery found no bundle classes"
    return sorted(set(found))


def _discovered_singletons():
    """Return ``(module_path, singleton_name)`` for every pre-built bundle."""
    from vultron.core.behaviors.call_out.bundles.base import CallOutBundle

    found = []
    for path, mod in _bundle_modules():
        for name, obj in vars(mod).items():
            if name.isupper() and isinstance(obj, CallOutBundle):
                found.append((path, name))
    assert found, "discovery found no bundle singletons"
    return sorted(set(found))


# ---------------------------------------------------------------------------
# Frozen dataclass invariants (BT-23-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path,class_name", _discovered_bundle_classes()
)
def test_bundle_is_frozen_dataclass(module_path, class_name):
    """Each bundle class is a frozen dataclass (mutation must raise FrozenInstanceError)."""
    import importlib

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    assert dataclasses.is_dataclass(cls), f"{class_name} must be a dataclass"
    params = dataclasses.fields(cls)
    # Frozen = attempting mutation on an instance raises FrozenInstanceError.
    instance = cls()  # type: ignore[call-arg]
    _assert_frozen(instance)
    # All fields must be CallOutBackendFactory-typed
    from vultron.core.behaviors.call_out_point import CallOutBackendFactory

    for f in params:
        val = getattr(instance, f.name)
        assert isinstance(
            val, CallOutBackendFactory
        ), f"{class_name}.{f.name} default does not satisfy CallOutBackendFactory: {val!r}"


# ---------------------------------------------------------------------------
# Singleton immutability (BT-23-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path,singleton_name", _discovered_singletons()
)
def test_singletons_are_immutable(module_path, singleton_name):
    """Every pre-built bundle singleton is immutable, whatever its mode.

    Discovery covers PERMISSIVE and any future mode as well as DETERMINISTIC and
    STOCHASTIC, which a two-name-per-module list could not.
    """
    import importlib

    mod = importlib.import_module(module_path)
    _assert_frozen(getattr(mod, singleton_name))


# ---------------------------------------------------------------------------
# Top-level __init__ re-exports (BT-23-005)
# ---------------------------------------------------------------------------


def test_bundles_init_re_exports_all_classes_and_singletons():
    """vultron.demo.fuzzer.bundles re-exports every discovered name (BT-23-005).

    Derived from the modules on disk rather than a literal list, so a bundle
    added without its ``__init__`` re-export fails here instead of quietly
    falling outside the roster.
    """
    import vultron.demo.fuzzer.bundles as bundles_pkg

    expected_classes = [n for _, n in _discovered_bundle_classes()]
    expected_singletons = [n for _, n in _discovered_singletons()]

    for name in expected_classes + expected_singletons:
        assert hasattr(
            bundles_pkg, name
        ), f"vultron.demo.fuzzer.bundles does not export {name!r}"
