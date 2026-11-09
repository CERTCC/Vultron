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

"""The committed plot manifest: every scenario's flattened story (DEMOCI-11-034).

A scenario is written as composition, so its story is a flat sequence of
``choose(...)`` items and fragments (``notes/demo-scenario-tree.md``
§ "Composition").  This module projects that sequence onto one committed JSON
artifact, which :mod:`.sync` drift-checks beside the CI matrix and the two
scenario tables (DEMOCI-11-005, DEMOCI-11-035).

Why the manifest earns its place: the shared-prefix check compares two
*committed* recordings with each other (DEMOCI-11-017, DEMOCI-11-018), so
moving one ``choose`` past its fragment inside a shared prefix moves both
recordings alike and passes.  The manifest is read by importing the stories —
nothing runs, no clock ticks and no recording is regenerated — so the reorder
shows up as a diff in this file at no cost at pull-request time.

What it cannot see is an edit *inside* a fragment's body; the base-versus-head
comparison of DEMOCI-11-055 is what sees that.

Two shapes of row, both all-string so a diff reads as prose:

- a choice — ``kind``, ``branch_point``, ``choice`` and ``by``, the deciding
  cast member's name in its scenario (DEMOCI-11-013, DEMOCI-11-047);
- a fragment — ``kind`` and ``name``, its ``__module__`` and ``__qualname__``
  joined.

A fragment whose qualified name is not stable is **refused** rather than
written: a lambda or a closure is named ``<lambda>`` or ``...<locals>...``,
which says nothing about which step it is and changes when its enclosing
function is renamed.  Parameterized helpers are called from inside a named
module-level fragment, so every real story item already has a stable name.
That rule lives with the fragments, in
:func:`vultron.demo.helpers.story.fragment_name`: it is a rule about how a
story is written, and the tooling layer raises no ``VultronError`` of its own
(MS-17-006).

**This module is the one in :mod:`vultron.metadata` that imports the demo
helper library, and the cost is accepted deliberately.** Reading a story's
items needs :class:`~vultron.demo.helpers.story.Choose`, and importing any
submodule of ``vultron/demo/helpers/`` runs that package's ``__init__``,
which reaches ``demo.utils`` and the AS2 factories: ``import
vultron.metadata.demo_scenarios`` goes from about 1.0 s to about 4.5 s
(measured warm, twice each).  A function-local import is not the remedy —
there is no cycle to break, so CS-05-005 puts it at module level — and the
weight falls only on ``export-demo-states`` and ``export-demo-semantics``,
two commands a developer runs by hand.  Every command that calls
``discover_scenarios()`` imports the scenario modules, and so the same
helper library, already.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypedDict

from vultron.demo.helpers.story import Choose, fragment_name
from vultron.demo.scenario.registry import AssembledStory, ScenarioSpec
from vultron.metadata.generated_files import serialize_json

#: Where the artifact lives: beside the scenario modules whose stories it
#: mirrors, so a reader who reordered a fragment finds it in the same
#: directory tree rather than under ``ui/`` or ``.github/``, neither of which
#: consumes it.
PLOT_MANIFEST = "vultron/demo/scenario/plots.json"

#: ``kind`` of a row standing for one ``choose(...)`` item.
CHOICE_KIND = "choice"

#: ``kind`` of a row standing for one story fragment.
FRAGMENT_KIND = "fragment"

#: One row of an entry: a choice's four names, or a fragment's two. Typed as
#: one all-string mapping rather than two row types, because the artifact is
#: compared as text and a reader of the diff reads the ``kind`` key.
PlotRow = dict[str, str]


class PlotManifest(TypedDict):
    """The manifest's whole payload, as the committed file holds it."""

    _README: str
    scenarios: dict[str, list[PlotRow]]


def plot_rows(scenario: str, story: AssembledStory) -> list[PlotRow]:
    """Return *story*'s items in order, as the manifest's rows.

    Args:
        scenario: The scenario the story belongs to, for error attribution.
        story: Its assembled story.

    Raises:
        DemoStoryError: As
            :func:`~vultron.demo.helpers.story.fragment_name`, which owns the
            naming rule because it is a rule about how a story is written,
            not about this artifact. The tooling layer raises no
            ``VultronError`` of its own (MS-17-006).
    """
    rows: list[PlotRow] = []
    for item in story.items:
        if isinstance(item, Choose):
            rows.append(
                {
                    "kind": CHOICE_KIND,
                    "branch_point": item.branch_point,
                    "choice": item.choice,
                    "by": item.by,
                }
            )
        else:
            rows.append(
                {
                    "kind": FRAGMENT_KIND,
                    "name": fragment_name(item, scenario=scenario),
                }
            )
    return rows


def plot_manifest(
    specs: Iterable[ScenarioSpec], write_command: str
) -> PlotManifest:
    """Return the manifest payload for *specs*, in registry order.

    Every spec is listed. ``ScenarioSpec`` requires a story and
    :func:`~vultron.demo.scenario.registry.scenario` requires ``story=``, so
    there is no spec to skip — and skipping one would be the wrong answer
    anyway: a scenario missing from the artifact leaves the drift check green
    over a story nobody recorded.

    Args:
        specs: The scenarios to list.
        write_command: The command that rewrites the artifact, quoted in the
            file so a reader who found it by grep learns not to hand-edit it.

    Raises:
        DemoStoryError: As :func:`plot_rows`.
    """
    return PlotManifest(
        _README=(
            f"Generated by `{write_command}` "
            "(vultron/metadata/demo_scenarios/plots.py) from the choices and "
            "fragments of each registered scenario's assembled story, in "
            "order. Do not edit by hand; re-run the command and commit the "
            "result instead."
        ),
        scenarios={
            spec.name: plot_rows(spec.name, spec.story) for spec in specs
        },
    )


def plot_manifest_json(
    specs: Sequence[ScenarioSpec], write_command: str
) -> str:
    """Return the manifest's desired full file contents.

    Raises:
        DemoStoryError: As :func:`plot_rows`.
    """
    return serialize_json(plot_manifest(specs, write_command))


__all__ = [
    "CHOICE_KIND",
    "FRAGMENT_KIND",
    "PLOT_MANIFEST",
    "PlotManifest",
    "PlotRow",
    "plot_manifest",
    "plot_manifest_json",
    "plot_rows",
]
