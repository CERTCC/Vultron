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

"""A run's two traces, their normal form, and the files a run is written as.

A scenario run leaves two traces, because each is blind to what the other
sees: the **ledger** shows an added act, a changed note text or a changed
argument, and the **check tree** shows which ``demo_step``, ``demo_check`` and
``demo_gate`` ran, nested, with their outcomes and the cast members whose
containers they read (:mod:`vultron.demo.utils.check_tree`).  Comparing a
scenario's run at a pull request's base with its run at the head needs both
(DEMOCI-11-055).

Neither trace is byte-comparable as it stands.  The recording clock ticks 10 ms
on every read, so one added clock read shifts every later timestamp and digest,
and one extra id draw shifts every later id; neither is a change in what the
scenario does.  :func:`normalize_run` therefore relabels every id by its first
appearance, with **one** mapping across the scenario's ledger and its check
labels, and replaces timestamps and hash-chain digests with a placeholder
(DEMOCI-11-058, DEMOCI-11-059).  It changes nothing else (DEMOCI-11-060): a
changed note text, an added entry and a changed check label all survive it.

Dropping timestamps costs real coverage, because a time the protocol *derives*
reads the same as one the clock minted: an embargo's ``startTime`` and
``endTime``, an invite's ``rsvpDeadline`` and the embargo name that quotes
them all go with the clock, so a change to the default embargo window or the
RSVP window compares equal.  The gate is not a check on those constants; the
blind spot is recorded in ``notes/demo-scenario-tree.md`` § "Composition".

Design: ``notes/demo-scenario-tree.md`` § "Composition".
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Container, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vultron.demo.utils.check_tree import (
    CheckNode,
    CheckTree,
    tree_from_json,
    tree_lines,
    tree_to_json,
)
from vultron.errors import DemoRecordingError

#: The ledger of a written run, one JSON entry per line.
LEDGER_FILENAME = "ledger.jsonl"

#: The check tree of a written run, as :func:`.check_tree.tree_to_json` writes it.
CHECKS_FILENAME = "checks.json"

#: An id a run draws.  Every id the protocol mints is a ``uuid4`` drawn from the
#: run's seeded generator (:mod:`vultron.demo.determinism`), so matching the
#: UUID alone relabels the ids that shift and leaves the cast's actor URIs
#: spelled out: the cast is fixed (DEMOCI-11-020), so those never shift, and a
#: diff that still names ``actor1`` is a diff a person can read.
_ID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

#: A timestamp, in the ISO-8601 spelling Pydantic serializes one as.  Matched
#: anywhere in a string rather than only as a whole value, because a note or a
#: participant name may quote a time it was given.
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?"
)

#: What a dropped timestamp reads as.
TIMESTAMP_PLACEHOLDER = "<timestamp>"

#: What a dropped hash-chain digest reads as.
DIGEST_PLACEHOLDER = "<digest>"

#: The suffix of every hash-chain digest field a ledger entry or a nested sync
#: payload carries (``prevLogHash``, ``entryHash``, a sync activity's tail
#: hash).  A suffix rather than a list of names, so a new digest field is
#: dropped without an edit here.  What holds the rule is not this constant but
#: the shape of a digest: ``test/demo_unit/test_recording_traces.py`` normalizes
#: a real :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry` and
#: fails if any 64-character hex value survives, so a digest field renamed out
#: of this suffix fails there rather than silently stopping being dropped
#: (#5535).
DIGEST_KEY_SUFFIX = "Hash"


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    """One run of one scenario: the two traces a comparison reads.

    Attributes:
        scenario: The scenario name.
        ledger: Its canonical case ledger, as JSONL.
        checks: Its check tree.
    """

    scenario: str
    ledger: str
    checks: CheckTree


@dataclass(frozen=True, slots=True)
class NormalizedRun:
    """A run with its ids relabelled and its clock-borne values dropped.

    Attributes:
        scenario: The scenario name.
        ledger: One line per ledger entry, normalized.
        checks: One line per check tree node, normalized and indented by
            nesting depth.
    """

    scenario: str
    ledger: tuple[str, ...]
    checks: tuple[str, ...]


class _IdLabels:
    """One run's id relabelling: each id becomes ``id-N`` by first appearance.

    Shared across the run's ledger and its check labels (DEMOCI-11-058), so an
    id that both name reads the same in each.
    """

    def __init__(self) -> None:
        self._labels: dict[str, str] = {}

    def relabel(self, text: str) -> str:
        """Return *text* with every id in it replaced by its label."""
        return _ID_RE.sub(self._label, text)

    def _label(self, match: re.Match[str]) -> str:
        drawn = match.group(0)
        if drawn not in self._labels:
            self._labels[drawn] = f"id-{len(self._labels) + 1}"
        return self._labels[drawn]


def _normalize_text(text: str, ids: _IdLabels) -> str:
    """Return *text* with its ids relabelled and its timestamps dropped."""
    return _TIMESTAMP_RE.sub(TIMESTAMP_PLACEHOLDER, ids.relabel(text))


def _normalize_value(value: Any, ids: _IdLabels) -> Any:
    """Return *value* normalized, walking a parsed ledger entry.

    A value under a hash-chain digest key is replaced whole: the digest covers
    the entry's content, so it changes whenever anything before it did, which
    would report every scenario as different from its own base.
    """
    if isinstance(value, Mapping):
        return {
            key: (
                DIGEST_PLACEHOLDER
                if isinstance(key, str) and key.endswith(DIGEST_KEY_SUFFIX)
                else _normalize_value(item, ids)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_value(item, ids) for item in value]
    if isinstance(value, str):
        return _normalize_text(value, ids)
    return value


def _normalize_entry(
    line: str, scenario: str, number: int, ids: _IdLabels
) -> str:
    """Return one normalized ledger line.

    Raises:
        DemoRecordingError: When the line is not a JSON object.  A ledger the
            recorder wrote always is (:func:`~.ledgers.canonical_ledger`
            refuses anything else), so a line that is not says the run
            directory was not written by this tool.
    """
    try:
        entry = json.loads(line)
    except ValueError as exc:
        raise DemoRecordingError(
            f"scenario {scenario!r}, ledger line {number}, is not a JSON "
            f"ledger entry: {exc}"
        ) from exc
    if not isinstance(entry, dict):
        raise DemoRecordingError(
            f"scenario {scenario!r}, ledger line {number}, is a "
            f"{type(entry).__name__}, not a ledger entry object."
        )
    return json.dumps(_normalize_value(entry, ids), sort_keys=False)


def _normalize_checks(tree: Iterable[CheckNode], ids: _IdLabels) -> CheckTree:
    """Return *tree* with every id in a node's label relabelled."""
    return tuple(
        CheckNode(
            kind=node.kind,
            label=_normalize_text(node.label, ids),
            outcome=node.outcome,
            reads=node.reads,
            children=_normalize_checks(node.children, ids),
        )
        for node in tree
    )


