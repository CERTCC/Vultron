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

"""The check tree a run leaves: what a recording's ledger cannot see.

A **check tree** lists every ``demo_step``, ``demo_check`` and ``demo_gate`` a
scenario run entered, nested as they ran, each node carrying its kind, its
label, its outcome and the cast members whose containers it read
(DEMOCI-11-056, DEMOCI-11-057).  A case ledger holds the run's protocol *acts*,
so a change that moves a check out of its gate, or points a wait at another
actor's replica, leaves it byte-identical (#5596).  The check tree is the other
half of the evidence a consolidation change owes under DEMOMA-17-002.

The capture is **off by default**.  :func:`enter_check`, :func:`leave_check` and
:func:`note_container_read` return at once while no recorder is installed, so a
scenario run outside :func:`recording_checks` logs and behaves exactly as
before.  The three context managers in :mod:`vultron.demo.utils.failures` are
the only callers of the first two (DEMOCI-01-004), and the recorder's routed
client (:mod:`vultron.demo.recordings.runner`) is the only caller of the third:
capture at runtime, because no static pass can resolve which actor
``state.session(owner.name)`` is, and that subject is what EDF-06-002
constrains.

Design: ``notes/demo-scenario-tree.md`` § "Composition".
"""

from __future__ import annotations

import threading
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from vultron.errors import DemoRecordingError


class CheckKind(StrEnum):
    """Which of the three context managers a node is.

    The value is what a rendered trace and a written artifact carry, so the
    three stay distinguishable: DC-02-003 divides an action step from an
    observation-only assertion, and DEMOCI-01-007 divides a causal
    precondition from either.
    """

    STEP = "step"
    CHECK = "check"
    GATE = "gate"


