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
"""The manifest every dump attempt writes, and the pre-run sentinel.

(:mod:`vultron.demo.helpers.ledger_dump`, ISSUE-2239, DEMOCI-10-006.)
"""

import json
import logging
import pathlib

from vultron.demo.helpers.ledger_dump.layout import (
    DUMP_MANIFEST_FILENAME,
    LedgerDumpReport,
    resolve_output_root,
)

logger = logging.getLogger(__name__)


def write_dump_manifest(
    report: LedgerDumpReport,
    output_root: pathlib.Path | None = None,
) -> pathlib.Path:
    """Write *report* to ``{output_root}/{demo_name}/dump-manifest.json``.

    Called on every dump attempt — including the degenerate attempt made when a
    scenario failed before it had a case — so the case-log artifact is never
    empty (DEMOCI-10-001).

    Args:
        report: The dump outcome to record.
        output_root: Devlogs root; defaults to ``DEVLOGS_DIR``.

    Returns:
        Path to the manifest that was written.
    """
    out_dir = resolve_output_root(output_root) / report.demo_name
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / DUMP_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(report.as_manifest(), indent=2) + "\n", encoding="utf-8"
    )
    logger.info(
        "Wrote dump manifest → %s (%s)", manifest_path, report.summary()
    )
    return manifest_path


def ensure_dump_manifest(
    demo_name: str,
    reason: str,
    output_root: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """Write a fallback manifest for *demo_name* only if none exists yet.

    Backstop for a dump that died before :func:`dump_case_ledgers` could write
    its own manifest. Guarantees the case-log artifact is non-empty whatever
    happened during the run.

    Args:
        demo_name: Scenario name; the devlogs sub-directory to check.
        reason: Explanation recorded when a fallback manifest is written.
        output_root: Devlogs root; defaults to ``DEVLOGS_DIR``.

    Returns:
        Path to the manifest written, or ``None`` if one already existed.
    """
    root = resolve_output_root(output_root)
    if (root / demo_name / DUMP_MANIFEST_FILENAME).exists():
        return None
    return write_dump_manifest(
        LedgerDumpReport(demo_name=demo_name, reason=reason), output_root=root
    )


_PRERUN_SENTINEL_REASON = "Pre-run sentinel: demo-runner had not yet started."
"""Reason string written by :func:`write_prerun_sentinel`.

Kept as a module constant so tests and the CI sentinel step can replicate the
exact value without importing this module (DEMOCI-10-006).
"""


def write_prerun_sentinel(
    demo_name: str,
    output_root: pathlib.Path | None = None,
) -> pathlib.Path:
    """Write a pre-run sentinel manifest for *demo_name*.

    Called immediately before the demo-runner container starts so the case-log
    artifact is non-empty even when the runner exits before
    ``scenario_harness()`` is entered (DEMOCI-10-006).

    When the demo-runner subsequently reaches ``scenario_harness()``, the
    harness overwrites this sentinel with the real dump manifest.  When the
    runner exits early — container startup failure, import error, or
    health-check gate — the sentinel survives and ``load_devlogs()`` reports a
    real failure instead of a plumbing error.

    Args:
        demo_name: Scenario name; the devlogs sub-directory to create.
        output_root: Devlogs root; defaults to ``DEVLOGS_DIR``.

    Returns:
        Path to the sentinel manifest written.
    """
    return write_dump_manifest(
        LedgerDumpReport(
            demo_name=demo_name,
            reason=_PRERUN_SENTINEL_REASON,
        ),
        output_root=output_root,
    )
