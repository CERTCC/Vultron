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
"""Render the capability catalog on ``docs/topics/capability_model/index.md``.

The catalog lists every named capability, by domain, from the core
declarations that
:func:`~vultron.core.behaviors.call_out.capabilities.capability_declarations`
enumerates (BT-18-020, BT-18-021).  Each domain section of the page is a
hand-written heading and prose, followed by a markdown-exec Python block that
calls :func:`render_capability_table` with the declaration modules of that
domain.  So a capability added to a module reaches the page without a docs
edit, and the hand-kept catalog that drifted is gone (MS-16-002, MS-16-003).

Every column comes from the declaration:

- **Capability** is the class name without its ``Capability`` suffix, which is
  the name a tree passes to the backend factory;
- **Shape** is the shape base it subclasses (ADR-0097);
- **Asks** is the first paragraph of its docstring;
- **Reads** and **Writes on yes** are its ``INPUT_PORTS`` and
  ``OUTPUT_PORTS``, with each port's ``data_type`` (BT-18-012).

A declaration that cannot be rendered raises :class:`CapabilityCatalogError`,
which fails the strict docs build rather than publishing a blank row.  The
domain modules are named on the page, not here, so the test
``test/metadata/docs/test_capability_catalog.py`` checks that the page's
blocks between them name every declaration module exactly once.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Mapping

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out import capabilities as _capabilities_pkg
from vultron.core.behaviors.call_out.capabilities import (
    capability_declarations,
)
from vultron.core.behaviors.call_out.capability import (
    Capability,
    CapabilityShape,
)

#: The package every declaration module sits under.
DECLARATION_PACKAGE = _capabilities_pkg.__name__

#: The suffix a declaration's class name carries beyond the capability name.
CLASS_SUFFIX = "Capability"

#: The table header the renderer emits.
TABLE_HEADER = (
    "| Capability | Shape | Asks | Reads | Writes on *yes* |",
    "|---|---|---|---|---|",
)

_RST_LITERAL = re.compile(r"``([^`]+)``")


class CapabilityCatalogError(ValueError):
    """A capability declaration cannot be rendered in the catalog."""


def declaration_module(declaration: type[Capability]) -> str:
    """Return *declaration*'s module, relative to the declaration package.

    ``...capabilities.report_management.validate`` reads
    ``report_management.validate``.
    """
    prefix = f"{DECLARATION_PACKAGE}."
    module = declaration.__module__
    if not module.startswith(prefix):
        raise CapabilityCatalogError(
            f"{declaration.__qualname__} is declared in {module}, outside "
            f"{DECLARATION_PACKAGE} (BT-18-020)."
        )
    return module.removeprefix(prefix)


def declarations_by_module() -> dict[str, tuple[type[Capability], ...]]:
    """Every declaration, grouped by its module relative to the package."""
    grouped: dict[str, list[type[Capability]]] = {}
    for declaration in capability_declarations():
        grouped.setdefault(declaration_module(declaration), []).append(
            declaration
        )
    return {module: tuple(found) for module, found in grouped.items()}


def capability_name(declaration: type[Capability]) -> str:
    """The capability's name: its class name without ``Capability``."""
    name = declaration.__name__
    if not name.endswith(CLASS_SUFFIX) or name == CLASS_SUFFIX:
        raise CapabilityCatalogError(
            f"{declaration.__qualname__} does not end in {CLASS_SUFFIX!r}, so "
            "the catalog cannot name the capability it declares."
        )
    return name.removesuffix(CLASS_SUFFIX)


def _cell(text: str) -> str:
    """*text* as one table cell: RST literals as code, pipes escaped."""
    return _RST_LITERAL.sub(r"`\1`", text).replace("|", r"\|")


def summary(declaration: type[Capability]) -> str:
    """The first paragraph of *declaration*'s own docstring, on one line."""
    doc = vars(declaration).get("__doc__")
    if not isinstance(doc, str) or not doc.strip():
        raise CapabilityCatalogError(
            f"{declaration.__qualname__} has no docstring, so the catalog "
            "has nothing to say it asks (BT-18-001)."
        )
    first = inspect.cleandoc(doc).split("\n\n", 1)[0]
    return _cell(" ".join(first.split()))


def _ports(ports: Mapping[str, PortInformation]) -> list[str]:
    return [
        f"`{key}` (`{info.data_type.__name__}`)" for key, info in ports.items()
    ]


def _writes(declaration: type[Capability]) -> str:
    if declaration.OUTPUT_PORTS:
        return "<br>".join(_ports(declaration.OUTPUT_PORTS))
    if declaration.shape is CapabilityShape.ACTUATOR:
        return "side effect only"
    return "verdict only"


def _reads(declaration: type[Capability]) -> str:
    return "<br>".join(_ports(declaration.INPUT_PORTS)) or "—"


def render_row(declaration: type[Capability]) -> str:
    """One catalog table row for *declaration*."""
    cells = (
        f"`{capability_name(declaration)}`",
        declaration.shape.value,
        summary(declaration),
        _reads(declaration),
        _writes(declaration),
    )
    return "| " + " | ".join(cells) + " |"


def _module_path(module: str) -> str:
    return f"{DECLARATION_PACKAGE}.{module}".replace(".", "/") + ".py"


def render_capability_table(
    *modules: str,
    grouped: Mapping[str, tuple[type[Capability], ...]] | None = None,
) -> str:
    """The catalog table for the declarations in *modules*.

    Args:
        modules: Declaration modules relative to the declaration package,
            such as ``"report_management.validate"``, in the order their
            rows appear.
        grouped: The declarations by module; defaults to
            :func:`declarations_by_module`.  Tests pass their own.

    Raises:
        CapabilityCatalogError: No module is named, a module is named twice,
            or a named module declares no capability, which is how a renamed
            or removed module shows on the page.
    """
    if not modules:
        raise CapabilityCatalogError("name at least one declaration module.")
    if len(set(modules)) != len(modules):
        raise CapabilityCatalogError(
            f"a declaration module is named twice in {list(modules)}."
        )
    grouped = declarations_by_module() if grouped is None else grouped
    missing = [m for m in modules if m not in grouped]
    if missing:
        raise CapabilityCatalogError(
            f"{missing} declare no capability under {DECLARATION_PACKAGE}; "
            "rename or remove the page's reference to them."
        )
    paths = ", ".join(f"`{_module_path(m)}`" for m in modules)
    lines = [f"Declared in {paths}.", "", *TABLE_HEADER]
    for module in modules:
        lines += [render_row(d) for d in grouped[module]]
    return "\n".join(lines) + "\n"


__all__ = [
    "CLASS_SUFFIX",
    "DECLARATION_PACKAGE",
    "TABLE_HEADER",
    "CapabilityCatalogError",
    "capability_name",
    "declaration_module",
    "declarations_by_module",
    "render_capability_table",
    "render_row",
    "summary",
]
