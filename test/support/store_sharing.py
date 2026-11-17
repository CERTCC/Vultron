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

"""Fail a single-node run that opens one actor's store under two authorities.

A node maps each store's slug back to an actor id through its own base URL
(DL-07-012).  The single-app demo harness serves its actors under
``http://testserver``, so a store opened there under any other authority
means some code resolved the actor in the configured ``localhost:7999``
namespace instead.  The lifespan's sender-sequence hold timer did that: it
drained a held entry under the configured id, and the addressee door
refused the copy addressed to the ``testserver`` id (HP-01-005, #6085).

The SQLite engine reports the collision as a WARNING and carries on, so the
symptom surfaced only as a flaky refusal far from its cause.  This guard
turns the warning into a failure of the run that caused it.
"""

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager

from vultron.adapters.driven.datalayer_sqlite import engine as sqlite_engine

#: The engine's cross-authority warning, as :func:`getMessage` renders it.
_SHARED_STORE = re.compile(r"is shared by two distinct actor ids")


class _SharedStoreRecords(logging.Handler):
    """Collect every cross-authority store-sharing warning."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if _SHARED_STORE.search(message):
            self.messages.append(message)


@contextmanager
def no_store_shared_across_authorities() -> Iterator[None]:
    """Assert no actor store was opened under two authorities in the block.

    Reads the engine logger through its own handler rather than ``caplog``,
    so a test's own log-level settings cannot hide the warning.

    Raises:
        AssertionError: on exit, naming each store and its two actor ids.
    """
    logger = sqlite_engine.logger
    handler = _SharedStoreRecords()
    previous_level = logger.level
    logger.addHandler(handler)
    if logger.getEffectiveLevel() > logging.WARNING:
        logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
    assert not handler.messages, (
        "an actor store was opened under two authorities, so some code"
        " resolved a hosted actor outside the serving node's namespace"
        " (DL-07-012, #6085):\n" + "\n".join(handler.messages)
    )
