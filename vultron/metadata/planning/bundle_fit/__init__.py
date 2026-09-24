"""Two-stage bundle selection for the ``propose-bundle`` skill.

Requirements: ISSUE-3482; PAD-03-001 (Schedule is the priority authority),
PAD-05 (``size:`` labels), PAD-15 (bundle selection and execution).

Selection used to be one stage: filter an Epic's sub-issues for *eligibility*
(open, unassigned, unblocked, leaf) and take the first five in GitHub order.
Every candidate that cleared eligibility was proposed, so an ``Idea``, a
``Concern`` scheduled ``Someday`` and two ``size:L`` Tasks all looked like
equally good members of one bundle.

This subpackage adds the missing second stage — **fit** — over three signals that
already exist on every candidate:

1. ``issueType`` decides which skill can execute the issue at all, so a bundle
   is homogeneous by workflow (``work-issue`` routes Task/Feature to ``build``,
   Bug to ``bugfix``, Idea/Concern/Epic to ``plan-issue``).
2. The ``Schedule`` field on Project #24 is the authoritative priority ordering
   (PAD-03-001) — sub-issue list order is manual drag-order and means nothing.
   A leaf with no Schedule of its own inherits its Epic's tier.
3. ``size:`` labels weigh a candidate's effort, and the bundle's total weight is
   capped, because a bundle is implemented as **one PR** closing every member.
   The band table those labels come from lives in the sibling
   ``planning.size_bands`` module, which ``model`` imports rather than restates;
   the top band (``size:XL``) has no weight at all and is refused outright.

Thematic coherence is deliberately *not* scored. ``calve-epics`` requires cutting
by design grain and warns that cutting by "superficial theme" produces
plausible-looking but wrong work units, so this code only emits structured
**hints** (shared spec IDs, shared file paths, shared topic labels) and leaves
the grain call to the agent, which must state the bundle's single shared design
idea in one sentence.

Layout (CS-18: one concern per submodule, each well under the 500-line cap):

| Module | Concern |
|---|---|
| ``model`` | tiers, weights, and the ``Candidate``/``Rejection``/``Bundle`` records |
| ``select`` | the two stages and the coherence hints — pure functions, no I/O |
| ``parse`` | the shape of GitHub's GraphQL response |
| ``render`` | the report a human reads |
| ``cli`` | the ``bundle-fit`` console script |

Every public name is re-exported here, so ``from
vultron.metadata.planning.bundle_fit import select_bundle`` and the
``bundle-fit = vultron.metadata.planning.bundle_fit:main`` entry point both keep
working (CS-18-003).

CLI (``PYTHONPATH`` must be cleared in this devcontainer — see AGENTS.md)::

    bash .agents/skills/shared/query-epic-subissues.sh <EPIC> \\
      | PYTHONPATH= uv run bundle-fit

    --workflow W        force the target skill instead of inferring it
    --budget N          total size-weight ceiling (default: 6)
    --max-members N     member-count ceiling (default: 5)
    --project-number N  planning board to read Schedule from (default: 24)
    --json              emit machine-readable JSON instead of the text report
"""

from __future__ import annotations

from vultron.metadata.planning.bundle_fit.cli import main
from vultron.metadata.planning.bundle_fit.model import (
    DEFAULT_BUDGET,
    DEFAULT_MAX_MEMBERS,
    EXCLUDED_TIERS,
    KNOWN_TIERS,
    NON_TOPIC_LABELS,
    PLANNING_PROJECT_NUMBER,
    SCHEDULE_ORDER,
    SIZE_LABELS,
    SIZE_WEIGHTS,
    UNBUNDLABLE_LABELS,
    UNSIZED_LABEL,
    UNSIZED_WEIGHT,
    WORKFLOW_BY_TYPE,
    Bundle,
    Candidate,
    Rejection,
    schedule_rank,
)
from vultron.metadata.planning.bundle_fit.parse import (
    _schedule_of,
    graphql_errors,
    parse_graphql,
)
from vultron.metadata.planning.bundle_fit.render import _render
from vultron.metadata.planning.bundle_fit.select import (
    coherence_hints,
    effective_schedule,
    eligibility,
    select_bundle,
)

__all__ = [
    "Bundle",
    "Candidate",
    "DEFAULT_BUDGET",
    "DEFAULT_MAX_MEMBERS",
    "EXCLUDED_TIERS",
    "KNOWN_TIERS",
    "NON_TOPIC_LABELS",
    "PLANNING_PROJECT_NUMBER",
    "Rejection",
    "SCHEDULE_ORDER",
    "SIZE_LABELS",
    "SIZE_WEIGHTS",
    "UNBUNDLABLE_LABELS",
    "UNSIZED_LABEL",
    "UNSIZED_WEIGHT",
    "WORKFLOW_BY_TYPE",
    "_render",
    "_schedule_of",
    "coherence_hints",
    "effective_schedule",
    "eligibility",
    "graphql_errors",
    "main",
    "parse_graphql",
    "schedule_rank",
    "select_bundle",
]
