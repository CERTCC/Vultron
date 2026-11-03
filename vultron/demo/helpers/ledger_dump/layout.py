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
"""Where a ledger dump goes and what it records.

The dump's file names, its target, record and report types, and the
devlogs root and case-id slug its paths are built from
(:mod:`vultron.demo.helpers.ledger_dump`).
"""

import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

from vultron.demo.utils import DataLayerClient

DUMP_MANIFEST_FILENAME = "dump-manifest.json"
"""Name of the per-scenario manifest written on every dump attempt."""

STEP_MARKS_FILENAME = "step-marks.json"
"""Name of the per-scenario file recording where each declared step fell in
the canonical ledger (written by the scenario harness, DEMOCI-11-017)."""

#: Repo root, used to resolve the default ``devlogs/`` directory. This module
#: lives at ``vultron/demo/helpers/ledger_dump/layout.py`` → ``parents[4]`` is the
#: repository root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

LEDGER_FILE_SUFFIX = "-case-ledger.jsonl"


@dataclass(frozen=True)
class LedgerDumpTarget:
    """One actor whose case-ledger view should be exported.

    Args:
        actor_name: Output sub-directory name, e.g. ``"vendor2"``. This is the
            name the invariant harness uses to identify the replica.
        client: DataLayerClient for the container that holds the ledger.
        route_key: In-container actor route key used to build the log path.
    """

    actor_name: str
    client: DataLayerClient
    route_key: str


@dataclass
class ActorLedgerRecord:
    """Outcome of one actor's dump attempt, as recorded in the manifest."""

    actor_name: str
    route_key: str
    captured: bool = False
    entry_count: int = 0
    ledger_file: str | None = None
    reason: str | None = None

    def as_manifest_entry(self) -> dict[str, Any]:
        """Return the JSON-serializable manifest form of this record."""
        return {
            "actorName": self.actor_name,
            "routeKey": self.route_key,
            "captured": self.captured,
            "entryCount": self.entry_count,
            "ledgerFile": self.ledger_file,
            "reason": self.reason,
        }


@dataclass
class LedgerDumpReport:
    """Aggregate result of a scenario's ledger dump."""

    demo_name: str
    case_id: str | None = None
    records: list[ActorLedgerRecord] = field(default_factory=list)
    reason: str | None = None
    """Explicit summary; overrides the one derived from *records*."""
    unreplicated: dict[str, str] = field(default_factory=dict)
    """``{actorName: routeKey}`` of actors that acted in the case but hold no
    ledger replica to dump (e.g. an invitee that rejected). Recorded so the
    invariant harness can resolve them as the recorded actor of an entry."""

    @property
    def ledger_file_count(self) -> int:
        """Number of actors whose ledger was written to disk."""
        return sum(1 for record in self.records if record.captured)

    def summary(self) -> str:
        """Return a one-line human-readable explanation of the outcome."""
        if self.reason:
            return self.reason
        if not self.records:
            return (
                "No dump targets: the scenario failed before a case existed, "
                "so there were no participant ledgers to export."
            )
        missing = [r.actor_name for r in self.records if not r.captured]
        if not missing:
            return (
                f"Captured case ledgers for all {len(self.records)} "
                "participants."
            )
        return (
            f"Captured {self.ledger_file_count} of {len(self.records)} "
            f"participant case ledgers; missing: {', '.join(missing)}."
        )

    def as_manifest(self) -> dict[str, Any]:
        """Return the JSON-serializable manifest for this report."""
        return {
            "demoName": self.demo_name,
            "caseId": self.case_id,
            "ledgerFileCount": self.ledger_file_count,
            "targetCount": len(self.records),
            "reason": self.summary(),
            "actors": [record.as_manifest_entry() for record in self.records],
            "unreplicatedActors": [
                {"actorName": name, "routeKey": route_key}
                for name, route_key in self.unreplicated.items()
            ],
        }


def default_devlogs_root() -> pathlib.Path:
    """Return ``DEVLOGS_DIR`` when set, else ``<repo root>/devlogs``.

    The single resolution of the devlogs root for the whole project;
    :func:`vultron.demo.report.default_input_dir` and the invariant harness
    both delegate here so a writer and a reader can never disagree about where
    the ledgers live (DEMOMA-17-001).

    The default must not be a container path. ``docker-compose-multi-actor.yml``
    sets ``DEVLOGS_DIR=/app/devlogs`` explicitly for the demo runner, so the
    fallback only ever fires *outside* the container — on a CI runner or a
    developer checkout, where ``/app`` cannot be created and ``mkdir`` raises
    ``PermissionError`` (ISSUE-2239).

    An empty ``DEVLOGS_DIR`` counts as unset; ``pathlib.Path("")`` is the
    current directory, which is never what an empty env var means.

    Returns:
        The directory under which per-scenario dump sub-directories live.
    """
    env = os.environ.get("DEVLOGS_DIR")
    if env:
        return pathlib.Path(env)
    return _REPO_ROOT / "devlogs"


def resolve_output_root(
    output_root: pathlib.Path | None = None,
) -> pathlib.Path:
    """Return the devlogs root, honouring the ``DEVLOGS_DIR`` environment var.

    Args:
        output_root: Explicit root; when given it is returned unchanged.

    Returns:
        The directory under which per-scenario dump sub-directories live.
    """
    if output_root is not None:
        return output_root
    return default_devlogs_root()


def case_id_slug(case_id: str) -> str:
    """Convert a case URI into a filesystem-safe slug.

    Args:
        case_id: The case's ``id_`` URI, e.g. ``https://example.org/cases/x``.

    Returns:
        The slug used in ledger file names, e.g. ``example.org_cases_x``.
    """
    return (
        case_id.replace("://", "_")
        .replace("/", "_")
        .replace(":", "_")
        .strip("_")
    )
