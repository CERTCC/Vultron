"""Protocol-level failure class URI constants for ProcessingFault messages.

These URIs identify failure classes in ``Create(ProcessingFault)`` NACK
messages (ASK-07-005, ADR-0080).  Defined in the core layer so both core
use cases and wire-layer vocab types can reference them without violating
the hexagonal architecture constraint (ARCH-01-001).

All URIs are under the Vultron namespace (ADR-0069).
"""

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

_VULTRON_NS = "https://certcc.github.io/Vultron/ns"

# ASK-07-001, ASK-07-005: receiver refused a status assertion in full;
# no dimension carried new state.
VULTRON_FAILURE_STATUS_ASSERTION_REFUSED = (
    f"{_VULTRON_NS}/errors/StatusAssertionRefused"
)

# RSH-05-021: replica refused a ledger entry because the effective
# composite state violates the RM↔VF, RM↔D, or VF↔D entailments.
VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE = (
    f"{VULTRON_FAILURE_STATUS_ASSERTION_REFUSED}/ImpossibleState"
)
