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
"""Parity between the mirror's registry and ``.github/workflows/`` (PAD-18-022).

Each function returns one message per breach, so a test reports them all.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from vultron.metadata.planning.ci_mirror._registry import MirrorCheck
from vultron.metadata.planning.ci_mirror._workflows import (
    KEY_SEPARATOR,
    StepKey,
    WorkflowStep,
    pull_request_steps,
)


def _uses_key(step: WorkflowStep) -> str | None:
    return f"uses:{step.uses}" if step.uses else None


def exclusion_key(
    step: WorkflowStep, exclusions: Mapping[str, str]
) -> str | None:
    """The key in *exclusions* that excludes *step*, if any.

    A key names the step, its job (``<file>::<job>``), its workflow file, or
    the action it calls (``uses:<action>``).
    """
    workflow, job, _ = step.key.split(KEY_SEPARATOR, 2)
    candidates = (
        step.key,
        KEY_SEPARATOR.join((workflow, job)),
        workflow,
        _uses_key(step),
    )
    return next((k for k in candidates if k and k in exclusions), None)


def opaque_actions(exclusions: Mapping[str, str]) -> frozenset[str]:
    """Local actions excluded whole, whose steps are never expanded."""
    return frozenset(
        key.removeprefix("uses:")
        for key in exclusions
        if key.startswith("uses:./")
    )


def _covers(key: str, step: WorkflowStep) -> bool:
    workflow, job, _ = step.key.split(KEY_SEPARATOR, 2)
    return key in (
        step.key,
        KEY_SEPARATOR.join((workflow, job)),
        workflow,
        _uses_key(step),
    )


def parity_problems(
    root: Path,
    checks: Iterable[MirrorCheck],
    exclusions: Mapping[str, str],
) -> list[str]:
    """Every way the registry and the workflows under *root* disagree."""
    checks = list(checks)
    steps = pull_request_steps(root, opaque_actions(exclusions))
    mirrored: dict[StepKey, list[str]] = {}
    for check in checks:
        if check.step is not None:
            mirrored.setdefault(check.step, []).append(check.id)
    problems = [
        f"{step.key}: a pull_request step neither mirrored nor excluded; "
        "add a MirrorCheck or an EXCLUSIONS entry with its reason"
        for step in steps.values()
        if step.key not in mirrored and exclusion_key(step, exclusions) is None
    ]
    problems += _registry_problems(checks, steps, mirrored, exclusions)
    return problems


def _registry_problems(
    checks: list[MirrorCheck],
    steps: Mapping[StepKey, WorkflowStep],
    mirrored: Mapping[StepKey, list[str]],
    exclusions: Mapping[str, str],
) -> list[str]:
    problems: list[str] = []
    ids = [c.id for c in checks]
    problems += [
        f"{i}: two checks share this id" for i in set(ids) if ids.count(i) > 1
    ]
    for key, owners in mirrored.items():
        step = steps.get(key)
        if step is None:
            problems.append(
                f"{key}: mirrored by {owners} but no such step runs"
            )
            continue
        if len(owners) > 1:
            problems.append(f"{key}: mirrored by more than one check {owners}")
        if (excluded := exclusion_key(step, exclusions)) is not None:
            problems.append(
                f"{key}: both mirrored and excluded by {excluded!r}"
            )
    for key, reason in exclusions.items():
        if not reason.strip():
            problems.append(f"{key}: an exclusion with no reason")
        if not any(_covers(key, step) for step in steps.values()):
            problems.append(f"{key}: an exclusion that matches no step")
    for check in checks:
        problems += _check_problems(check, steps)
    return problems


def _check_problems(
    check: MirrorCheck, steps: Mapping[StepKey, WorkflowStep]
) -> list[str]:
    step = steps.get(check.step) if check.step else None
    problems: list[str] = []
    if check.command is None:
        if step is None or step.run is None:
            problems.append(
                f"{check.id}: no command, and its step has no run:"
            )
        elif "${{" in step.run:
            problems.append(
                f"{check.id}: its step's run: names a GitHub expression, so "
                "it cannot run verbatim; give the check a command and a note"
            )
    elif not check.note.strip():
        problems.append(
            f"{check.id}: a command differing from CI needs a note"
        )
    if step is not None:
        problems += [
            f"{check.id}: its step's env {name} names a GitHub expression; "
            "set it in the check's env, or say in drops_env why it can go"
            for name, value in step.env.items()
            if "${{" in value
            and name not in check.env
            and not check.drops_env.get(name, "").strip()
        ]
    if check.paths is not None and not check.narrowed.strip():
        problems.append(f"{check.id}: narrowed paths need a reason")
    return problems
