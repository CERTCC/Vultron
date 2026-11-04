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

"""Append-only canonical case ledger for AppendOnlyLedger.

This module provides:

- :func:`compute_genesis_hash` — derive the per-case genesis hash from case
  identity metadata (CLP-08-001, CLP-08-002).
- :class:`HashChainLedgerRecord` — a single canonical ledger entry with
  hash-chain linkage and an optional embedded activity payload snapshot.
- :class:`CaseLedger` — an append-only, hash-chained ledger for a single case.

Per-peer replication state tracking is provided by
:class:`~vultron.core.models.replication_state.VultronReplicationState`
in ``vultron.core.models.replication_state``.

Design follows the single-writer CaseActor architecture described in
``notes/sync-ledger-replication.md`` and the requirements in
``specs/sync-ledger-replication.yaml`` (SYNC-01) and
``specs/case-ledger-processing.yaml`` (CLP-01 through CLP-08).

Hash chain:

- Each :class:`HashChainLedgerRecord` stores the SHA-256 hash of its own
  canonical content (``entry_hash``) and the hash of its immediate predecessor
  (``prev_log_hash``).
- The first entry uses the per-case genesis hash (see
  :func:`compute_genesis_hash`) as ``prev_log_hash`` (CLP-08-001,
  CLP-08-004).
- Canonical serialization uses deterministic JSON (``sort_keys=True``,
  compact separators, UTF-8) — compatible with RFC 8785 JCS and
  forward-compatible with a future Merkle Tree implementation.
- ``entry_hash`` is excluded from the content that is hashed (to avoid a
  self-referential dependency).

Append-only enforcement:

- :class:`CaseLedger` rejects any attempt to modify or remove existing
  entries.  New entries are appended via :meth:`CaseLedger.append`.

**Canonical entries only**: the case ledger records protocol-significant
assertions that the CASE_MANAGER admitted.  Refused assertions and
locally-scoped markers are not ledger entries — they are logging events.  See
``notes/case-ledger-authority.md`` and CLP-04-007.

Per ``specs/sync-ledger-replication.yaml`` SYNC-01, SYNC-07,
``specs/case-ledger-processing.yaml`` CLP-02 through CLP-08, and
``notes/sync-ledger-replication.md``.
"""

from vultron.core.models.case_ledger.hashing import compute_genesis_hash
from vultron.core.models.case_ledger.ledger import CaseLedger
from vultron.core.models.case_ledger.record import (
    HashChainLedgerRecord,
    ledger_entry_hash_intact,
)

__all__ = [
    "CaseLedger",
    "HashChainLedgerRecord",
    "compute_genesis_hash",
    "ledger_entry_hash_intact",
]
