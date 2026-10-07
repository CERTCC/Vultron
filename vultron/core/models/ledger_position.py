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

"""A position in one case's ledger: the index and hash of a tail entry.

The full-case Invite carries the CASE_MANAGER's ledger position as a floor,
and each reply to it carries the replier's own position (CM-11-010,
CM-11-011, ADR-0121).  The position names the last entry a copy of the ledger
holds, so it is a pair: the entry's ``log_index`` and its ``entry_hash``.

An **empty ledger** has no last entry.  Its position is ``log_index == -1``
with ``entry_hash`` equal to the case's ``genesis_hash``, the same value
``CaseLedger.tail_hash`` returns for an empty log (CLP-08-004).  That keeps a
position a single shape: a hash chain's tail hash is always the value the next
entry's ``prev_log_hash`` must carry.
"""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin

EMPTY_LEDGER_LOG_INDEX = -1
"""``log_index`` of the position of a ledger with no entries (CLP-08-004)."""


class LedgerPosition(ValidatedAssignmentMixin, BaseModel):
    """The tail of a case ledger: ``log_index`` and ``entry_hash`` of its last entry.

    On the wire it is the ``ledgerTail`` object, with ``logIndex`` and
    ``entryHash`` members.  It is a value, not a stored record: a case carries
    one only on the copy placed in a full-case Invite, and never persists it
    on the case's own record.
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    log_index: int = Field(ge=EMPTY_LEDGER_LOG_INDEX)
    entry_hash: NonEmptyString


__all__ = ["EMPTY_LEDGER_LOG_INDEX", "LedgerPosition"]
