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

"""The case reader each case source reads through, from the configuration.

:func:`configured_case_reader` turns a
:class:`~vultron.shadow.readers.selection.CaseSource` and the ``shadow:``
settings (:class:`~vultron.config.shadow.ShadowConfig`) into one
:class:`~vultron.core.ports.case_reader.CaseReader`
(:func:`~vultron.shadow.readers.selection.select_case_reader`):

* The recorded demo cases are Vultron case-ledger files confined to
  ``ledger_dir`` or, when it is unset, to the directory the run starts in.
* The outside system is the connector ``connector`` names, VINCE's when it
  is unset, found among the installed connector plugins
  (:func:`~vultron.adapters.connectors.loader.load_connectors`,
  ARCH-05-003).  :func:`outside_source_ready` says whether it can be read
  at all: VINCE only with its base URL and credential in the environment
  (SHD-02-003).
* A running Vultron node is the one the analyst typed
  (:func:`typed_node`), else the one the settings name.

The loader runs only when the outside system is chosen, so a run over
Vultron ledgers is not stopped by a bad third-party package it does not use.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from vultron.adapters.connectors.base import ConnectorPlugin
from vultron.adapters.connectors.loader import load_connectors
from vultron.config.shadow import (
    SHADOW_NODE_ACTOR_ID_ENV_VAR,
    SHADOW_NODE_URL_ENV_VAR,
    VINCE_CONNECTOR,
    ShadowConfig,
)
from vultron.config.vince import VinceConfig
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import ShadowConnectorError, VultronConfigError
from vultron.shadow.readers.selection import (
    CaseSource,
    VultronNode,
    select_case_reader,
)
from vultron.shadow.readers.vultron_node import path_segment

#: What the page calls the two values a typed node is named by.
_TYPED_URL = "the node API root"
_TYPED_ACTOR = "the Case Manager actor id"
_TYPED_LABELS = {"node_url": _TYPED_URL, "node_actor_id": _TYPED_ACTOR}


def _node(
    config: ShadowConfig, *, half_set: str, actor_name: str
) -> VultronNode | None:
    """The Vultron node *config* names, or ``None`` when it names none.

    Raises:
        VultronConfigError: Only one of the node URL and the actor id is
            set, since either alone names no case ledger (*half_set* says
            so), or the actor id, which *actor_name* names, names no actor.
    """
    if config.node_url is None and config.node_actor_id is None:
        return None
    if config.node_url is None or config.node_actor_id is None:
        raise VultronConfigError(half_set)
    try:
        path_segment(config.node_actor_id)
    except ValueError as exc:
        raise VultronConfigError(
            f"{actor_name} names no actor on the node: {exc}"
        ) from exc
    return VultronNode(config.node_url, config.node_actor_id)


def configured_node(config: ShadowConfig) -> VultronNode | None:
    """The Vultron node the settings name, or ``None`` when they name none.

    Raises:
        VultronConfigError: Only one of ``node_url`` and ``node_actor_id``
            is set, or the actor id names no actor.
    """
    return _node(
        config,
        half_set=(
            f"set both {SHADOW_NODE_URL_ENV_VAR} and"
            f" {SHADOW_NODE_ACTOR_ID_ENV_VAR} to read a Vultron node, or"
            " neither"
        ),
        actor_name=SHADOW_NODE_ACTOR_ID_ENV_VAR,
    )


def _problem(error: ErrorDetails) -> str:
    """One validation error's reason, without the input it refused."""
    message = error["msg"].removeprefix("Value error, ")
    field = ".".join(str(part) for part in error["loc"])
    label = _TYPED_LABELS.get(field, field)
    return f"{label}: {message}" if label else message


