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
with none named, the run reads Vultron case-ledger files
(:func:`~vultron.shadow.readers.selection.select_case_reader`), confined to
``ledger_dir`` or, when it is unset, to the directory the run starts in.

The loader runs only when a connector is named, so a run over Vultron
ledgers is not stopped by a bad third-party package it does not use.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from vultron.adapters.connectors.base import ConnectorPlugin
from vultron.adapters.connectors.loader import load_connectors
from vultron.config.shadow import ShadowConfig
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import ShadowConnectorError
from vultron.shadow.readers.selection import select_case_reader


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
        ConnectorRefusedError: The loader refused an installed entry point.
    """
    if config.connector is None:
        # A case id is typed into a page, so the reader always keeps it to
        # one directory: the configured one, or the one the run starts in.
        root = (
            config.ledger_dir if config.ledger_dir is not None else Path.cwd()
        )
        return select_case_reader(ledger_root=root)
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
