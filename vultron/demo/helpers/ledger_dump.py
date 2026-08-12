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
uploaded ``*-case-logs`` artifact, so the dump is the *only* forensic record a
failed demo leaves behind.

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
"""

import json
import logging
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

import httpx2 as httpx

from vultron.adapters.utils import strip_id_prefix
from vultron.demo.utils import DataLayerClient, demo_step
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

DUMP_MANIFEST_FILENAME = "dump-manifest.json"
"""Name of the per-scenario manifest written on every dump attempt."""

DEFAULT_OUTPUT_ROOT = "/app/devlogs"
"""Fallback devlogs root used when ``DEVLOGS_DIR`` is unset."""

LEDGER_FILE_SUFFIX = "-case-ledger.jsonl"


@dataclass(frozen=True)
class LedgerDumpTarget:
    """One actor whose case-ledger view should be exported.

    Args:
        actor_name: Output sub-directory name, e.g. ``"vendor2"``. This is the
            name the invariant harness uses to identify the replica.
        client: DataLayerClient for the container that holds the ledger.
        route_key: In-container actor route key used to build the log path.
        fallback_client: Optional second container to try when *client* returns
            404 or an empty ledger.
        fallback_route_key: Route key to use with *fallback_client*.
    """

    actor_name: str
    client: DataLayerClient
    route_key: str
    fallback_client: DataLayerClient | None = None
    fallback_route_key: str | None = None


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
        }


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
    return pathlib.Path(os.environ.get("DEVLOGS_DIR", DEFAULT_OUTPUT_ROOT))


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


def resolve_case_actor_route_key(case: as_VulnerabilityCase) -> str | None:
    """Return the in-container route key of the case's case-actor, if any.

    The case-actor is a sub-actor created inside whichever container owns the
    case; its route key is discoverable only from the case's participant index.

    Args:
        case: The case whose participants are scanned.

    Returns:
        The case-actor's route key, or ``None`` when the case has no case-actor
        participant.
    """
    return next(
        (
            strip_id_prefix(actor_id)
            for actor_id in case.actor_participant_index
            if strip_id_prefix(actor_id).startswith("case-actor")
        ),
        None,
    )


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


def _fetch_entries(
    client: DataLayerClient, log_path: str, actor_name: str
) -> list[dict[str, Any]]:
    """Fetch ledger entries, treating a 404 as an empty ledger.

    A 404 means the container does not hold this case at all, which is a
    legitimate outcome for a dedicated case-actor container (see the fallback in
    :func:`dump_case_ledgers`) and for a scenario that never delivered the case
    to that participant. Any other HTTP error is a real failure and propagates.

    Args:
        client: Container client to read from.
        log_path: Case-log route on that container.
        actor_name: Actor name, for logging.

    Returns:
        The ledger entries, or an empty list on 404.
    """
    try:
        return client.get_list(log_path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        logger.info(
            "Case not found on %s container (HTTP 404); treating as empty.",
            actor_name,
        )
        return []


def _write_ledger_file(
    entries: list[dict[str, Any]],
    out_dir: pathlib.Path,
    slug: str,
) -> pathlib.Path:
    """Write *entries* as JSONL and return the path written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{slug}{LEDGER_FILE_SUFFIX}"
    with out_file.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    logger.info("Wrote %d log entries → %s", len(entries), out_file)
    return out_file


def dump_case_ledgers(
    demo_name: str,
    case: as_VulnerabilityCase,
    targets: list[LedgerDumpTarget],
    output_root: pathlib.Path | None = None,
) -> LedgerDumpReport:
    """Export every target's case-ledger view, then write the dump manifest.

    Each target's export runs inside ``demo_step``, so a failure is accumulated
    and reported by ``assert_demo_success()`` without preventing the remaining
    targets — or the manifest — from being written.

    Args:
        demo_name: Scenario name; becomes the devlogs sub-directory.
        case: The case whose ledgers are exported.
        targets: Actors to export, in output order.
        output_root: Devlogs root; defaults to ``DEVLOGS_DIR``.

    Returns:
        The dump report, also persisted as the manifest.
    """
    logger.info("─" * 80)
    logger.info("Phase: Case log JSONL export")
    logger.info("─" * 80)

    root = resolve_output_root(output_root)
    case_id = case.id_ or ""
    slug = case_id_slug(case_id)
    case_key = strip_id_prefix(case_id)

    report = LedgerDumpReport(demo_name=demo_name, case_id=case_id or None)
    try:
        for target in targets:
            record = ActorLedgerRecord(
                actor_name=target.actor_name, route_key=target.route_key
            )
            report.records.append(record)
            with demo_step(f"Dumping case ledger for {target.actor_name}"):
                # Record why a dump failed before demo_step swallows the
                # exception, so the manifest explains every missing ledger.
                try:
                    _dump_one_target(
                        target=target,
                        record=record,
                        case_key=case_key,
                        case_id=case_id,
                        out_dir=root / demo_name / target.actor_name,
                        slug=slug,
                    )
                except Exception as exc:
                    record.reason = f"{type(exc).__name__}: {exc}"
                    raise
    finally:
        write_dump_manifest(report, output_root=root)

    return report


def _dump_one_target(
    target: LedgerDumpTarget,
    record: ActorLedgerRecord,
    case_key: str,
    case_id: str,
    out_dir: pathlib.Path,
    slug: str,
) -> None:
    """Export one target's ledger and update *record* in place.

    Raises:
        ValueError: When the container returned no ledger entries. This is a
            real invariant failure — a participant of the case should have a
            ledger — so it is reported rather than silently tolerated.
    """
    entries = _fetch_entries(
        target.client,
        f"/actors/{target.route_key}/demo/cases/{case_key}/log",
        target.actor_name,
    )
    if not entries and target.fallback_client is not None:
        logger.info(
            "Primary %s log unavailable; falling back to route key '%s'",
            target.actor_name,
            target.fallback_route_key,
        )
        entries = _fetch_entries(
            target.fallback_client,
            f"/actors/{target.fallback_route_key}/demo/cases/{case_key}/log",
            target.actor_name,
        )
    if not entries:
        raise ValueError(
            f"No case ledger entries for actor={target.actor_name!r}, "
            f"case_id={case_id!r}"
        )

    out_file = _write_ledger_file(entries, out_dir, slug)
    record.captured = True
    record.entry_count = len(entries)
    record.ledger_file = f"{target.actor_name}/{out_file.name}"
