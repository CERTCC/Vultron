"""MSM mapping and rendering infrastructure.

Public API for the ``vultron.metadata.msm`` package:

- :func:`render_page` — render a shorthand↔wire-form mapping table for a
  ``docs/reference/messages/`` page.
- :data:`PAGE_SLUGS` — canonical tuple of valid page slugs.
- :class:`MappingStatus` — enum of mapping relationship types.
- :class:`RowSpec` — one registry entry with its page assignment and metadata.
- :data:`ROW_SPECS` — complete mapping table.
- :data:`SEMANTICS_TO_ROW` — O(1) lookup from ``MessageSemantics`` → ``RowSpec``.
"""

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

from vultron.metadata.msm._mapping import (
    EXEMPTED_SEMANTICS,
    MappingStatus,
    PAGE_ROWS,
    PAGE_SLUGS,
    ROW_SPECS,
    SEMANTICS_TO_ROW,
    RowSpec,
)
from vultron.metadata.msm.render import render_page

__all__ = [
    "render_page",
    "PAGE_SLUGS",
    "PAGE_ROWS",
    "MappingStatus",
    "RowSpec",
    "ROW_SPECS",
    "SEMANTICS_TO_ROW",
    "EXEMPTED_SEMANTICS",
]
