"""Read-only demo scenario report tool (DRPT-01 through DRPT-05).

Parses the JSONL case-ledger replica files produced by demo scenario runs
(``{DEVLOGS_DIR}/{demo}/{actor}/{case_slug}-case-ledger.jsonl``, written by
:func:`vultron.demo.helpers.ledger_dump.dump_case_ledgers`) and renders a
selective, human-readable report — "who did what to whom, with what activity,
in what order."

The ``dump-manifest.json`` file that ``dump_case_ledgers`` writes alongside the
replicas (ISSUE-2239) is not part of this tool's input; ``discover_replicas``
globs only ``**/*-case-ledger.jsonl``.

The tool is intentionally standalone (its own ``__main__`` entry point,
invokable as ``python -m vultron.demo.report`` or via the
``vultron-demo-report`` console script) so it stays decoupled from the
demo-run CLI (DC-01) while remaining colocated with the demo code that
produces the ledger files.

Pipeline:

1. :func:`discover_replicas` globs ``**/*-case-ledger.jsonl`` beneath the
   input directory and groups parsed entries by the containing actor
   directory name.
2. :func:`build_timeline` distils each raw entry into a
   :class:`CaseTimelineEvent`, merges all replicas into one canonical
   timeline (de-duplicated by ``entry_hash``, grouped by ``case_id`` then
   ordered by ``log_index`` so distinct cases are never interleaved), and
   computes a per-actor replica-presence indicator.
3. :func:`render_markdown` / :func:`render_html` render the timeline as one
   labelled section per case (DRPT-02-006); both consume
   :class:`CaseTimelineEvent` objects, never raw JSONL dicts.

Spec: ``specs/demo-report.yaml`` (DRPT-01 through DRPT-05).
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

from vultron.demo.report.cli import (
    default_input_dir,
    default_output_path,
    generate_report,
    main,
)
from vultron.demo.report.naming import (
    event_phrase,
    friendly_target_noun,
)
from vultron.demo.report.render import (
    render_html,
    render_markdown,
)
from vultron.demo.report.timeline import (
    CaseTimelineEvent,
    ReportError,
    build_timeline,
    discover_replicas,
    discovered_actors,
    group_events_by_case,
)
from vultron.measure.ledger import collect_actor_names, friendly_actor_name

__all__ = [
    "CaseTimelineEvent",
    "ReportError",
    "build_timeline",
    "collect_actor_names",
    "default_input_dir",
    "default_output_path",
    "discover_replicas",
    "discovered_actors",
    "event_phrase",
    "friendly_actor_name",
    "friendly_target_noun",
    "generate_report",
    "group_events_by_case",
    "main",
    "render_html",
    "render_markdown",
]
