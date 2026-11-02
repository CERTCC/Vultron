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
"""Read the steps a pull request runs out of ``.github/workflows/``.

A step is named by a :data:`StepKey`, ``<workflow file>::<job id>::<label>``,
where the label is the step's ``name:``, else its ``uses:`` without the
``@<ref>`` pin. A step that calls a local composite action
(``uses: ./.github/actions/<x>``) is replaced by that action's steps, each
labelled ``<outer label> > <inner label>``, so a step added inside a shared
action is a new key too. The expansion stops at any ``uses:`` the caller
passes as *opaque* — the setup and notification actions the mirror never runs.
A job that calls a reusable workflow (``jobs.<id>.uses:``) has no steps, so it
counts as one step labelled with what it calls. Two steps of one job with the
same label get ``#2``, ``#3``, … appended, so neither hides the other.

Both ``pull_request`` and ``pull_request_target`` count as pull-request
triggers; when a workflow has both, ``pull_request``'s filters decide.

Path filters follow GitHub's rules: ``*`` matches within one path segment,
``**`` across segments, ``?`` one character, and a ``!`` pattern removes what
the patterns before it matched; the last matching pattern decides.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

WORKFLOWS_DIR = Path(".github/workflows")

#: A parsed YAML mapping. ``Any`` is the YAML boundary: a workflow file's
#: values are whatever the author wrote, and each reader narrows what it uses.
YamlMapping = dict[Any, Any]

PULL_REQUEST_EVENTS = ("pull_request", "pull_request_target")

#: ``<workflow file>::<job id>::<step label>``.
StepKey = str

KEY_SEPARATOR = "::"
NEST_SEPARATOR = " > "


@dataclass(frozen=True)
class WorkflowStep:
    """One step a ``pull_request`` run of a workflow can execute."""

    key: StepKey
    workflow: str
    job: str
    run: str | None
    uses: str | None
    env: Mapping[str, str]
    working_directory: str | None


@dataclass(frozen=True)
class PullRequestTrigger:
    """The ``on: pull_request`` filters of one workflow."""

    branches: tuple[str, ...] | None
    paths: tuple[str, ...] | None
    paths_ignore: tuple[str, ...] | None

    def runs_for(self, base: str, changed: Collection[str]) -> bool:
        """Whether GitHub would run the workflow for this base and diff."""
        if self.branches is not None and not matches_filter(
            base, self.branches
        ):
            return False
        if self.paths is not None:
            return any(matches_filter(p, self.paths) for p in changed)
        if self.paths_ignore is not None:
            return any(
                not matches_filter(p, self.paths_ignore) for p in changed
            )
        return True


def load_mapping(path: Path) -> YamlMapping:
    """The YAML mapping in *path*, or ``{}`` when it holds anything else."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def on_block(data: Mapping[Any, Any]) -> Any:
    """A workflow's ``on:`` value; PyYAML reads a bare ``on:`` key as True."""
    return data.get("on", data.get(True))


