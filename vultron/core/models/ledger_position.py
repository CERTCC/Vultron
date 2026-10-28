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

Each case stores the position its case file is a projection of
(SYNC-16-005, ADR-0142), and every case activity states its sender's tail
(SYNC-18-001, ADR-0156).  The full-case Invite's is the CASE_MANAGER's floor,
and each reply to it carries the replier's own position (CM-11-010,
CM-11-011, ADR-0121).  The position names the last entry
a copy of the ledger holds, so it is a pair: the entry's ``log_index`` and its
``entry_hash``.

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

    On the wire it is an object with ``logIndex`` and ``entryHash`` members.
    It is a value, not a record of its own: every case stores one as
    ``VulnerabilityCase.ledger_position``, the entry its case file reflects
    (SYNC-16-005), and every case activity carries its sender's as its
    ``ledgerPosition`` (SYNC-18-001), the full-case Invite's being the floor
    its reply must reach (VAM-04-011).
    """

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    log_index: int = Field(ge=EMPTY_LEDGER_LOG_INDEX)
    entry_hash: NonEmptyString


def accepted_entry_hash(position: LedgerPosition | None) -> str:
    """The ``entry_hash`` of the last entry *position* says was accepted.

    ``""`` when there is no position, or one at index -1: the sender holds
    no entry, so a replay starts from the beginning (CLP-08-005,
    SYNC-16-007).  The name the replay nodes read is ``last_accepted_hash``
    on the received event (SYNC-03-002, SYNC-17-003, SYNC-18-007).
    """
    if position is None or position.log_index == EMPTY_LEDGER_LOG_INDEX:
        return ""
    return position.entry_hash


__all__ = ["EMPTY_LEDGER_LOG_INDEX", "LedgerPosition", "accepted_entry_hash"]
