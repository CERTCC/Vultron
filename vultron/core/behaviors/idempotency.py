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

"""Reusable BT contracts a node uses to declare what its status means.

- :class:`SilentIdempotencyGuardMixin` enforces the CLP-13 silence contract.
- :class:`ReportsIdempotentRepeat` is how a guard says its ``FAILURE`` was a
  repeat the handler reports ``SKIPPED``, not a refusal, so the refusal stage
  sends no refusal effect for it (CLP-10-042, CLP-05-006).
  :func:`repeat_ending_run` finds the guard that said so on a failed run.
- :class:`ReportsNoChange` is how a node says the run it let succeed changed
  nothing, so the handler reports ``SKIPPED``, not ``APPLIED`` (ID-05-003,
  RSH-08-002).  :func:`unchanged_by_run` finds the node that said so.
- :class:`ReportsRefusal` is how a node says its ``FAILURE`` refused the
  received activity, and why, so the handler reports ``REFUSED`` with that
  reason (HP-01-003).  :func:`refusal_ending_run` finds the node that said
  so; :class:`DeclaredRefusalMixin` implements it.

Per ``specs/case-ledger-processing.yaml`` CLP-13-001, CLP-13-002, CLP-13-003,
CLP-10-022.
"""

import logging
from typing import ClassVar, Protocol, runtime_checkable

import py_trees
from py_trees.common import Status


@runtime_checkable
class ReportsIdempotentRepeat(Protocol):
    """A guard whose ``FAILURE`` may be an idempotent repeat, not a refusal.

    ``failed_as_repeat`` is ``True`` only when the guard's last run failed
    because the activity repeats one whose effect is already in place, so
    the handler reports it ``SKIPPED`` (HP-01-014, ID-05-003).  A repeat was
    not refused, so the refusal stage runs no refusal effect for it: a
    ``Reject`` of it would contradict the effect already in place
    (CLP-10-042, CLP-05-006).
    """

    @property
    def failed_as_repeat(self) -> bool:
        """Whether the last run failed as an idempotent repeat."""
        ...


@runtime_checkable
class ReportsNoChange(Protocol):
    """A node whose ``SUCCESS`` may mean the run had nothing to change.

    ``succeeded_without_change`` is ``True`` only when the node's last run
    succeeded because the change the activity asks for is already in place,
    so the work it guards was skipped and the handler reports the run
    ``SKIPPED``, not ``APPLIED`` (ID-05-003, RSH-08-002).  The node says why
    in ``no_change_reason``.  The other half of
    :class:`ReportsIdempotentRepeat`: a repeat guard ends the run in
    ``FAILURE``, while a node reporting no change lets it succeed.
    """

    @property
    def succeeded_without_change(self) -> bool:
        """Whether the last run succeeded with nothing to change."""
        ...

    @property
    def no_change_reason(self) -> str:
        """Why the run changed nothing, for the handler's ``SKIPPED``."""
        ...


@runtime_checkable
class ReportsRefusal(Protocol):
    """A node whose ``FAILURE`` may be a refusal of the received activity.

    ``declared_refusal`` is the reason the handler reports ``REFUSED`` with,
    and ``None`` unless the node's last run failed because the activity is
    refused (HP-01-003).  A node that fails for a local fault (a missing
    DataLayer or port) declares no refusal, so the runner reads that
    failure as ours (ADR-0095).  The reason is the sender's to read, so it
    names the condition and the requirement it cites (HP-01-005).
    """

    @property
    def declared_refusal(self) -> str | None:
        """Why the last run refused the activity, or ``None``."""
        ...


