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

"""Export the demo scenario tree to a JSON index for ``ui/`` (DEMOCI-11-016).

The demo UI must not keep its own copy of the scenario tree: which decisions a
presenter can make, what each choice is called, and which scenario each path
ends in.  The branch-point table
(:data:`~vultron.demo.scenario.branch_points.BRANCH_POINTS`) and each
scenario's ``@scenario(path=...)`` are the single source, and
:func:`~vultron.demo.scenario.registry.scenario_tree` merges the paths.  This
module projects them into ``ui/src/data/scenario_tree.json``:

- ``branch_points`` — the branch-point table, keyed by id, in table order:
  the deciding role, the presenter prompt, and the choices, each with its
  label and trigger.
- ``tree`` — the tree as nested nodes from the root.  An interior node names
  its ``branch_point`` and maps each choice taken there, in the table's
  choice order, to the child node; an ending names its ``scenario``.
- ``scenarios`` — one entry per registered scenario, keyed by name, in
  registry order: its label, its path, and its recording files keyed by actor
  and then by case.

The recording files are the committed ones under ``ui/src/recordings/``
(:mod:`vultron.demo.recordings`), one per recorded actor.  Each file is listed
under every case its entries carry a ``caseId`` for, in order of first
appearance, so a scenario that splits or merges cases needs no new key.  Paths
are relative to ``ui/src/``, the directory the UI imports them from.  The case
ids are read from the recordings, so a recording refresh that changes a case
id also needs this export rerun; the drift check says so.

The output is deterministic, so ``--check`` (the ``demo-tree-sync``
pre-commit hook, DEMOCI-11-005) and the drift test
``test/metadata/demo_scenarios/test_export_tree.py`` fail when the committed
file differs from a fresh export.

Usage::

    uv run export-demo-tree           # write the index
    uv run export-demo-tree --check   # exit 1 if the committed index is stale
"""

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from vultron.demo.recordings.layout import RECORDING_SUFFIX, RECORDINGS_DIR
from vultron.demo.scenario.branch_points import BRANCH_POINTS, BranchPoint
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.demo.scenario.tree import TreeNode, build_scenario_tree
from vultron.errors import DemoRecordingError, DemoScenarioRegistryError
from vultron.metadata.demo_scenarios.export_states import REPO_ROOT
from vultron.metadata.generated_files import read_committed, write_generated

#: Where the artifact lives, beside ``protocol_states.json``.
OUTPUT_PATH = REPO_ROOT / "ui" / "src" / "data" / "scenario_tree.json"

#: The directory recording paths in the index are relative to.
UI_SRC_DIR = REPO_ROOT / "ui" / "src"

#: The command that regenerates the artifact, quoted in every hint.
REGEN_COMMAND = "uv run export-demo-tree"

#: The command that regenerates the recordings this index lists.
RECORDINGS_COMMAND = "uv run export-demo-recordings"


def branch_point_row(branch_point: BranchPoint) -> dict[str, Any]:
    """Project one branch point onto the artifact's row shape."""
    return {
        "role": branch_point.role.value,
        "prompt": branch_point.prompt,
        "choices": [
            {"id": choice.id, "label": choice.label, "trigger": choice.trigger}
            for choice in branch_point.choices
        ],
    }


def tree_node(
    node: TreeNode, branch_points: Mapping[str, BranchPoint] = BRANCH_POINTS
) -> dict[str, Any]:
    """Project *node* and its descendants onto nested JSON nodes.

    A node's choices follow the branch-point table's order, the order the
    presenter sees them in, so adding a scenario never reorders its siblings.
    """
    if node.scenario is not None:
        return {"scenario": node.scenario}
    if node.branch_point is None:
        raise DemoScenarioRegistryError(
            "the scenario tree has a node that is neither a decision nor an "
            "ending; register at least one scenario."
        )
    order = [choice.id for choice in branch_points[node.branch_point].choices]
    return {
        "branch_point": node.branch_point,
        "choices": {
            choice_id: tree_node(node.children[choice_id], branch_points)
            for choice_id in order
            if choice_id in node.children
        },
    }


def _case_ids(path: Path) -> list[str]:
    """Return the ``caseId`` of *path*'s entries, in order of first appearance.

    Raises:
        DemoRecordingError: When a line is not a ledger entry with a
            non-empty ``caseId``, or the file holds no entry at all.
    """
    case_ids: dict[str, None] = {}
    text = path.read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            case_id = json.loads(line)["caseId"]
        except (ValueError, KeyError, TypeError) as exc:
            raise DemoRecordingError(
                f"{path}, line {number}, is not a ledger entry with a "
                f"caseId: {exc}"
            ) from exc
        if not isinstance(case_id, str) or not case_id:
            raise DemoRecordingError(
                f"{path}, line {number}, has caseId {case_id!r}; expected a "
                "non-empty string."
            )
        case_ids.setdefault(case_id)
    if not case_ids:
        raise DemoRecordingError(
            f"{path} holds no ledger entry; regenerate it with "
            f"`{RECORDINGS_COMMAND} --scenario {path.parent.name}`."
        )
    return list(case_ids)


