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

"""Case shadow tool configuration: what each case source reads through.

Provides :class:`ShadowConfig`, the ``shadow:`` section of
:class:`~vultron.config.app.AppConfig`.  The case shadow tool's dashboard
reads it at start (ADR-0190, ADR-0192).  The analyst picks the source on the
page: the recorded demo cases, an outside system, or a running Vultron node
(#6642).  These settings configure each source:

* ``ledger_dir`` confines the Vultron case reader, which reads the recorded
  demo cases, to one directory, so an analyst's input cannot open the host's
  other files.  Unset, the directory the tool starts in confines it.
* ``connector`` names the connector entry point whose case reader the
  outside-system source reads through.  When it is unset, that source is
  VINCE, through the ``vince`` connector.
* ``node_url`` and ``node_actor_id`` prefill the running-node source's
  fields: a Vultron node's API root and the CASE_MANAGER whose case ledger
  the live Vultron case reader reads.  The deployment sets them, as
  ``VULTRON_SHADOW__NODE_URL`` and ``VULTRON_SHADOW__NODE_ACTOR_ID``.  They
  are not secret: the analyst may type others on the page, and a typed value
  is checked by the same rules.  The live reader only reads a node's case
  ledger (SHD-04-001), so no value sends anything (SHD-01-001).

An outside system's endpoint and credential are that connector's own
settings, such as the ``vince:`` section.  The page never asks for a
credential (SHD-02-003).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator

from vultron.config.env_names import env_var_name
from vultron.primitives import NonEmptyString

#: The environment variable that names the node the live reader reads.
SHADOW_NODE_URL_ENV_VAR = env_var_name(("shadow", "node_url"))
#: The environment variable that names the CASE_MANAGER it reads as.
SHADOW_NODE_ACTOR_ID_ENV_VAR = env_var_name(("shadow", "node_actor_id"))
#: The connector the outside-system source reads through when
#: ``connector`` is unset: VINCE's, by its entry-point name.
VINCE_CONNECTOR = "vince"


class ShadowConfig(BaseModel):
    """Which case reader the case shadow tool reads cases through.

    Attributes:
        connector: The name of the connector entry point, in the
            ``vultron.connectors`` group, whose case reader the case shadow
            tool's outside-system source reads cases through.  When it is
            ``None`` that source is VINCE, through the ``vince`` connector
            (:data:`VINCE_CONNECTOR`).  Default ``None``.
        ledger_dir: The directory the Vultron case reader reads case-ledger
            files from.  A case is then named by its file's path relative to
            this directory, and a path outside it is refused.  When it is
            ``None`` the directory the tool starts in takes its place.
            Default ``None``.
        node_url: The API root of a running Vultron node in prototype run
            mode, such as ``http://case-actor:7999/api/v2``.  It prefills
            the page's running-node source, which follows each case on that
            node's case ledger through the live Vultron case reader.  It
            starts with ``http://`` or ``https://``.  Default ``None``.
        node_actor_id: The actor id of the CASE_MANAGER on that node whose
            case ledger the live reader reads, such as ``case-actor``, or
            its full id.  It prefills the running-node source with
            ``node_url``; the source is read only with both.  Default
            ``None``.
    """

    # A validation error names the field but never quotes its input, so a
    # refused node URL is not echoed into a log or the page (VSD-01-005).
    model_config = ConfigDict(hide_input_in_errors=True)

    connector: NonEmptyString | None = None
    ledger_dir: Path | None = None
    node_url: NonEmptyString | None = None
    node_actor_id: NonEmptyString | None = None

    @field_validator("node_url")
    @classmethod
    def validate_node_url(cls, v: str | None) -> str | None:
        """Require a plain http:// or https:// API root when one is set.

        A user name or password, a query or a fragment is refused: the URL
        is quoted in the reader's errors, on the page and in the logs, so it
        must carry nothing but where the node is.
        """
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError("node_url must start with http:// or https://")
        parts = urlsplit(v)
        if "@" in parts.netloc or "?" in v or "#" in v:
            raise ValueError(
                "node_url must name only the node's API root: no user name,"
                " password, query or fragment"
            )
        return v