class CheckOutcome(StrEnum):
    """Whether the body of a node left cleanly.

    ``FAILED`` is what the accumulator recorded a failure for: the three
    context managers suppress the exception and continue (DEMOCI-01-003), so
    the outcome is the only place the trace says a check did not hold.
    """

    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CheckNode:
    """One entered ``demo_step``, ``demo_check`` or ``demo_gate``.

    Attributes:
        kind: Which context manager this is.
        label: The description the scenario gave it.
        outcome: Whether its body left cleanly.
        reads: The cast members whose containers the node read, in name order.
            A read is attributed to the innermost node open when it was made,
            so a check moved out of its gate moves its reads with it.
        children: The nodes entered inside this one, in the order they ran.
    """

    kind: CheckKind
    label: str
    outcome: CheckOutcome
    reads: tuple[str, ...] = ()
    children: tuple[CheckNode, ...] = ()

    def to_json(self) -> dict[str, Any]:
        """Return this node as the JSON a written run artifact carries."""
        return {
            "kind": str(self.kind),
            "label": self.label,
            "outcome": str(self.outcome),
            "reads": list(self.reads),
            "children": [child.to_json() for child in self.children],
        }

    @classmethod
    def from_json(cls, raw: object) -> CheckNode:
        """Return the node *raw* describes.

        Raises:
            DemoRecordingError: When *raw* is not a node this module wrote.
                Read eagerly rather than left to fail later, so a malformed
                artifact names itself instead of comparing as a difference.
        """
        if not isinstance(raw, Mapping):
            raise DemoRecordingError(
                f"a check tree node is {type(raw).__name__}, not an object."
            )
        try:
            kind = CheckKind(raw["kind"])
            outcome = CheckOutcome(raw["outcome"])
            label = raw["label"]
            reads = tuple(raw["reads"])
            children = tuple(cls.from_json(child) for child in raw["children"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DemoRecordingError(
                f"a check tree node is not readable: {exc}"
            ) from exc
        if not isinstance(label, str) or not all(
            isinstance(name, str) for name in reads
        ):
            raise DemoRecordingError(
                f"check tree node {label!r} has a non-string label or read."
            )
        return cls(
            kind=kind,
            label=label,
            outcome=outcome,
            reads=reads,
            children=children,
        )


#: A run's check tree: its root nodes, in the order they ran.
CheckTree = tuple[CheckNode, ...]


def tree_to_json(tree: CheckTree) -> list[dict[str, Any]]:
    """Return *tree* as the JSON a written run artifact carries."""
    return [node.to_json() for node in tree]


def tree_from_json(raw: object) -> CheckTree:
    """Return the check tree *raw* describes.

    Raises:
        DemoRecordingError: When *raw* is not a tree :func:`tree_to_json`
            wrote.
    """
    if not isinstance(raw, list):
        raise DemoRecordingError(
            f"a check tree is {type(raw).__name__}, not a list of nodes."
        )
    return tuple(CheckNode.from_json(node) for node in raw)


@dataclass(slots=True)
class _OpenNode:
    """A node entered and not yet left, gathering its reads and children."""

    kind: CheckKind
    label: str
    reads: set[str] = field(default_factory=set)
    children: list[CheckNode] = field(default_factory=list)

    def close(self, outcome: CheckOutcome) -> CheckNode:
        """Return the finished node.

        The reads are sorted rather than kept in call order: a delivery that a
        read triggers runs on a worker thread (``_one_row_at_a_time``), so two
        runs can interleave two containers' reads differently, and an order
        that varies would read as a difference where nothing changed.
        """
        return CheckNode(
            kind=self.kind,
            label=self.label,
            outcome=outcome,
            reads=tuple(sorted(self.reads)),
            children=tuple(self.children),
        )


class CheckRecorder:
    """Gathers the check tree of one scenario run.

    Guarded by a lock because the recorder's in-process topology delivers on
    worker threads, so a read can be noted while the scenario thread is
    entering or leaving a node.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._open: list[_OpenNode] = []
        self._roots: list[CheckNode] = []

    def enter(self, kind: CheckKind, label: str) -> None:
        """Open a node of *kind* labelled *label* inside the current one."""
        with self._lock:
            self._open.append(_OpenNode(kind=kind, label=label))

    def leave(self, outcome: CheckOutcome) -> None:
        """Close the innermost open node with *outcome*.

        Raises:
            DemoRecordingError: When no node is open.  The three context
                managers pair every enter with a leave, so an unpaired leave
                means something else is driving the recorder.
        """
        with self._lock:
            if not self._open:
                raise DemoRecordingError(
                    "a check tree node was left while none was open; only the "
                    "demo_step, demo_check and demo_gate context managers "
                    "drive the recorder (DEMOCI-01-004)."
                )
            node = self._open.pop().close(outcome)
            (self._open[-1].children if self._open else self._roots).append(
                node
            )

    def note_read(self, cast_member: str) -> None:
        """Attribute a read of *cast_member*'s container to the open node.

        A read made while no node is open belongs to no check and is dropped:
        every poll and verification a scenario makes runs inside one of the
        three (DEMOCI-01-011, DEMOMA-22-007), so what is dropped here is the
        recorder's own setup and teardown traffic.
        """
        with self._lock:
            if self._open:
                self._open[-1].reads.add(cast_member)

    def tree(self) -> CheckTree:
        """Return the tree recorded so far.

        Raises:
            DemoRecordingError: When a node is still open, which would make the
                tree a prefix of the run rather than the run.
        """
        with self._lock:
            if self._open:
                still_open = ", ".join(node.label for node in self._open)
                raise DemoRecordingError(
                    "the check tree was read while these nodes were still "
                    f"open: {still_open}."
                )
            return tuple(self._roots)


class _RecorderSlot:
    """The installed recorder, or ``None`` while the capture is off.

    A slot object rather than a module global so that the three hooks read one
    attribute: a ``global`` rebind is invisible to a module that did
    ``from ... import _RECORDER``, and the hooks are hot paths on every demo
    check of every scenario.
    """

    value: CheckRecorder | None = None


_SLOT = _RecorderSlot()


def active_recorder() -> CheckRecorder | None:
    """Return the installed recorder, or ``None`` while the capture is off."""
    return _SLOT.value


@contextmanager
def recording_checks() -> Generator[CheckRecorder]:
    """Capture the check tree of the run inside this block.

    Yields the recorder; read its :meth:`CheckRecorder.tree` after the block,
    once every node it entered has been left.

    Raises:
        DemoRecordingError: When a capture is already installed.  Two nested
            captures would split one run's tree between them.
    """
    if _SLOT.value is not None:
        raise DemoRecordingError(
            "a check tree capture is already installed; one run records one "
            "tree."
        )
    recorder = CheckRecorder()
    _SLOT.value = recorder
    try:
        yield recorder
    finally:
        _SLOT.value = None


def enter_check(kind: CheckKind, label: str) -> None:
    """Open a check tree node, when a capture is installed."""
    recorder = _SLOT.value
    if recorder is not None:
        recorder.enter(kind, label)


def leave_check(outcome: CheckOutcome) -> None:
    """Close the innermost check tree node, when a capture is installed."""
    recorder = _SLOT.value
    if recorder is not None:
        recorder.leave(outcome)


def note_container_read(cast_member: str) -> None:
    """Attribute a container read, when a capture is installed."""
    recorder = _SLOT.value
    if recorder is not None:
        recorder.note_read(cast_member)


def tree_lines(tree: Iterable[CheckNode], depth: int = 0) -> list[str]:
    """Render *tree* as one line per node, for a diff a person reads.

    Each line is ``<indent><kind> <label> -> <outcome> reads=<members>``, with
    two spaces of indent per level, so a node that changed nesting moves and a
    node that changed its reads shows them.
    """
    lines: list[str] = []
    for node in tree:
        reads = ",".join(node.reads) or "-"
        lines.append(
            f"{'  ' * depth}{node.kind} {node.label} -> "
            f"{node.outcome} reads={reads}"
        )
        lines.extend(tree_lines(node.children, depth + 1))
    return lines


__all__ = [
    "CheckKind",
    "CheckNode",
    "CheckOutcome",
    "CheckRecorder",
    "CheckTree",
    "active_recorder",
    "enter_check",
    "leave_check",
    "note_container_read",
    "recording_checks",
    "tree_from_json",
    "tree_lines",
    "tree_to_json",
]