def typed_node(url: str, actor_id: str) -> VultronNode:
    """The Vultron node the analyst typed on the page.

    Each value is checked by the rules the ``shadow:`` settings check
    ``node_url`` and ``node_actor_id`` by, so a typed node is refused for
    what a configured one is refused for.  A refusal never quotes the value
    it refused (VSD-01-005).

    Args:
        url: The node's API root as typed; surrounding blanks are dropped.
        actor_id: The CASE_MANAGER's actor id as typed; the same.

    Raises:
        VultronConfigError: A value is blank, the URL is not a plain
            ``http://`` or ``https://`` API root, or the actor id names no
            actor.
    """
    try:
        typed = ShadowConfig(
            node_url=url.strip() or None,
            node_actor_id=actor_id.strip() or None,
        )
    except ValidationError as exc:
        raise VultronConfigError(
            "; ".join(_problem(error) for error in exc.errors())
        ) from exc
    enter_both = f"enter both {_TYPED_URL} and {_TYPED_ACTOR}"
    node = _node(typed, half_set=enter_both, actor_name=_TYPED_ACTOR)
    if node is None:
        raise VultronConfigError(enter_both)
    return node


def outside_connector(config: ShadowConfig) -> str:
    """The connector the outside-system source reads through, by name."""
    return config.connector or VINCE_CONNECTOR


def outside_source_ready(config: ShadowConfig, vince: VinceConfig) -> bool:
    """Whether the outside-system source can be chosen.

    VINCE can be chosen only when its base URL and its credential are set,
    both of which come from the environment the tool runs in: the page never
    asks for a credential (SHD-02-003).  Another connector holds its own
    settings, so it can always be chosen, and refuses its own reads.
    """
    if outside_connector(config) != VINCE_CONNECTOR:
        return True
    return vince.base_url is not None and vince.api_token is not None


def _outside_reader(
    name: str, connectors: Callable[[], Mapping[str, ConnectorPlugin]]
) -> CaseReader:
    installed = connectors()
    plugin = installed.get(name)
    if plugin is None:
        names = ", ".join(sorted(installed)) or "none"
        raise ShadowConnectorError(
            name,
            f"no connector entry point has that name (installed: {names})",
        )
    if not isinstance(plugin, CaseReader):
        raise ShadowConnectorError(name, "its plugin implements no CaseReader")
    return plugin


def configured_case_reader(
    config: ShadowConfig,
    source: CaseSource = CaseSource.RECORDINGS,
    *,
    node: VultronNode | None = None,
    connectors: Callable[[], Mapping[str, ConnectorPlugin]] = load_connectors,
) -> CaseReader:
    """The case reader *source* reads through, as *config* sets it up.

    Args:
        config: The run's ``shadow:`` settings.
        source: The source the analyst chose; the recorded demo cases by
            default.
        node: The Vultron node the analyst typed, for the running-node
            source; when it is ``None``, the node the settings name.
        connectors: Returns the installed connector plugins by entry-point
            name; the connector loader by default.  Called only for the
            outside-system source.

    Raises:
        ShadowConnectorError: The outside system's connector is not
            installed, or does not implement ``CaseReader``.
        VultronConfigError: The running-node source has no node, or its
            settings name half a node, or an actor id that names no actor.
        ConnectorRefusedError: The loader refused an installed entry point.
    """
    match source:
        case CaseSource.OUTSIDE:
            return select_case_reader(
                source,
                outside=_outside_reader(outside_connector(config), connectors),
            )
        case CaseSource.NODE:
            node = node or configured_node(config)
            if node is None:
                raise VultronConfigError(
                    f"name a Vultron node to read: {_TYPED_URL} and"
                    f" {_TYPED_ACTOR}"
                )
            return select_case_reader(source, node=node)
        case CaseSource.RECORDINGS:
            # The file reader confines every read: to ledger_dir, or to the
            # directory the run starts in when it is unset.
            return select_case_reader(source, ledger_root=config.ledger_dir)


__all__ = [
    "configured_case_reader",
    "configured_node",
    "outside_connector",
    "outside_source_ready",
    "typed_node",
]
