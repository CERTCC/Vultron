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
"""Find the capability classes the simulation layer defines, for tests.

A fuzzer node binds to its core capability declaration by subclassing it
(BT-18-021), so the classes a test checks are reached through
``__subclasses__()`` — and only once every module that defines one has been
imported.  These helpers do both, once, for every test that needs them:

- :func:`capability_subclasses` returns every transitive subclass of a
  capability class, after importing the whole ``vultron.demo.fuzzer`` package;
- :func:`fuzzer_capability_classes` keeps those defined under that package.
"""

from __future__ import annotations

import importlib
import pkgutil

import vultron.demo.fuzzer as fuzzer_pkg
from vultron.core.behaviors.call_out.capability import Capability
from vultron.subclasses import all_subclasses

#: The package every simulation node lives under (BT-16-001).
FUZZER_PACKAGE = fuzzer_pkg.__name__


def import_fuzzer_modules() -> None:
    """Import every module of ``vultron.demo.fuzzer``."""
    for info in pkgutil.walk_packages(
        fuzzer_pkg.__path__, prefix=f"{FUZZER_PACKAGE}."
    ):
        importlib.import_module(info.name)


def capability_subclasses(
    base: type[Capability] = Capability,
) -> list[type[Capability]]:
    """Every transitive subclass of *base*, by qualified name.

    Imports the whole fuzzer package first, so a node defined in any of its
    modules is reached.
    """
    import_fuzzer_modules()
    return sorted(
        all_subclasses(base), key=lambda c: f"{c.__module__}.{c.__qualname__}"
    )


def fuzzer_capability_classes(
    base: type[Capability] = Capability,
) -> list[type[Capability]]:
    """The subclasses of *base* defined under ``vultron.demo.fuzzer``."""
    return [
        cls
        for cls in capability_subclasses(base)
        if cls.__module__.startswith(f"{FUZZER_PACKAGE}.")
    ]


__all__ = [
    "FUZZER_PACKAGE",
    "capability_subclasses",
    "fuzzer_capability_classes",
    "import_fuzzer_modules",
]
