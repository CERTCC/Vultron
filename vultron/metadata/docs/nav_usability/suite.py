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
"""The personas and tasks of the nav usability test, fixed before a run."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
    load_yaml,
    validate,
)
from vultron.primitives import NonEmptyString

SUITE_PATH = Path("notes/nav-usability/suite.yaml")


class Persona(BaseModel):
    """A briefed newcomer, with the things they explicitly do not know."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyString
    name: NonEmptyString
    brief: NonEmptyString
    does_not_know: list[NonEmptyString] = Field(min_length=1)
    start_page: NonEmptyString
    """The start page that opens this reader's thread: the destination of
    every ``thread`` task, on any nav that carries it."""


class Task(BaseModel):
    """A findability task, with every page that correctly answers it."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyString
    persona: NonEmptyString
    kind: Literal["lookup", "thread"]
    prompt: NonEmptyString
    destinations: list[NonEmptyString] = Field(default_factory=list)
    source: NonEmptyString


class Suite(BaseModel):
    """The personas and tasks; every task names a known persona."""

    model_config = ConfigDict(extra="forbid")

    personas: list[Persona] = Field(min_length=1)
    tasks: list[Task] = Field(min_length=1)

    def persona(self, persona_id: str) -> Persona:
        for persona in self.personas:
            if persona.id == persona_id:
                return persona
        raise KeyError(f"no persona {persona_id!r} in the suite")

    def tasks_for(self, persona_id: str) -> list[Task]:
        return [t for t in self.tasks if t.persona == persona_id]

    def destinations(self, task: Task) -> list[str]:
        """The pages that answer *task*: its own, or its persona's start."""
        if task.kind == "thread":
            return [self.persona(task.persona).start_page]
        return list(task.destinations)


def _suite_faults(suite: Suite) -> list[str]:
    """Every way *suite* breaks the test's rules, not just the first."""
    faults: list[str] = []
    persona_ids = [p.id for p in suite.personas]
    task_ids = [t.id for t in suite.tasks]
    for ids, what in ((persona_ids, "persona"), (task_ids, "task")):
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            faults.append(f"repeats {what} id(s) {', '.join(repeated)}")
    for task in suite.tasks:
        if task.persona not in persona_ids:
            faults.append(
                f"task {task.id} names unknown persona {task.persona!r}"
            )
        if task.kind == "lookup" and not task.destinations:
            faults.append(f"lookup task {task.id} names no destination")
        if task.kind == "thread" and task.destinations:
            faults.append(
                f"thread task {task.id} declares destinations; a thread "
                "task's destination is its persona's start_page"
            )
    for persona_id in persona_ids:
        if not any(t.kind == "thread" for t in suite.tasks_for(persona_id)):
            faults.append(
                f"persona {persona_id} has no 'follow your thread' task "
                "(ADR-0136 § Validation)"
            )
    return faults


def load_suite(path: Path) -> Suite:
    """Load and cross-check the suite at *path*.

    Raises:
        MetadataLoadError: If the file is not valid YAML or does not match
            :class:`Suite`.
        MetadataLoadErrors: One failure per rule the suite breaks: a task
            naming an unknown persona, a lookup task with no destination, a
            thread task declaring its own, a persona with no thread task, or
            a repeated id.
    """
    suite = validate(Suite, load_yaml(path), path=path)
    faults = _suite_faults(suite)
    if faults:
        raise MetadataLoadErrors(
            [MetadataLoadError(f, path=str(path)) for f in faults]
        )
    return suite