def repeat_ending_run(
    root: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour | None:
    """The guard on *root*'s failure chain that failed as a repeat, if any.

    Follows the chain ``BTBridge.get_failure_reason`` follows: the last failed
    child at each composite, down to the leaf that ended the run.  A guard
    that failed off that chain (an alternative a ``Selector`` tried first) did
    not decide the run, so its repeat flag is not read.  ``None`` when *root*
    did not fail, or no guard on the chain reports a repeat.
    """
    node = root
    while node.status == Status.FAILURE:
        if isinstance(node, ReportsIdempotentRepeat) and node.failed_as_repeat:
            return node
        failed = [c for c in node.children if c.status == Status.FAILURE]
        if not failed:
            return None
        node = failed[-1]
    return None


def unchanged_by_run(
    root: py_trees.behaviour.Behaviour,
) -> ReportsNoChange | None:
    """The node in *root* that let the run succeed with nothing to change.

    ``None`` when *root* did not succeed, or no node in it reports that it
    succeeded without a change.
    """
    if root.status != Status.SUCCESS:
        return None
    for node in root.iterate():
        if isinstance(node, ReportsNoChange) and node.succeeded_without_change:
            return node
    return None


def refusal_ending_run(root: py_trees.behaviour.Behaviour) -> str | None:
    """The reason the first node whose failure decided *root*'s declared.

    A node decided the run when it failed and every composite above it
    failed with it: the one failed child of a ``Sequence``, and each child
    of a failed ``Selector``, whose every alternative failed.  The search
    takes those in tree order, so a guard is found ahead of the fallback
    that answered it (a fault or a ``Reject`` that still fails the
    ``Selector``).  A node that failed under a decorator or composite that
    succeeded did not decide the run, so its declaration is not read.
    ``None`` when *root* did not fail, or no deciding node declares a
    refusal.  A local fault elsewhere on the run is the caller's to read
    first: the received runner raises on one before it asks this
    (ADR-0095).
    """
    if root.status != Status.FAILURE:
        return None
    if isinstance(root, ReportsRefusal) and root.declared_refusal:
        return root.declared_refusal
    for child in root.children:
        if (found := refusal_ending_run(child)) is not None:
            return found
    return None


class DeclaredRefusalMixin:
    """:class:`ReportsRefusal` for a node that fails through :meth:`_refuse`.

    The node returns ``self._refuse(reason)`` where its condition refuses
    the activity, and keeps returning plain ``Status.FAILURE`` for a local
    fault.  The declaration is cleared at the start of every run.
    """

    _refusal: str | None = None
    status: Status

    def initialise(self) -> None:
        self._refusal = None
        super().initialise()  # type: ignore[misc]

    @property
    def declared_refusal(self) -> str | None:
        """The reason given to :meth:`_refuse` on a run that failed."""
        return self._refusal if self.status == Status.FAILURE else None

    def _refuse(self, reason: str) -> Status:
        """Declare the run's failure a refusal for *reason*; ``FAILURE``.

        Raises:
            ValueError: *reason* is empty; a refusal names why (HP-01-005,
                CS-08-002).
        """
        if not reason:
            raise ValueError(
                f"{type(self).__name__}: a declared refusal needs a reason"
            )
        self._refusal = reason
        return Status.FAILURE


class FlaggedRepeatGuardMixin:
    """:class:`ReportsIdempotentRepeat` for a guard that sets a repeat flag.

    A guard that records a repeat in an attribute of its own (``is_repeat``,
    ``is_redelivery``, ``is_duplicate``) names it in ``_REPEAT_FLAG``; the
    guard resets the flag at the start of every run.
    """

    _REPEAT_FLAG: ClassVar[str]
    status: Status

    @property
    def failed_as_repeat(self) -> bool:
        """Whether the last run failed with the repeat flag set."""
        return (
            bool(getattr(self, self._REPEAT_FLAG))
            and self.status == Status.FAILURE
        )


class SilentIdempotencyGuardMixin:
    """CLP-13-002: Silent-FAILURE-on-duplicate contract for BT guard nodes.

    BT guard nodes that detect a duplicate activity (idempotency no-op) MUST:

    - Return ``Status.FAILURE`` so the enclosing Sequence aborts (CLP-13-001).
    - Make NO call to ``create_commit_log_entry_tree`` — no ``CaseLedgerEntry``
      of any disposition (CLP-13-001: MUST_NOT).
    - Emit a ``logger.info`` or ``logger.debug`` message (CLP-13-003: MUST).

    This mixin provides :meth:`_idempotent_failure` as the single call site
    for this contract.  Using it makes the "no ledger write" guarantee
    structural: the method returns ``FAILURE`` immediately after logging, so
    no subsequent write can follow within the same call chain.

    Usage::

        class MyGuardNode(SilentIdempotencyGuardMixin, DataLayerCondition):
            def update(self) -> Status:
                if duplicate_detected:
                    return self._idempotent_failure(
                        self.logger,
                        "%s: duplicate detected for '%s' — skipping (CLP-13-001)",
                        self.name,
                        self.some_id,
                    )
                return Status.SUCCESS

    A guard using it satisfies :class:`ReportsIdempotentRepeat`: its
    :attr:`failed_as_repeat` is ``True`` after a run that ended in
    :meth:`_idempotent_failure`.

    Per ``specs/case-ledger-processing.yaml`` CLP-13-001, CLP-13-002, CLP-13-003.
    """

    _repeat_detected: bool = False
    status: Status

    def initialise(self) -> None:
        self._repeat_detected = False
        super().initialise()  # type: ignore[misc]

    @property
    def failed_as_repeat(self) -> bool:
        """Whether the last run ended in :meth:`_idempotent_failure`."""
        return self._repeat_detected and self.status == Status.FAILURE

    def _idempotent_failure(
        self,
        logger: logging.Logger,
        message: str,
        *args: object,
    ) -> Status:
        """Log the idempotent no-op and return FAILURE. No ledger write may follow.

        Callers MUST return the result of this call immediately — they MUST NOT
        call ``create_commit_log_entry_tree`` or any other DataLayer write after
        this method (CLP-13-001).

        Args:
            logger: The node's managed logger.
            message: ``logging``-style format string describing the duplicate.
            *args: Format arguments for ``message``.

        Returns:
            ``Status.FAILURE`` unconditionally.
        """
        logger.info(message, *args)
        self._repeat_detected = True
        return Status.FAILURE


__all__ = [
    "DeclaredRefusalMixin",
    "FlaggedRepeatGuardMixin",
    "ReportsIdempotentRepeat",
    "ReportsNoChange",
    "ReportsRefusal",
    "SilentIdempotencyGuardMixin",
    "refusal_ending_run",
    "repeat_ending_run",
    "unchanged_by_run",
]
