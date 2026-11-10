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

"""Build a fixture :class:`ScenarioSpec`, in the one place that knows its shape.

Six test modules build a spec the registry never registered, to make a check
fire without touching a real scenario module.  Each one repeated the whole
constructor, so every field added to ``ScenarioSpec`` had to be added seven
times — which is how ``story`` arrived (DEMOCI-11-034).  The constructor is
called here instead, and a caller passes only the fields its own assertion
reads (CS-22-001).

``path`` is derived from the story's choices by default, the way
:func:`~vultron.demo.scenario.registry.scenario` derives a registered
scenario's (DEMOCI-11-019); a test that needs the two to disagree passes
``path`` itself.

Not for the three sites that build a spec **wrongly** on purpose — a bad
field value, a non-boolean ``in_pr_set``, an omitted ``story``.  Those call
``ScenarioSpec`` directly, because the malformed call is what they assert.
"""

from __future__ import annotations

from vultron.demo.scenario.registry import AssembledStory, ScenarioSpec
from vultron.demo.scenario.tree import PathStep

#: The first step of every scenario path: the Reporter's one branch point.
#: The shortest valid path a fixture can walk.
FIRST_STEP: PathStep = ("reporter-whom-to-tell", "vendor")


def fixture_spec(
    *,
    name: str,
    label: str,
    story: AssembledStory,
    participants: str = "Reporter + Vendor",
    feature: str = "Fixture scenario; never registered",
    in_pr_set: bool = False,
    path: tuple[PathStep, ...] | None = None,
) -> ScenarioSpec:
    """Return a :class:`ScenarioSpec` carrying *story*, for a test fixture.

    Args:
        name: Sub-command spelling. Required: several callers assert on it,
            and a default would hide which scenario a failure names.
        label: Display label. Required for the same reason — it is rendered
            into every generated table a staleness test compares.
        story: The assembled story. Required, as on the spec itself.
        participants: Prose cast list. Defaulted; override when a test reads
            it.
        feature: Prose one-liner. Defaulted; override when a test reads it.
        in_pr_set: Whether CI runs the scenario on every pull request.
            Defaulted to ``False`` so a fixture never claims a PR-set slot.
        path: The scenario's place on the tree. Derived from *story*'s
            choices when omitted.
    """
    return ScenarioSpec(
        name=name,
        label=label,
        participants=participants,
        feature=feature,
        in_pr_set=in_pr_set,
        path=tuple(story.path) if path is None else path,
        story=story,
    )


__all__ = ["FIRST_STEP", "fixture_spec"]