def _strings(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def pull_request_trigger(data: Mapping[Any, Any]) -> PullRequestTrigger | None:
    """The workflow's ``pull_request`` trigger, or ``None`` when it has none."""
    on = on_block(data)
    if isinstance(on, str):
        on = [on]
    if isinstance(on, list):
        return (
            PullRequestTrigger(None, None, None)
            if any(event in on for event in PULL_REQUEST_EVENTS)
            else None
        )
    if not isinstance(on, dict):
        return None
    name = next((e for e in PULL_REQUEST_EVENTS if e in on), None)
    if name is None:
        return None
    event = on[name] or {}
    return PullRequestTrigger(
        branches=_strings(event.get("branches")),
        paths=_strings(event.get("paths")),
        paths_ignore=_strings(event.get("paths-ignore")),
    )


def workflow_files(root: Path) -> list[Path]:
    """Every workflow file under *root*, sorted by name."""
    folder = root / WORKFLOWS_DIR
    return sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")])


def pull_request_workflows(root: Path) -> dict[str, PullRequestTrigger]:
    """Each workflow file name that ``pull_request`` triggers, with its filters."""
    found: dict[str, PullRequestTrigger] = {}
    for path in workflow_files(root):
        trigger = pull_request_trigger(load_mapping(path))
        if trigger is not None:
            found[path.name] = trigger
    return found


def _bare_uses(uses: str) -> str:
    return uses.split("@", 1)[0]


def _label(step: Mapping[str, Any]) -> str:
    if step.get("name"):
        return str(step["name"])
    return _bare_uses(str(step.get("uses", ""))) or "<unnamed step>"


def composite_steps(root: Path, uses: str) -> list[YamlMapping]:
    """The steps of the local composite action *uses* names (``./…``)."""
    folder = root / uses.removeprefix("./")
    for name in ("action.yml", "action.yaml"):
        if (folder / name).is_file():
            runs = load_mapping(folder / name).get("runs", {})
            return [s for s in runs.get("steps", []) if isinstance(s, dict)]
    raise FileNotFoundError(f"local action {uses} has no action.yml")


def expand_steps(
    root: Path,
    steps: Iterable[Mapping[str, Any]],
    opaque: Collection[str] = (),
) -> list[tuple[str, Mapping[str, Any]]]:
    """*steps* in run order, each local action replaced by its own steps.

    Each step comes with its label (``<outer> > <inner>`` inside an action).
    Expansion recurses, and stops at an action named in *opaque*.
    """
    return list(_expand(root, steps, "", opaque))


def _expand(
    root: Path,
    steps: Iterable[Mapping[str, Any]],
    prefix: str,
    opaque: Collection[str],
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for step in steps:
        label = prefix + _label(step)
        uses = _bare_uses(str(step.get("uses", "")))
        if uses.startswith("./") and uses not in opaque:
            yield from _expand(
                root,
                composite_steps(root, uses),
                label + NEST_SEPARATOR,
                opaque,
            )
        else:
            yield label, step


def _env(*blocks: Any) -> dict[str, str]:
    merged: dict[str, str] = {}
    for block in blocks:
        if isinstance(block, dict):
            merged.update({str(k): str(v) for k, v in block.items()})
    return merged


def _run_directory(job: Mapping[str, Any]) -> str | None:
    defaults = job.get("defaults")
    run = defaults.get("run") if isinstance(defaults, dict) else None
    value = run.get("working-directory") if isinstance(run, dict) else None
    return str(value) if value else None


def workflow_steps(
    root: Path, workflow: str, opaque: Collection[str] = ()
) -> list[WorkflowStep]:
    """Every step of *workflow*, local composite actions expanded."""
    data = load_mapping(root / WORKFLOWS_DIR / workflow)
    found: list[WorkflowStep] = []
    for job_id, job in (data.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        job_env = _env(data.get("env"), job.get("env"))
        job_dir = _run_directory(job)
        steps = [s for s in job.get("steps", []) if isinstance(s, dict)]
        labelled: list[tuple[str, Mapping[str, Any]]]
        if job.get("uses"):
            # A reusable-workflow call has no steps: the job is one step,
            # named by its call, and never expanded as a composite action.
            call = _bare_uses(str(job["uses"]))
            labelled = [(call, {"uses": job["uses"]})]
        else:
            labelled = list(_expand(root, steps, "", opaque))
        seen: dict[str, int] = {}
        for name, step in labelled:
            seen[name] = seen.get(name, 0) + 1
            label = name if seen[name] == 1 else f"{name} #{seen[name]}"
            run = step.get("run")
            found.append(
                WorkflowStep(
                    key=KEY_SEPARATOR.join((workflow, str(job_id), label)),
                    workflow=workflow,
                    job=str(job_id),
                    run=str(run) if run is not None else None,
                    uses=_bare_uses(str(step["uses"]))
                    if step.get("uses")
                    else None,
                    env=_env(job_env, step.get("env")),
                    working_directory=step.get("working-directory") or job_dir,
                )
            )
    return found


def pull_request_steps(
    root: Path, opaque: Collection[str] = ()
) -> dict[StepKey, WorkflowStep]:
    """Every step of every ``pull_request``-triggered workflow, by key."""
    return {
        step.key: step
        for workflow in pull_request_workflows(root)
        for step in workflow_steps(root, workflow, opaque)
    }


@lru_cache(maxsize=512)
def _pattern_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def matches_filter(value: str, patterns: Iterable[str]) -> bool:
    """Whether *value* passes a GitHub filter list (last match decides)."""
    included = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        body = pattern[1:] if negated else pattern
        if _pattern_regex(body).match(value):
            included = not negated
    return included