def recording_files(
    scenario: str,
    recordings_dir: Path = RECORDINGS_DIR,
    relative_to: Path = UI_SRC_DIR,
) -> dict[str, dict[str, str]]:
    """Return *scenario*'s recording files keyed by actor and then by case.

    Args:
        scenario: The scenario name, which names its recordings directory.
        recordings_dir: The directory holding one directory per scenario.
        relative_to: The directory each returned path is relative to.

    Raises:
        DemoRecordingError: When the scenario has no recording, or a recording
            names no case.
    """
    scenario_dir = recordings_dir / scenario
    files = (
        sorted(scenario_dir.glob(f"*{RECORDING_SUFFIX}"))
        if scenario_dir.is_dir()
        else []
    )
    if not files:
        raise DemoRecordingError(
            f"scenario {scenario!r} has no recording under {scenario_dir}; "
            f"record it with `{RECORDINGS_COMMAND} --scenario {scenario}`."
        )
    return {
        path.name.removesuffix(RECORDING_SUFFIX): {
            case_id: path.relative_to(relative_to).as_posix()
            for case_id in _case_ids(path)
        }
        for path in files
    }


def scenario_row(
    spec: ScenarioSpec,
    recordings_dir: Path = RECORDINGS_DIR,
    relative_to: Path = UI_SRC_DIR,
) -> dict[str, Any]:
    """Project one registered scenario onto the artifact's row shape."""
    return {
        "label": spec.label,
        "path": [
            {"branch_point": branch_point_id, "choice": choice_id}
            for branch_point_id, choice_id in spec.path
        ],
        "recordings": recording_files(spec.name, recordings_dir, relative_to),
    }


def build_payload(
    specs: Sequence[ScenarioSpec] | None = None,
    branch_points: Mapping[str, BranchPoint] = BRANCH_POINTS,
    recordings_dir: Path = RECORDINGS_DIR,
    relative_to: Path = UI_SRC_DIR,
) -> dict[str, Any]:
    """Build the full, deterministic export payload.

    Args:
        specs: The scenarios to export. Defaults to the discovered registry.
        branch_points: The branch-point table the paths resolve against.
        recordings_dir: The directory holding the committed recordings.
        relative_to: The directory recording paths are relative to.

    Raises:
        DemoScenarioRegistryError: When the paths do not make one tree.
        DemoRecordingError: When a scenario's recording is missing or names
            no case.
    """
    resolved = discover_scenarios() if specs is None else tuple(specs)
    return {
        "_README": (
            f"Generated by `{REGEN_COMMAND}` "
            "(vultron/metadata/demo_scenarios/export_tree.py) from the "
            "branch-point table, the @scenario path declarations and the "
            "committed recordings. Recording paths are relative to ui/src/. "
            "Do not edit by hand; re-run the exporter and commit the result "
            "instead."
        ),
        "branch_points": {
            branch_point_id: branch_point_row(branch_point)
            for branch_point_id, branch_point in branch_points.items()
        },
        "tree": tree_node(build_scenario_tree(resolved), branch_points),
        "scenarios": {
            spec.name: scenario_row(spec, recordings_dir, relative_to)
            for spec in resolved
        },
    }


def serialize(payload: dict[str, Any]) -> str:
    """Render *payload* as the canonical on-disk string."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def stale_hint(path: Path = OUTPUT_PATH) -> str:
    """Return the message a stale or missing index is reported with."""
    shown = (
        path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    )
    return (
        f"{shown} is stale: the branch-point table, a scenario path or a "
        f"recording changed but the index was not regenerated. Run "
        f"`{REGEN_COMMAND}` and commit {shown}."
    )


def is_stale(path: Path = OUTPUT_PATH, text: str | None = None) -> bool:
    """Return whether *path* differs from *text* (a fresh export by default)."""
    desired = serialize(build_payload()) if text is None else text
    return read_committed(path) != desired


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run export-demo-tree [--check]``."""
    parser = argparse.ArgumentParser(
        prog="export-demo-tree",
        description="Write ui/src/data/scenario_tree.json from the scenario "
        "registry, or check that the committed copy is current.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Write nothing; exit 1 if the committed index is stale.",
    )
    args = parser.parse_args(argv)
    text = serialize(build_payload())
    if args.check:
        if is_stale(OUTPUT_PATH, text):
            raise SystemExit(stale_hint(OUTPUT_PATH))
        return
    write_generated(OUTPUT_PATH, text)
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
