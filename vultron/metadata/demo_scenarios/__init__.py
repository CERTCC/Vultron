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
"""Artifacts derived from the demo scenario registry (ADR-0098, DEMOCI-11).

Public API:

- :func:`render_page` — render one consumer's scenario table as markdown.
- :data:`PAGE_SLUGS` — canonical tuple of valid page slugs.
- :func:`scenario_matrix_json` — desired contents of
  ``.github/demo-scenarios.json``.
- :func:`stale_artifacts` / :func:`write_artifacts` — the ``--check`` and
  ``--write`` halves of the ``demo-scenarios`` console script.

The registry itself lives in :mod:`vultron.demo.scenario.registry`, because only
a demo module can know that a demo exists. This package reads it; nothing here
is imported by demo or protocol code.
"""

from vultron.metadata.demo_scenarios.render import (
    MATRIX_KEYS,
    PAGE_SLUGS,
    matrix_entries,
    narrative_link,
    render_page,
    scenario_matrix_json,
)
from vultron.metadata.demo_scenarios.sync import (
    ARTIFACTS,
    BEGIN_MARKER,
    END_MARKER,
    HARNESS_README,
    MATRIX_JSON,
    SCENARIO_README,
    WRITE_COMMAND,
    desired_contents,
    missing_derived_paths,
    stale_artifacts,
    write_artifacts,
)

__all__ = [
    "ARTIFACTS",
    "BEGIN_MARKER",
    "END_MARKER",
    "HARNESS_README",
    "MATRIX_JSON",
    "MATRIX_KEYS",
    "PAGE_SLUGS",
    "SCENARIO_README",
    "WRITE_COMMAND",
    "desired_contents",
    "matrix_entries",
    "missing_derived_paths",
    "narrative_link",
    "render_page",
    "scenario_matrix_json",
    "stale_artifacts",
    "write_artifacts",
]
