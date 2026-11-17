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

"""Case shadow tool configuration: which case reader a run reads through.

Provides :class:`ShadowConfig`, the ``shadow:`` section of
:class:`~vultron.config.app.AppConfig`.  The case shadow tool's dashboard
reads it at start (ADR-0190, ADR-0192):

* ``connector`` names the connector entry point whose case reader the run
  reads an outside system's cases through.  When it is unset, the run reads
  Vultron case-ledger files through the Vultron case reader.
* ``ledger_dir`` confines the Vultron case reader to one directory, so an
  analyst's input cannot open the host's other files.  Unset, the directory
  the tool starts in confines it.
* ``node_url`` and ``node_actor_id`` name a running Vultron node and the
  CASE_MANAGER whose case ledger the live Vultron case reader reads.  The
  deployment sets them, as ``VULTRON_SHADOW__NODE_URL`` and
  ``VULTRON_SHADOW__NODE_ACTOR_ID``; the page never asks for them, so an
  analyst's input cannot point the tool at another host (SHD-01-001).

An outside system's endpoint and credential are that connector's own
settings, such as the ``vince:`` section (SHD-02-003).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, field_validator

from vultron.config.env_names import env_var_name
from vultron.primitives import NonEmptyString

#: The environment variable that names the node the live reader reads.
SHADOW_NODE_URL_ENV_VAR = env_var_name(("shadow", "node_url"))
#: The environment variable that names the CASE_MANAGER it reads as.
SHADOW_NODE_ACTOR_ID_ENV_VAR = env_var_name(("shadow", "node_actor_id"))


class ShadowConfig(BaseModel):
    """Which case reader the case shadow tool reads cases through.

    Attributes:
        connector: The name of the connector entry point, in the
            ``vultron.connectors`` group, whose case reader the case shadow
            tool reads cases through.  When it is ``None`` the tool reads
            Vultron case-ledger files.  Default ``None``.
        ledger_dir: The directory the Vultron case reader reads case-ledger
            files from.  A case is then named by its file's path relative to
            this directory, and a path outside it is refused.  When it is
            ``None`` the directory the tool starts in takes its place.
            Default ``None``.
        node_url: The API root of a running Vultron node in prototype run
            mode, such as ``http://case-actor:7999/api/v2``.  When it is set
            and no connector is named, the tool reads each case from that
            node's case ledger through the live Vultron case reader, and
            ``ledger_dir`` is not used.  It starts with ``http://`` or
            ``https://``.  Default ``None``.
        node_actor_id: The actor id of the CASE_MANAGER on that node whose
            case ledger the live reader reads, such as ``case-actor``, or
            its full id.  The two are set together: a run with only one of
            them is refused before any case is read.  Default ``None``.
    """

    connector: NonEmptyString | None = None
    ledger_dir: Path | None = None
    node_url: NonEmptyString | None = None
    node_actor_id: NonEmptyString | None = None

    @field_validator("node_url")
    @classmethod
    def validate_node_url(cls, v: str | None) -> str | None:
        """Require an http:// or https:// scheme when a node URL is set."""
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("node_url must start with http:// or https://")
        return v
