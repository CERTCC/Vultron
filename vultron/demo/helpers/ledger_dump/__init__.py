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

"""Shared case-ledger dump for demo scenarios.

Every scenario exports each participant's view of the case ledger to
``{DEVLOGS_DIR}/{demo_name}/{actor_name}/{case_id_slug}-case-ledger.jsonl``.
The invariant harness (``test/ci/invariants/``) reads those files from the
uploaded ``*-case-logs-attempt-*`` artifact, so the dump is the *only*
forensic record a failed demo leaves behind.

Two rules follow from that, and this module exists to hold them in one place
rather than in nine near-identical scenario functions (DEMOMA-17-001):

1. **The dump always writes a manifest.** ``DUMP_MANIFEST_FILENAME`` records
   which actors were captured and why the others were not, so
   ``{DEVLOGS_DIR}/{demo_name}/`` exists even when the scenario died before it
   had a case. The artifact upload then always has something to upload, and the
   invariant harness reports a real invariant result instead of failing on
   artifact download (ISSUE-2239, DEMOCI-10-001).

2. **A per-actor dump failure is recorded, not raised.** Each actor's dump runs
   inside ``demo_step``, which accumulates the failure and continues
   (DEMOCI-01-003), so one unreachable container cannot cost us the other
   containers' ledgers.

The scenario-facing entry point is :func:`dump_case_ledgers`; the harness in
:mod:`vultron.demo.harness` calls :func:`write_dump_manifest` directly when a
scenario failed before a case existed.

The package is split by concern (CS-18-005): :mod:`.layout` holds the dump's
paths and record types, :mod:`.manifest` the manifest and the pre-run
sentinel, and :mod:`.dump` the fetch and the write.  Every public name is
re-exported here (CS-18-003).
"""

from vultron.demo.helpers.ledger_dump.dump import (
    case_actor_dump_target,
    case_ledger_length,
    dump_case_ledgers,
    replica_route_key,
)
from vultron.demo.helpers.ledger_dump.layout import (
    DUMP_MANIFEST_FILENAME,
    LEDGER_FILE_SUFFIX,
    STEP_MARKS_FILENAME,
    ActorLedgerRecord,
    LedgerDumpReport,
    LedgerDumpTarget,
    case_id_slug,
    default_devlogs_root,
    resolve_output_root,
)
from vultron.demo.helpers.ledger_dump.manifest import (
    ensure_dump_manifest,
    write_dump_manifest,
    write_prerun_sentinel,
)

__all__ = [
    "ActorLedgerRecord",
    "DUMP_MANIFEST_FILENAME",
    "LEDGER_FILE_SUFFIX",
    "LedgerDumpReport",
    "LedgerDumpTarget",
    "STEP_MARKS_FILENAME",
    "case_actor_dump_target",
    "case_id_slug",
    "case_ledger_length",
    "default_devlogs_root",
    "dump_case_ledgers",
    "ensure_dump_manifest",
    "replica_route_key",
    "resolve_output_root",
    "write_dump_manifest",
    "write_prerun_sentinel",
]
