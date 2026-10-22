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

"""The owner a test gives a case when the owner's identity does not matter.

Every ``VulnerabilityCase`` has an owner (``attributed_to``): its genesis hash,
and so its whole ledger chain, is computed from it (CLP-08-002/003), so a case
without one is refused at construction (ARCH-10-001).  A test that builds a
case only to exercise something else names this owner rather than inventing
its own literal (CS-22-001).
"""

from typing import Any

from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)

CASE_OWNER_ID = "https://example.org/actors/case-owner"

#: A genesis hash a test case carries when its exact value does not matter.
#: A receiver keeps a carried hash rather than rederiving it (ADR-0103).
CASE_GENESIS_HASH = "0" * 64

#: The keys a wire-shaped (inbound) test case needs to validate: its owner, its
#: genesis hash, and the ledger position its wire form must name (SYNC-16-005),
#: here the empty ledger's.  Spread into a case dict as
#: ``{**INBOUND_CASE_OWNERSHIP, "type": "VulnerabilityCase", ...}``.
INBOUND_CASE_OWNERSHIP: dict[str, object] = {
    "attributedTo": CASE_OWNER_ID,
    "genesisHash": CASE_GENESIS_HASH,
    "ledgerPosition": {"logIndex": -1, "entryHash": CASE_GENESIS_HASH},
}

#: The same keys under field names, for a case built with ``model_construct``,
#: which runs no validator to compute the hash or start the position.
CONSTRUCTED_CASE_OWNERSHIP: dict[str, Any] = {
    "attributed_to": CASE_OWNER_ID,
    "genesis_hash": CASE_GENESIS_HASH,
    "ledger_position": LedgerPosition(
        log_index=EMPTY_LEDGER_LOG_INDEX, entry_hash=CASE_GENESIS_HASH
    ),
}

#: The same keys as a stored row holds them: plain JSON, field names.
STORED_CASE_OWNERSHIP: dict[str, object] = {
    "attributed_to": CASE_OWNER_ID,
    "genesis_hash": CASE_GENESIS_HASH,
    "ledger_position": {
        "log_index": EMPTY_LEDGER_LOG_INDEX,
        "entry_hash": CASE_GENESIS_HASH,
    },
}
