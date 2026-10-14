"""MSM mapping and rendering infrastructure.

Public API for the ``vultron.metadata.msm`` package:

- :data:`PAGE_SLUGS` — canonical tuple of valid page slugs.
- :class:`MappingStatus` — enum of mapping relationship types.
- :class:`RowSpec` — one registry entry's derived page, shorthands and status.
- :data:`ROW_SPECS` — one mapping row per entry, derived from the occasions on
  ``SEMANTIC_REGISTRY`` (ADR-0128); nothing in it is typed by hand.
- :data:`SEMANTICS_TO_ROW` — O(1) lookup from ``MessageSemantics`` → ``RowSpec``.
- :func:`mapping_status`, :func:`sent_by`, :func:`section_heading` — the
  derivations (MSM-08-005, MSM-08-006, MSM-08-008).
- :class:`OccasionTable`, :func:`load_occasion_table` — the committed occasion
  table YAML and its loader.  The generator is
  :mod:`vultron.metadata.msm.occasions`; run it as ``uv run msm-occasions``,
  not ``python -m``, which would load the module twice through this package.
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
    PAGE_SLUGS,
    ROW_SPECS,
    SEMANTICS_TO_ROW,
    MappingStatus,
    OccasionTable,
    RowSpec,
    load_occasion_table,
    mapping_status,
    section_heading,
    sent_by,
)

__all__ = [
    "PAGE_SLUGS",
    "MappingStatus",
    "RowSpec",
    "ROW_SPECS",
    "SEMANTICS_TO_ROW",
    "EXEMPTED_SEMANTICS",
    "mapping_status",
    "sent_by",
    "section_heading",
    "OccasionTable",
    "load_occasion_table",
]
