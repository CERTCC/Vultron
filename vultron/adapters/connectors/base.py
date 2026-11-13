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

"""The connector plugin base, and which core ports a plugin implements.

A connector plugin integrates one outside system.  Its directions are the
core ports it implements for outside systems (ADR-0191, ARCH-05-004):
:data:`CONNECTOR_PORTS` lists them, and today there is one,
:class:`~vultron.core.ports.case_reader.CaseReader`.  Besides those ports a
plugin carries only its :attr:`ConnectorPlugin.name`.

A plugin implements only the ports it serves, and carries no method, not
even a raising stub, of a port it does not (ARCH-05-005).  The loader
(``loader.py``) asks :func:`ports_implemented_by` which ports a discovered
plugin implements and refuses one that implements none (ARCH-05-006).
"""

from __future__ import annotations

from typing import Final, Protocol, runtime_checkable

from vultron.core.ports.case_reader import CaseReader

#: Every port the core declares for outside systems, in the order
#: :func:`ports_implemented_by` reports them.  A new port joins this tuple
#: when the core declares it (ARCH-05-004).
CONNECTOR_PORTS: Final[tuple[type, ...]] = (CaseReader,)


@runtime_checkable
class ConnectorPlugin(Protocol):
    """What every connector plugin has besides its ports: a name.

    Plugins are discovered through Python entry points under the
    ``vultron.connectors`` group (ARCH-05-003, ``loader.py``).
    """

    #: Human-readable name used in logs and configuration.
    name: str


def ports_implemented_by(plugin: object) -> tuple[type, ...]:
    """Return each port of :data:`CONNECTOR_PORTS` that *plugin* implements.

    A port counts as implemented when *plugin* has every member the port
    declares.  An empty tuple means the plugin implements no port, which the
    loader refuses (ARCH-05-006).
    """
    return tuple(port for port in CONNECTOR_PORTS if isinstance(plugin, port))


__all__ = ["CONNECTOR_PORTS", "ConnectorPlugin", "ports_implemented_by"]
