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

"""The polling primitives every demo wait is built on.

Holds the shared timeout constants (EDF-06-006, EDF-06-008), the
``_poll_until`` and ``_poll_datalayer_for`` loops, and the two deadline
types they share: :class:`ProgressDeadline` and :class:`SharedBudget`.
"""

import logging
import time
from collections.abc import Callable, Sequence

from vultron.demo.utils import (
    DataLayerClient,
    read_stored_of_types,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared timeout constants (EDF-06-006, EDF-06-008)
# ---------------------------------------------------------------------------

# 15 s: conservative cross-container delivery budget.
CROSS_CONTAINER_TIMEOUT: float = 15.0
# 20 s: invitation-chain propagation (find invite → accept → case replica seed).
PARTICIPANT_JOIN_TIMEOUT: float = 20.0
# 90 s: late-joiner and complex multi-hop join paths.
LATE_JOINER_TIMEOUT: float = 90.0
# 30 s: late-joiner replica catch-up after the join gate passes.
LATE_JOINER_REPLICA_TIMEOUT: float = 30.0
# 10 s: early participant's replica participant-index propagation budget.
REPLICA_PARTICIPANT_TIMEOUT: float = 10.0
# 30 s: the EM-transition delivery chain — the CASE_MANAGER commits the
# transition, fans out Announce(CaseLedgerEntry), and the polled replica
# applies it (ADR-0058).  The longest wait on that chain is embargo teardown
# at publication, measured at 1.92–4.73 s over 13 samples from 7 main-push
# Demo Integration runs on 2026-11-04/05, in both extension scenarios; 30 s
# is a 6.3x margin on the worst of those.  That band is a sample, not a
# ceiling: a 38-job sweep of the same window, scenarios and event reached
# 4.76 s, which is still 6.3x.  Sized from that measurement and not widened
# on report: the single flake behind #1978 was bracketed by passing runs of
# the same scenario, so there was nothing to widen for.
EM_TRANSITION_TIMEOUT: float = 30.0
# 30 s: contiguous ledger-coverage budget for a replica that has been receiving
# Announce(CaseLedgerEntry) as each entry was committed. 15 s fired at 0/29
# entries under CI load (#1911, #2337).
LEDGER_COVERAGE_TIMEOUT: float = 30.0
# 45 s: contiguous ledger-coverage budget for a late joiner, which catches up
# from genesis through the CM-17-004 backfill — one Announce per prior entry.
# Both coverage budgets are stall budgets: each newly arrived entry restarts
# them, up to BACKFILL_PROGRESS_CEILING (wait_for_contiguous_ledger_coverage).
LATE_JOINER_COVERAGE_TIMEOUT: float = 45.0
# 300 s: ceiling for a wait that follows a late joiner's backfill
# (:class:`ProgressDeadline`).  Such a wait fails when the joiner's ledger copy
# stops advancing, not when a fixed budget runs out: the backfill is one
# Announce per prior entry, applied one at a time by the joiner's inbox, and
# under CI load it ran from 26 s to over 100 s for the same 50-odd entries
# (#4424).  The ceiling only stops a wait that keeps seeing progress from
# running for ever; it is about three times the slowest backfill seen in CI.
BACKFILL_PROGRESS_CEILING: float = 300.0


def _client_in(
    client: DataLayerClient, clients: "Sequence[DataLayerClient]"
) -> bool:
    """Identity-based membership: is *client* one of *clients*?

    Demo clients are plain objects with no equality of their own, and two
    clients for the same container are still two clients, so membership in a
    late-joiner or covered-replica list is decided by identity, not equality.
    """
    return any(client is candidate for candidate in clients)


# ---------------------------------------------------------------------------
# Generic polling primitive
# ---------------------------------------------------------------------------


class ProgressDeadline:
    """A deadline that moves forward while the awaited cause visibly advances.

    A wait whose effect lands behind a queue of work — a late joiner's
    full-case Invite, queued after the ledger backfill (CM-11-010) — cannot be
    bounded by a fixed budget, because the queue's length times its per-item
    cost under load is not known in advance (#4424).  Gating on the cause
    (EDF-06, ADR-0058) means watching the queue drain: each reading of the
    progress measure that is higher than every earlier one restarts the
    *stall* budget.  The wait then fails only when nothing has advanced for
    ``stall_seconds``, or at ``ceiling_seconds`` from construction, whichever
    comes first.

    With no readings at all it is a plain ``stall_seconds`` deadline.  The
    first reading only sets the baseline, so progress made before the wait
    began earns no extra time.

    Args:
        stall_seconds: Seconds the measure may go without advancing.
        ceiling_seconds: Seconds after construction at which the wait ends
            however much progress it sees; never less than ``stall_seconds``.
    """

    def __init__(self, stall_seconds: float, ceiling_seconds: float) -> None:
        now = time.monotonic()
        self._stall = stall_seconds
        self._ceiling_seconds = max(stall_seconds, ceiling_seconds)
        self._ceiling = now + self._ceiling_seconds
        self._deadline = now + stall_seconds
        self._best: int | None = None

    def observe(self, progress: int) -> None:
        """Record a reading; restart the stall budget if it is a new high."""
        if self._best is None:
            self._best = progress
        elif progress > self._best:
            self._best = progress
            self._deadline = min(time.monotonic() + self._stall, self._ceiling)

    def expired(self) -> bool:
        """Whether the wait has run out of time."""
        return time.monotonic() >= self._deadline

    def describe(self) -> str:
        """Name the last progress reading, for a timeout message."""
        if self._best is None:
            return "no progress reading was taken"
        if (
            self._ceiling_seconds > self._stall
            and self._deadline >= self._ceiling
        ):
            return (
                f"progress reached {self._best} and was still advancing when"
                f" the wait hit its {self._ceiling_seconds:.0f} s ceiling"
            )
        return (
            f"progress reached {self._best}, then did not advance for"
            f" {self._stall:.0f} s"
        )


def _poll_until(
    condition_fn: Callable[[], bool],
    timeout_seconds: float,
    poll_interval: float = 0.5,
    error_msg: str = "Timed out waiting for condition",
    swallow_exceptions: bool = True,
    progress: ProgressDeadline | None = None,
) -> None:
    """Poll *condition_fn* until it returns ``True`` or the deadline passes.

    Args:
        condition_fn: Callable returning ``True`` when the condition is met.
        timeout_seconds: Maximum time to wait in seconds.
        poll_interval: Seconds between successive calls to *condition_fn*.
        error_msg: Message for the ``AssertionError`` raised on timeout.
        swallow_exceptions: When ``True``, exceptions raised by *condition_fn*
            are caught and treated as ``False`` (poll continues).  When
            ``False``, exceptions propagate immediately.
        progress: When given, replaces the fixed *timeout_seconds* deadline;
            *condition_fn* feeds it readings, so the wait lasts as long as the
            cause keeps advancing (:class:`ProgressDeadline`).

    Raises:
        AssertionError: If *condition_fn* does not return ``True`` within
            *timeout_seconds*. When exceptions were swallowed, the last one is
            named in the message — a condition that never *ran* is a different
            fault from one that ran and stayed false, and reporting both as a
            bare timeout sends the reader looking for a slow protocol instead of
            a broken read.
    """
    # The condition is always tried at least once, even with no time left: a
    # wait handed the tail of a shared budget (SharedBudget) must still succeed
    # when its effect has already landed, and fail only when it has not.
    deadline = (
        progress
        if progress is not None
        else ProgressDeadline(timeout_seconds, timeout_seconds)
    )
    last_exc: Exception | None = None
    while True:
        try:
            if condition_fn():
                return
            last_exc = None
        except Exception as exc:
            if not swallow_exceptions:
                raise
            last_exc = exc
        if deadline.expired():
            break
        time.sleep(poll_interval)

    if last_exc is not None:
        raise AssertionError(
            f"{error_msg} — the check never completed: every attempt raised"
            f" {type(last_exc).__name__}: {last_exc}"
        ) from last_exc
    if progress is not None:
        raise AssertionError(f"{error_msg} ({progress.describe()})")
    raise AssertionError(error_msg)


class SharedBudget:
    """One timeout shared by consecutive waits on the same delivery chain.

    When several replicas are fed by one fan-out, waiting on each with its
    own full timeout multiplies the worst case by the number of replicas and
    hides which hop was slow.  A shared budget bounds the whole fan-out once:
    each wait is given what is left.  A wait that starts with nothing left
    still checks its condition once (:func:`_poll_until`), so a replica that
    has already caught up passes, and one that has not fails at once with
    that wait's own message — the budget itself says only how much was left
    (``repr(budget)``), which the scenario logs on exhaustion.

    Args:
        timeout_seconds: The total budget, started on construction.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self._total = timeout_seconds
        self._deadline = time.monotonic() + timeout_seconds

    def remaining(self) -> float:
        """Seconds left, never negative."""
        return max(0.0, self._deadline - time.monotonic())

    def __repr__(self) -> str:
        return (
            f"SharedBudget(total={self._total:.1f}s,"
            f" remaining={self.remaining():.1f}s)"
        )


# ---------------------------------------------------------------------------
# Generic DataLayer scan helper
# ---------------------------------------------------------------------------


def _poll_datalayer_for(
    client: DataLayerClient,
    object_types: Sequence[str],
    discriminator_fn: Callable[[dict], bool],
    timeout_seconds: float,
    poll_interval: float,
    log_msg: str,
    error_msg: str,
    id_fn: Callable[[str, dict], str] | None = None,
    progress_fn: Callable[[], int] | None = None,
    progress_ceiling: float = BACKFILL_PROGRESS_CEILING,
) -> str:
    """Poll the client's own DataLayer until *discriminator_fn* matches.

    The path is ``client.dl_path()`` — the *actor-scoped* collection, not the
    retired unscoped ``/datalayer/``.  Under ADR-0073 there is no store that is
    not some actor's own, so a poll must name whose store it is reading.

    Each tick reads the store's objects of *object_types* — serialized as the
    whole-store dump serializes them — and calls *discriminator_fn* on every
    ``dict``-typed value.  Returns the matching object's raw ID string on the
    first match.  The read is never the whole store: the polled container is
    often the one doing the work being waited on, and rehydrating and
    serializing its every object twice a second slowed that work down as the
    store grew (#4600).

    Args:
        client: DataLayerClient to poll.
        object_types: The stored types the awaited object can be held as.
        discriminator_fn: Callable receiving a single ``dict`` and returning
            ``True`` when the target object is found.
        timeout_seconds: Maximum seconds to wait before raising.
        poll_interval: Seconds between successive GET calls.
        log_msg: ``%``-style format string with a single ``%s`` placeholder
            for the matched object ID; logged at INFO on a successful find.
        error_msg: Message for the ``AssertionError`` raised on timeout.
        id_fn: Maps a match's raw ID and data to the ID returned; the raw ID
            itself when omitted.  A record that wraps another object (a
            received-activity archive) returns the wrapped object's ID.
        progress_fn: Reads how far the work queued ahead of the awaited
            object has got.  When given, *timeout_seconds* is
            a stall budget that each advance restarts, up to
            *progress_ceiling* (:class:`ProgressDeadline`); when omitted it is
            a fixed deadline.
        progress_ceiling: Seconds after which a *progress_fn* wait gives up
            however much progress it sees.

    Returns:
        The ID of the first matching object, as *id_fn* derives it.

    Raises:
        AssertionError: If no matching object is found in time.
    """
    deadline = ProgressDeadline(
        timeout_seconds,
        progress_ceiling if progress_fn is not None else timeout_seconds,
    )
    while not deadline.expired():
        try:
            objects = read_stored_of_types(client, object_types)
            for raw_id, obj_data in objects.items():
                if not isinstance(obj_data, dict):
                    continue
                if discriminator_fn(obj_data):
                    obj_id = (
                        id_fn(str(raw_id), obj_data)
                        if id_fn is not None
                        else str(raw_id)
                    )
                    logger.info(log_msg, obj_id)
                    return obj_id
            # Read progress only after the match, so a reading that raises
            # can never hide an object that has already arrived.
            if progress_fn is not None:
                deadline.observe(progress_fn())
        except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
            pass
        time.sleep(poll_interval)
    if progress_fn is not None:
        raise AssertionError(f"{error_msg} ({deadline.describe()})")
    raise AssertionError(error_msg)