def normalize_run(run: ScenarioRun) -> NormalizedRun:
    """Return *run* in the form two runs are compared in.

    The ledger is read first and the check tree second, so one mapping covers
    both and the order of first appearance is fixed.

    Raises:
        DemoRecordingError: When a ledger line is not a JSON ledger entry.
    """
    ids = _IdLabels()
    ledger = tuple(
        _normalize_entry(line, run.scenario, number, ids)
        for number, line in enumerate(run.ledger.splitlines(), start=1)
    )
    return NormalizedRun(
        scenario=run.scenario,
        ledger=ledger,
        checks=tuple(tree_lines(_normalize_checks(run.checks, ids))),
    )


def write_run(run: ScenarioRun, root: Path) -> Path:
    """Write *run*'s two traces under ``root/<scenario>/``.

    Nothing here is committed: no pull request regenerates a recording
    (#3901), and the comparison records both sides itself.

    Returns:
        The directory written.
    """
    directory = root / run.scenario
    directory.mkdir(parents=True, exist_ok=True)
    (directory / LEDGER_FILENAME).write_text(run.ledger, encoding="utf-8")
    (directory / CHECKS_FILENAME).write_text(
        json.dumps(tree_to_json(run.checks), indent=2) + "\n",
        encoding="utf-8",
    )
    return directory


def _run_directories(root: Path) -> list[Path]:
    """The directories under *root* that hold a written run, or half of one.

    A directory holding neither trace file is not a run and is skipped: a
    cache directory beside the runs, or a CI artifact that extracted into a
    nested folder, would otherwise take the whole comparison down with a
    message naming it as a scenario.  One holding exactly one of the two is
    the genuine half-written run, and is kept so that :func:`read_runs`
    refuses it.
    """
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir()
        and (
            (path / LEDGER_FILENAME).exists()
            or (path / CHECKS_FILENAME).exists()
        )
    )


def read_runs(root: Path) -> dict[str, ScenarioRun]:
    """Return the runs :func:`write_run` left under *root*, by scenario name.

    Raises:
        DemoRecordingError: When *root* is not a directory, or a scenario
            directory under it holds only one of the two traces, or an
            unreadable one.  A half-written run is refused rather than
            compared, so a run that failed before its traces landed does not
            read as "no difference".
    """
    if not root.is_dir():
        raise DemoRecordingError(
            f"{root} is not a directory of recorded runs."
        )
    runs: dict[str, ScenarioRun] = {}
    for directory in _run_directories(root):
        name = directory.name
        try:
            ledger = (directory / LEDGER_FILENAME).read_text(encoding="utf-8")
            checks = (directory / CHECKS_FILENAME).read_text(encoding="utf-8")
        except OSError as exc:
            raise DemoRecordingError(
                f"the recorded run of {name!r} in {root} is incomplete: {exc}"
            ) from exc
        try:
            tree = tree_from_json(json.loads(checks))
        except (ValueError, DemoRecordingError) as exc:
            # `tree_from_json` raises `DemoRecordingError`, which is not a
            # `ValueError`: without it a valid-JSON-but-not-a-tree file
            # escaped naming neither the scenario nor the directory.
            raise DemoRecordingError(
                f"the check tree of {name!r} in {root} is not readable: {exc}"
            ) from exc
        runs[name] = ScenarioRun(name, ledger=ledger, checks=tree)
    return runs


def prune_runs(root: Path, keep: Container[str]) -> list[str]:
    """Remove the written runs under *root* whose scenario is not in *keep*.

    A write into a reused directory would otherwise leave an earlier, now
    stale run in place, and :func:`read_runs` would read it as that side's
    current evidence.  Only directories that hold a written run are touched
    (:func:`_run_directories`), so nothing else under *root* is removed.

    Returns:
        The scenario names removed, in name order.
    """
    removed = []
    for directory in _run_directories(root) if root.is_dir() else []:
        if directory.name not in keep:
            shutil.rmtree(directory)
            removed.append(directory.name)
    return removed


__all__ = [
    "CHECKS_FILENAME",
    "DIGEST_KEY_SUFFIX",
    "DIGEST_PLACEHOLDER",
    "LEDGER_FILENAME",
    "NormalizedRun",
    "ScenarioRun",
    "TIMESTAMP_PLACEHOLDER",
    "normalize_run",
    "prune_runs",
    "read_runs",
    "write_run",
]
