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

Public API, in the two halves ADR-0098 splits the consumers into.

*Generate* — :mod:`.render` and :mod:`.sync`:

- :func:`render_page` — render one consumer's scenario table as markdown.
- :data:`PAGE_SLUGS` — canonical tuple of valid page slugs.
- :func:`scenario_matrix_json` — desired contents of
  ``.github/demo-scenarios.json``.
- :func:`stale_artifacts` / :func:`write_artifacts` — the ``--check`` and
  ``--write`` halves of the ``demo-scenarios`` console script.

*Check* — :mod:`.prose_checks` and its siblings:

- :func:`consistency_problems` — every hand-written-prose disagreement, which is
  what ``--check`` adds to the staleness report.
- :func:`scenario_table_problems` / :func:`undeclared_scenario_tables` — the
  ``notes/`` scenario tables (:mod:`.prose_tables`).
- :func:`restated_counts` / :func:`stray_scenario_includes` — the prose scans
  (:mod:`.prose_counts`).
- :func:`scenario_spec_groups` / :func:`partition_problems` — the spec-side
  selector and the two-register partition (:mod:`.scenario_groups`).
- :func:`harness_event_types` — a scenario's expected event types, the source the
  tick matrix is ratcheted against (:mod:`.event_types`).

The registry itself lives in :mod:`vultron.demo.scenario.registry`, because only
a demo module can know that a demo exists. This package reads it; nothing here
is imported by demo or protocol code.
"""

from vultron.metadata.demo_scenarios.event_types import (
    UNIVERSAL_EVENT_TYPES,
    HarnessEventTypeError,
    additional_event_types,
    harness_event_types,
)
from vultron.metadata.demo_scenarios.prose_checks import (
    consistency_problems,
    missing_event_type_requirements,
    missing_narrative_nav_entries,
    scenario_set_statement_problems,
)
from vultron.metadata.demo_scenarios.prose_counts import (
    SCENARIO_TABLE_CONSUMERS,
    restated_counts,
    stray_scenario_includes,
)
from vultron.metadata.demo_scenarios.prose_tables import (
    SCENARIO_TABLES,
    ScenarioTable,
    scenario_table_problems,
    undeclared_scenario_tables,
)
from vultron.metadata.demo_scenarios.render import (
    MATRIX_KEYS,
    PAGE_SLUGS,
    matrix_entries,
    narrative_link,
    render_page,
    scenario_matrix_json,
)
from vultron.metadata.demo_scenarios.scenario_groups import (
    PLANNED_COLUMNS,
    PLANNED_REGISTER,
    PLANNED_REGISTER_HEADING,
    SPEC_ID_RE,
    PlannedScenario,
    partition_problems,
    per_scenario_event_type_requirements,
    planned_scenarios,
    scenario_spec_groups,
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
    "PLANNED_COLUMNS",
    "PLANNED_REGISTER",
    "PLANNED_REGISTER_HEADING",
    "SCENARIO_README",
    "SCENARIO_TABLES",
    "SCENARIO_TABLE_CONSUMERS",
    "SPEC_ID_RE",
    "UNIVERSAL_EVENT_TYPES",
    "WRITE_COMMAND",
    "HarnessEventTypeError",
    "PlannedScenario",
    "ScenarioTable",
    "additional_event_types",
    "consistency_problems",
    "desired_contents",
    "harness_event_types",
    "matrix_entries",
    "missing_derived_paths",
    "missing_event_type_requirements",
    "missing_narrative_nav_entries",
    "narrative_link",
    "partition_problems",
    "per_scenario_event_type_requirements",
    "planned_scenarios",
    "render_page",
    "restated_counts",
    "scenario_matrix_json",
    "scenario_set_statement_problems",
    "scenario_spec_groups",
    "scenario_table_problems",
    "stale_artifacts",
    "stray_scenario_includes",
    "undeclared_scenario_tables",
    "write_artifacts",
]
