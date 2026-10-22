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

CASE_OWNER_ID = "https://example.org/actors/case-owner"

#: A time a wire-shaped test case claims, so a receiver can derive its genesis
#: hash from the carried owner and time (CLP-08-002, ADR-0103).
CASE_PUBLISHED = "2026-01-01T00:00:00+00:00"

#: The keys a wire-shaped (inbound) test case needs to validate: its owner and
#: the ``published`` time its genesis hash is derived from.  Spread into a case
#: dict as ``{**INBOUND_CASE_OWNERSHIP, "type": "VulnerabilityCase", ...}``.
INBOUND_CASE_OWNERSHIP: dict[str, str] = {
    "attributedTo": CASE_OWNER_ID,
    "published": CASE_PUBLISHED,
}
