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

"""Read a run's ledger dump and check every replica against the canonical one."""

import json
from collections.abc import Sequence
from pathlib import Path

from vultron.demo.helpers.harness import StepMark
from vultron.demo.helpers.ledger_dump import STEP_MARKS_FILENAME
from vultron.demo.scenario.tree import PathStep
from vultron.errors import DemoRecordingError

#: The dump target whose ledger is the canonical one, and the only one committed.
CANONICAL_ACTOR = "case-actor"


def read_dump(devlogs: Path, scenario: str) -> dict[str, str]:
    """Return the dumped ledger of each actor in the scenario's manifest.

    Raises:
        DemoRecordingError: When an actor's ledger was not captured.
    """
    manifest = json.loads(
        (devlogs / scenario / "dump-manifest.json").read_text(encoding="utf-8")
    )
    ledgers: dict[str, str] = {}
    for actor in manifest["actors"]:
        if not actor.get("captured") or not actor.get("ledgerFile"):
            raise DemoRecordingError(
                f"scenario {scenario!r}: the ledger of "
                f"{actor.get('actorName')!r} was not captured "
                f"({actor.get('reason') or 'no reason recorded'})."
            )
        ledgers[actor["actorName"]] = (
            devlogs / scenario / actor["ledgerFile"]
        ).read_text(encoding="utf-8")
    return ledgers


def _entries_by_index(actor: str, text: str) -> dict[int, str]:
    """Return each JSONL line of *text* keyed by its entry's ``logIndex``."""
    entries: dict[int, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            entries[json.loads(line)["logIndex"]] = line
        except (ValueError, KeyError, TypeError) as exc:
            raise DemoRecordingError(
                f"the ledger of {actor!r}, line {number}, is not a ledger "
                f"entry with a logIndex: {exc}"
            ) from exc
    return entries


def canonical_ledger(scenario: str, ledgers: dict[str, str]) -> str:
    """Return the canonical ledger of a run, after checking every replica.

    Each replica entry must be byte-identical to the canonical entry at the
    same ``logIndex`` (CLP-07-013).  A replica may hold fewer entries, for
    example a participant that left before the case closed (CM-23-004).

    Raises:
        DemoRecordingError: When the dump holds no canonical ledger, or a
            replica entry is absent from or differs from the canonical one.
    """
    if CANONICAL_ACTOR not in ledgers:
        raise DemoRecordingError(
            f"scenario {scenario!r} dumped no {CANONICAL_ACTOR!r} ledger; "
            f"it dumped {sorted(ledgers)}."
        )
    canonical = _entries_by_index(CANONICAL_ACTOR, ledgers[CANONICAL_ACTOR])
    for actor, text in ledgers.items():
        if actor == CANONICAL_ACTOR:
            continue
        for index, line in _entries_by_index(actor, text).items():
            if canonical.get(index) != line:
                raise DemoRecordingError(
                    f"scenario {scenario!r}: the replica of {actor!r} holds "
                    f"an entry at logIndex {index} that "
                    + (
                        "the canonical ledger does not."
                        if index not in canonical
                        else "differs from the canonical entry."
                    )
                )
    return ledgers[CANONICAL_ACTOR]


def parse_step_marks(
    text: str, scenario: str, path: Sequence[PathStep]
) -> tuple[StepMark, ...]:
    """Parse step marks, after checking they cover *path*.

    The harness records one mark per declared step the scenario reports
    reaching (:meth:`~vultron.demo.helpers.harness.ScenarioHarness.reach_step`).
    A recording is kept only with a mark for every step, in order, so the
    shared-prefix check never reads a guessed branch point (DEMOCI-11-017).

    Args:
        text: The marks, as the harness writes them.
        scenario: The scenario name, for messages.
        path: The scenario's declared path.

    Raises:
        DemoRecordingError: When the marks are malformed, do not name exactly
            the declared steps in order, or put a later step before an
            earlier one in the ledger.
    """
    try:
        marks = tuple(
            StepMark(
                branch_point=step["branchPoint"],
                choice=step["choice"],
                ledger_tail=step["ledgerTail"],
            )
            for step in json.loads(text)["steps"]
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise DemoRecordingError(
            f"scenario {scenario!r}: the step marks are not readable: {exc}"
        ) from exc
    reached = [(mark.branch_point, mark.choice) for mark in marks]
    if reached != list(path):
        raise DemoRecordingError(
            f"scenario {scenario!r} reported reaching {reached}, but its "
            f"declared path is {list(path)}; every step needs a "
            "harness.reach_step() call."
        )
    tails = [mark.ledger_tail for mark in marks]
    if (
        any(
            isinstance(tail, bool) or not isinstance(tail, int)
            for tail in tails
        )
        or any(tail < 0 for tail in tails)
        or tails != sorted(tails)
    ):
        raise DemoRecordingError(
            f"scenario {scenario!r} recorded ledger tails {tails}; each must "
            "be a count of entries, and a later step cannot come before an "
            "earlier one in the ledger."
        )
    return marks


def read_step_marks(
    devlogs: Path, scenario: str, path: Sequence[PathStep]
) -> tuple[StepMark, ...]:
    """Return the step marks of a run, checked by :func:`parse_step_marks`.

    Raises:
        DemoRecordingError: When the run left no marks, or as
            :func:`parse_step_marks`.
    """
    marks_file = devlogs / scenario / STEP_MARKS_FILENAME
    try:
        text = marks_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise DemoRecordingError(
            f"scenario {scenario!r} left no step marks ({marks_file.name}): "
            f"{exc}"
        ) from exc
    return parse_step_marks(text, scenario, path)
