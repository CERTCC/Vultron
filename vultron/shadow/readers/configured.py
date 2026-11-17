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

"""The case reader a case shadow run reads through, from its configuration.

:func:`configured_case_reader` turns the ``shadow:`` settings
(:class:`~vultron.config.shadow.ShadowConfig`) into one
:class:`~vultron.core.ports.case_reader.CaseReader`.  A named connector is
found among the installed connector plugins
(:func:`~vultron.adapters.connectors.loader.load_connectors`, ARCH-05-003);
with none named, the run reads a configured Vultron node's case ledger
through the live Vultron case reader, or, with no node configured, Vultron
case-ledger files confined to ``ledger_dir`` or, when it is unset, to the
directory the run starts in
(:func:`~vultron.shadow.readers.selection.select_case_reader`).

The loader runs only when a connector is named, so a run over Vultron
ledgers is not stopped by a bad third-party package it does not use.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from vultron.adapters.connectors.base import ConnectorPlugin
from vultron.adapters.connectors.loader import load_connectors
from vultron.config.shadow import (
    SHADOW_NODE_ACTOR_ID_ENV_VAR,
    SHADOW_NODE_URL_ENV_VAR,
    ShadowConfig,
)
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import ShadowConnectorError, VultronConfigError
from vultron.shadow.readers.selection import (
    VultronNode,
    select_case_reader,
)
from vultron.shadow.readers.vultron_node import path_segment


def _configured_node(config: ShadowConfig) -> VultronNode | None:
    """The Vultron node *config* names, or ``None`` when it names none.

    Raises:
        VultronConfigError: Only one of the node URL and the actor id is
            set, since either alone names no case ledger, or the actor id
            names no actor.
    """
    if config.node_url is None and config.node_actor_id is None:
        return None
    if config.node_url is None or config.node_actor_id is None:
        raise VultronConfigError(
            f"set both {SHADOW_NODE_URL_ENV_VAR} and"
            f" {SHADOW_NODE_ACTOR_ID_ENV_VAR} to read a Vultron node, or"
            " neither"
        )
    try:
        path_segment(config.node_actor_id)
    except ValueError as exc:
        raise VultronConfigError(
            f"{SHADOW_NODE_ACTOR_ID_ENV_VAR} names no actor on the node: {exc}"
        ) from exc
    return VultronNode(config.node_url, config.node_actor_id)


def configured_case_reader(
    config: ShadowConfig,
    connectors: Callable[[], Mapping[str, ConnectorPlugin]] = load_connectors,
) -> CaseReader:
    """The case reader *config* names.

    Args:
        config: The run's ``shadow:`` settings.
        connectors: Returns the installed connector plugins by entry-point
            name; the connector loader by default.

    Raises:
        ShadowConnectorError: The named connector is not installed, or does
            not implement ``CaseReader``.
        VultronConfigError: With no connector named, only one of the node
            URL and the node actor id is set, or the actor id names no
            actor.
        ConnectorRefusedError: The loader refused an installed entry point.
    """
    if config.connector is None:
        # The file reader confines every read: to ledger_dir, or to the
        # directory the run starts in when it is unset.
        return select_case_reader(
            node=_configured_node(config), ledger_root=config.ledger_dir
        )
    installed = connectors()
    plugin = installed.get(config.connector)
    if plugin is None:
        names = ", ".join(sorted(installed)) or "none"
        raise ShadowConnectorError(
            config.connector,
            f"no connector entry point has that name (installed: {names})",
        )
    if not isinstance(plugin, CaseReader):
        raise ShadowConnectorError(
            config.connector, "its plugin implements no CaseReader"
        )
    return select_case_reader(plugin)


__all__ = ["configured_case_reader"]
