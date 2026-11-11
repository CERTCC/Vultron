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
"""Every named capability's core-owned declaration (BT-18-020, BT-18-021).

Each module here declares the capabilities of one domain, one class per
capability, as a subclass of a shape base in
:mod:`vultron.core.behaviors.call_out.capability`.  The declaration carries
the capability's ports (BT-18-012); its simulation node in
``vultron/demo/fuzzer/`` sits at the same module path under that package
and subclasses it, so the contract is stated once, here.

:func:`capability_declarations` enumerates them, so a check or a default
that must cover every capability derives its roster from the declarations
rather than from a hand-kept list
(ADR-0097#core-declared-typed-port-contract).

The modules are imported only by :func:`capability_declarations`, never by
this package's import, so a bundle importing one declaration does not pull
in every domain.
"""

from __future__ import annotations

import importlib
import pkgutil

from vultron.core.behaviors.call_out.capability import Capability


def capability_declarations() -> tuple[type[Capability], ...]:
    """Every capability declared under this package, by qualified name.

    Imports each module of the package and returns the
    :class:`~vultron.core.behaviors.call_out.capability.Capability`
    subclasses defined in it.  A class defined elsewhere (a backend or a
    simulation node that binds to a declaration) is not a declaration and is
    not returned.
    """
    found: dict[str, type[Capability]] = {}
    for info in pkgutil.walk_packages(__path__, prefix=f"{__name__}."):
        module = importlib.import_module(info.name)
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Capability)
                and obj.__module__ == module.__name__
                and obj.declaration() is obj
            ):
                found[f"{obj.__module__}.{obj.__qualname__}"] = obj
    return tuple(found[key] for key in sorted(found))


__all__ = ["capability_declarations"]
