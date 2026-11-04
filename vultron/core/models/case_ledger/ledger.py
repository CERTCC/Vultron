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


"""The append-only, hash-chained canonical ledger of one case (SYNC-01)."""

import logging
from typing import Any

from vultron.core.models.case_ledger.record import HashChainLedgerRecord

logger = logging.getLogger(__name__)


class CaseLedger:
    """Append-only, hash-chained canonical case ledger.

    Maintains the full ordered list of :class:`HashChainLedgerRecord` objects
    for a single case. Enforces:

    - **Append-only**: entries are immutable once added; no removal or
      replacement is permitted (SYNC-01-001, SYNC-08-001).
    - **Hash-chain integrity**: each appended entry's ``prev_log_hash``
      references the ``entry_hash`` of the most recently appended entry
      (SYNC-01-003).
    - **Monotonically increasing** ``log_index`` values scoped to the case
      (SYNC-01-002).

    Every entry in the ledger is a canonical admitted assertion.  The ledger
    records only what happened, not what was refused.  Refusals are surfaced
    through Python logging, not ledger entries (CLP-04-007, CLP-04-008).

    Usage example::

        from vultron.core.models._helpers import format_timestamp, now_utc
        case_id = "https://example.org/cases/abc123"
        owner_id = "https://example.org/actors/vendor"
        created_at = now_utc()
        g_hash = compute_genesis_hash(case_id, created_at, owner_id)
        log = CaseLedger(case_id=case_id, genesis_hash=g_hash)
        entry = log.append(
            object_id="urn:uuid:report1",
            semantic_type="add_report_to_case",
            payload_snapshot={"id": "urn:uuid:report1"},
        )
        assert entry.log_index == 0
        assert entry.prev_log_hash == g_hash
        assert entry.verify_hash()

    Spec: SYNC-01-001, SYNC-01-002, SYNC-01-003, SYNC-07-001; CLP-04-001,
    CLP-04-003, CLP-04-007, CLP-08-002, CLP-08-004.
    """

    def __init__(self, case_id: str, genesis_hash: str) -> None:
        """Initialise an empty log for *case_id*.

        Args:
            case_id: URI of the :class:`VulnerabilityCase` this log tracks.
            genesis_hash: Per-case genesis hash computed via
                :func:`compute_genesis_hash`.  Used as ``prev_log_hash`` for
                the first entry and returned by :attr:`tail_hash` when the
                ledger is empty (CLP-08-004).
        """
        self._case_id = case_id
        self._genesis_hash = genesis_hash
        self._entries: list[HashChainLedgerRecord] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def case_id(self) -> str:
        """URI of the parent :class:`VulnerabilityCase`."""
        return self._case_id

    @property
    def entries(self) -> tuple[HashChainLedgerRecord, ...]:
        """All canonical entries as an immutable tuple."""
        return tuple(self._entries)

    @property
    def tail_hash(self) -> str:
        """Hash of the last entry, or the per-case genesis hash when empty.

        This is the ``prev_log_hash`` that the next entry MUST reference.

        Returns:
            64-character lowercase hex SHA-256 string, or the per-case
            genesis hash (see :func:`compute_genesis_hash`) if no entries
            exist yet (CLP-08-004).
        """
        return (
            self._entries[-1].entry_hash
            if self._entries
            else self._genesis_hash
        )

    @property
    def next_index(self) -> int:
        """Next ``log_index`` value that will be assigned on :meth:`append`.

        Returns:
            Integer equal to the current number of entries in the full log.
        """
        return len(self._entries)

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def append(
        self,
        object_id: str,
        semantic_type: str,
        payload_snapshot: dict[str, Any] | None = None,
        term: int | None = None,
    ) -> HashChainLedgerRecord:
        """Append a new canonical entry to the log and return it.

        Assigns ``log_index``, sets ``prev_log_hash`` from
        :attr:`tail_hash`, and computes ``entry_hash`` automatically.

        Args:
            object_id: Full URI of the asserted activity or primary object.
            semantic_type: The entry's semantic type (CLP-02-014).
            payload_snapshot: The asserted activity payload verbatim, for
                deterministic replay (CLP-02-003, CLP-07-011).
            term: Raft cluster term; ``None`` for single-node deployments.

        Returns:
            The newly created and appended :class:`HashChainLedgerRecord`.
        """
        entry = HashChainLedgerRecord(
            case_id=self._case_id,
            log_index=self.next_index,
            term=term,
            object_id=object_id,
            semantic_type=semantic_type,
            payload_snapshot=payload_snapshot or {},
            prev_log_hash=self.tail_hash,
        )
        self._entries.append(entry)
        logger.info(
            "Committed ledger entry: case_id=%s semantic_type=%s log_index=%d",
            self._case_id,
            semantic_type,
            entry.log_index,
        )
        logger.debug(
            "Ledger entry detail: entry_hash=%.16s… payload_snapshot=%s",
            entry.entry_hash,
            payload_snapshot or {},
        )
        return entry

    def verify_chain(self) -> bool:
        """Return ``True`` if the hash chain is internally consistent.

        Checks:

        1. Every entry's ``entry_hash`` matches its computed hash.
        2. Every entry's ``prev_log_hash`` equals the ``entry_hash`` of the
           previous entry (or the per-case genesis hash for the first).
        3. Every entry's ``log_index`` equals its position in :attr:`entries`.

        Returns:
            ``True`` if the chain is intact; ``False`` on the first violation.
        """
        prev_hash = self._genesis_hash
        for pos, entry in enumerate(self._entries):
            if entry.log_index != pos:
                return False
            if not entry.verify_hash():
                return False
            if entry.prev_log_hash != prev_hash:
                return False
            prev_hash = entry.entry_hash
        return True
