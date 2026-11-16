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


"""Discover the installed connector plugins through entry points.

A connector plugin is installed, never imported by name: its package
declares an entry point in the ``vultron.connectors`` group (ARCH-05-003),
and :func:`load_connectors` finds it with
:func:`importlib.metadata.entry_points`.  A site adds or removes a connector
by installing or removing its package, with no change to Vultron code.

The entry point names the plugin's class, which the loader constructs with
no arguments; a plugin reads its own settings when it needs them.  The
loader refuses an entry point that cannot be loaded or constructed, whose
plugin is not a :class:`~vultron.adapters.connectors.base.ConnectorPlugin`
(no non-empty ``name``), or whose plugin implements no core port in
:data:`~vultron.adapters.connectors.base.CONNECTOR_PORTS` (ARCH-05-006).
It also refuses two entry points that share one name, because neither can
then be chosen by it.  Each refusal names its entry point, and one
:class:`ConnectorRefusedError` reports every refusal at once, so an operator
fixes every bad package in one pass.

Example ``pyproject.toml`` entry for a third-party plugin::

    [project.entry-points."vultron.connectors"]
    my_tracker = "my_package.connectors:MyTrackerCaseReader"

The example connectors under ``example/`` declare no entry point, so this
loader never finds them.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points

from pydantic import BaseModel, ConfigDict

from vultron.adapters.connectors.base import (
    ConnectorPlugin,
    ports_implemented_by,
)
from vultron.errors import VultronConfigError
from vultron.primitives import NonEmptyString

logger = logging.getLogger(__name__)

#: The entry-point group a connector plugin's package declares (ARCH-05-003).
ENTRY_POINT_GROUP = "vultron.connectors"


class ConnectorRefusal(BaseModel):
    """One entry point the loader refused, and why.

    Attributes:
        entry_point: The entry point, as ``name = target from package``.
        reason: Why the loader refused it.
    """

    model_config = ConfigDict(frozen=True)

    entry_point: NonEmptyString
    reason: NonEmptyString


class ConnectorRefusedError(VultronConfigError):
    """Raised when the loader refuses one or more connector entry points.

    The message names every refused entry point and its reason
    (ARCH-05-006); :attr:`refusals` holds them for a caller.
    """

    def __init__(self, refusals: Iterable[ConnectorRefusal]) -> None:
        self.refusals: tuple[ConnectorRefusal, ...] = tuple(refusals)
        lines = "\n".join(
            f"  - {r.entry_point!r}: {r.reason}" for r in self.refusals
        )
        super().__init__(
            f"Refused {len(self.refusals)} connector entry point(s) in the"
            f" {ENTRY_POINT_GROUP!r} group:\n{lines}"
        )


def _describe(entry_point: EntryPoint) -> str:
    """The entry point as an operator finds it: name, target and package."""
    dist = entry_point.dist
    package = f" from {dist.name}" if dist is not None else ""
    return f"{entry_point.name} = {entry_point.value}{package}"


def _plugin_or_refusal(
    entry_point: EntryPoint,
) -> ConnectorPlugin | ConnectorRefusal:
    """Load and check one entry point's plugin, or say why it is refused."""
    described = _describe(entry_point)
    try:
        plugin_class = entry_point.load()
        plugin = plugin_class()
    except Exception as exc:
        # Any error a third-party package raises refuses only its entry
        # point; the traceback goes to the log for the operator.
        logger.exception("Connector entry point %s failed to load", described)
        return ConnectorRefusal(
            entry_point=described,
            reason=(
                "cannot be loaded and constructed:"
                f" {type(exc).__name__}: {exc}"
            ),
        )
    name = getattr(plugin, "name", None)
    if not isinstance(plugin, ConnectorPlugin) or not (
        isinstance(name, str) and name.strip()
    ):
        return ConnectorRefusal(
            entry_point=described,
            reason=(
                "is not a connector plugin: it has no non-empty string `name`"
            ),
        )
    if not ports_implemented_by(plugin):
        return ConnectorRefusal(
            entry_point=described,
            reason=(
                "implements no core port for outside systems (ARCH-05-006)"
            ),
        )
    return plugin


def load_connectors(
    found: Iterable[EntryPoint] | None = None,
) -> Mapping[str, ConnectorPlugin]:
    """Return every installed connector plugin, by its entry point's name.

    Args:
        found: The entry points to load; by default, every entry point in
            the :data:`ENTRY_POINT_GROUP` group of the installed packages.

    Raises:
        ConnectorRefusedError: Any entry point is refused; the error names
            each one and its reason, and no plugin is returned.
    """
    if found is None:
        found = entry_points(group=ENTRY_POINT_GROUP)
    candidates = list(found)
    counts = Counter(ep.name for ep in candidates)
    refusals: list[ConnectorRefusal] = []
    plugins: dict[str, ConnectorPlugin] = {}
    for entry_point in candidates:
        if counts[entry_point.name] > 1:
            refusals.append(
                ConnectorRefusal(
                    entry_point=_describe(entry_point),
                    reason=(
                        f"shares the name {entry_point.name!r} with another"
                        " entry point"
                    ),
                )
            )
            continue
        result = _plugin_or_refusal(entry_point)
        if isinstance(result, ConnectorRefusal):
            refusals.append(result)
        else:
            plugins[entry_point.name] = result
    if refusals:
        raise ConnectorRefusedError(refusals)
    for name, plugin in plugins.items():
        logger.info(
            "Loaded connector plugin %r (%s), ports: %s",
            name,
            plugin.name,
            ", ".join(p.__name__ for p in ports_implemented_by(plugin)),
        )
    return plugins


__all__ = [
    "ENTRY_POINT_GROUP",
    "ConnectorRefusal",
    "ConnectorRefusedError",
    "load_connectors",
]
