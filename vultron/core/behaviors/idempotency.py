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

"""Reusable BT contracts for guards that detect an idempotent repeat.

- :class:`SilentIdempotencyGuardMixin` enforces the CLP-13 silence contract.
- :class:`ReportsIdempotentRepeat` is how a guard says its ``FAILURE`` was a
  repeat the handler reports ``SKIPPED``, not a refusal, so the refusal stage
  sends no refusal effect for it (CLP-10-022, CLP-05-001).

Per ``specs/case-ledger-processing.yaml`` CLP-13-001, CLP-13-002, CLP-13-003,
CLP-10-022.
"""

import logging
from typing import ClassVar, Protocol, runtime_checkable

from py_trees.common import Status


@runtime_checkable
class ReportsIdempotentRepeat(Protocol):
    """A guard whose ``FAILURE`` may be an idempotent repeat, not a refusal.

    ``failed_as_repeat`` is ``True`` only when the guard's last run failed
    because the activity repeats one whose effect is already in place, so
    the handler reports it ``SKIPPED`` (HP-01-003, ID-05-003).  A repeat was
    not refused, so the refusal stage runs no refusal effect for it: a
    ``Reject`` of it would contradict the effect already in place
    (CLP-10-022, CLP-05-001).
    """

    @property
    def failed_as_repeat(self) -> bool:
        """Whether the last run failed as an idempotent repeat."""
        ...


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
    "FlaggedRepeatGuardMixin",
    "ReportsIdempotentRepeat",
    "SilentIdempotencyGuardMixin",
]
