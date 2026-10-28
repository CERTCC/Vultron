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
from pathlib import Path

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
