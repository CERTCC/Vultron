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

"""The consent row as an AS2 object (ADR-0122, CLP-07-009).

A row of the consent table is the object of the CASE_MANAGER's
``Create(EmbargoConsent)`` and ``Update(EmbargoConsent)`` ledger entries.  The
core class is the wire class (ADR-0099); registering it lets the parser and
the canonical-entry check revalidate a carried row by its ``type``.
"""

from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# Backward-compatibility-style alias for the wire name (ARCH-25-003, ADR-0099)
as_EmbargoConsent = EmbargoConsent

WIRE_TYPE_MAP["EmbargoConsent"] = EmbargoConsent

__all__ = ["as_EmbargoConsent"]
