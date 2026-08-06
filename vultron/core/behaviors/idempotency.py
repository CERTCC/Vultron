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

"""Reusable BT mixin enforcing the CLP-13 idempotency guard silence contract.

Per ``specs/case-ledger-processing.yaml`` CLP-13-001, CLP-13-002, CLP-13-003.
"""

import logging

from py_trees.common import Status


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

    Per ``specs/case-ledger-processing.yaml`` CLP-13-001, CLP-13-002, CLP-13-003.
    """

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
        return Status.FAILURE


__all__ = ["SilentIdempotencyGuardMixin"]
