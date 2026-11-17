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

An outside system's endpoint and credential are that connector's own
settings, such as the ``vince:`` section (SHD-02-003).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from vultron.primitives import NonEmptyString


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
    """

    connector: NonEmptyString | None = None
    ledger_dir: Path | None = None
