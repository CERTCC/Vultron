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

"""LedgerFanout log-replication helpers for demo workflows.

Provides :func:`verify_replica_state` to assert that a replica actor's case
state matches the authoritative actor, and the two shared
scenario-phase helpers of DEMOMA-23: :func:`wait_for_replica_ledger_coverage`
(the read-authority-tail-then-poll-each-replica loop, DEMOMA-23-005) and
:func:`run_sync_verification_phase` (the whole replica sync-verification
phase, DEMOMA-23-007). A scenario module never calls
``wait_for_contiguous_ledger_coverage`` or ``_get_log_entries_for_case``
itself (DEMOMA-23-006).

Submodules
----------
- :mod:`.ledger` — reading the authority's ledger tail and waiting for each
  replica to cover it (DEMOMA-23-005).
- :mod:`.replica` — :func:`verify_replica_state`.
- :mod:`.phase` — :func:`run_sync_verification_phase` (DEMOMA-23-007).
"""

from vultron.demo.helpers.sync.ledger import (
    ReplicaSpec,
    wait_for_replica_ledger_coverage,
    wait_for_replica_ledger_ending_at,
)
from vultron.demo.helpers.sync.phase import (
    run_sync_verification_phase,
)
from vultron.demo.helpers.sync.replica import (
    verify_replica_state,
)

__all__ = [
    "ReplicaSpec",
    "run_sync_verification_phase",
    "verify_replica_state",
    "wait_for_replica_ledger_coverage",
    "wait_for_replica_ledger_ending_at",
]
