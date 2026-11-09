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
"""Fetch each target's case ledger and write it to the devlogs.

The route key and target of each replica, then :func:`dump_case_ledgers`,
which fetches and writes every target's ledger and always writes the
manifest (:mod:`vultron.demo.helpers.ledger_dump`).
"""

import json
import logging
import pathlib
from typing import Any

import httpx2 as httpx

from vultron.adapters.utils import strip_id_prefix
from vultron.demo.helpers.cast import cast_member_name, slot_for
from vultron.demo.helpers.ledger_dump.layout import (
    LEDGER_FILE_SUFFIX,
    ActorLedgerRecord,
    LedgerDumpReport,
    LedgerDumpTarget,
    case_id_slug,
    resolve_output_root,
)
from vultron.demo.helpers.ledger_dump.manifest import write_dump_manifest
from vultron.demo.utils import CASE_ACTOR_SLUG, DataLayerClient, demo_step
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def replica_route_key(client: DataLayerClient) -> str:
    """Return the route key naming *client*'s own actor.

    A route key *selects the store* (ADR-0073) rather than decorating a path
    into a store shared by everyone in the container.  A guessed key therefore
    reads whichever actor happens to be hosted under that slug; the moment it
    names the wrong one, the dump reports "No case ledger entries" while the
    real store holds the whole exchange.

    The client already knows: :func:`vultron.demo.helpers.seeding.actors._own_actor`
    binds ``client.actor_id`` as each container's own actor is created, so by
    ledger-dump time every scenario client is bound.  The fallback covers the
    ordering exception — a client built for the pre-seed health check and dumped
    without ever being bound — and is the name of the cast container the URL
    addresses, which is the slug of the one actor that container hosts
    (DEMOCI-11-020).  It is read from the cast rather than from the URL's host
    name, because a local run addresses every container as ``localhost`` on a
    different port.  Guessing beats raising during teardown, when the ledger is
    the only evidence left.

    Args:
        client: The container client whose own actor the dump is about.

    Returns:
        The route key to read the ledger under.
    """
    if not client.actor_id:
        name = cast_member_name(client.base_url)
        if slot_for(client.base_url) is None:
            # Not a cast container, so nothing says which actor it hosts.  The
            # host name is the last guess available, and the WARNING is the
            # only notice the dump will give before it reports an empty ledger.
            logger.warning(
                "ledger dump: client for %s is unbound and addresses no cast"
                " container, so its route key falls back to the host name"
                " %r, which may name no actor (ADR-0073, DEMOCI-11-020)",
                client.base_url,
                name,
            )
        else:
            logger.debug(
                "ledger dump: client for %s is unbound, falling back to the"
                " slug of the actor cast container %r hosts (ADR-0073,"
                " DEMOCI-11-020)",
                client.base_url,
                name,
            )
        return name
    return strip_id_prefix(client.actor_id)


def case_actor_dump_target(
    case_actor_client: DataLayerClient,
) -> LedgerDumpTarget:
    """Return the dump target for the CaseActor's canonical ledger.

    The CaseActor lives in the dedicated case-actor container in every Docker
    scenario (DEMOMA-06-004, CP-08-008), so its ledger is read there and nowhere
    else (DEMOMA-06-009). There is no fallback to a participant's container: a
    participant holds a replica, not the canonical ledger, and dumping that as
    ``case-actor`` would hide exactly the topology fault this target exists to
    expose.

    Args:
        case_actor_client: Client for the dedicated case-actor container, bound
            to its CaseActor.

    Returns:
        The ``case-actor`` target, the name the invariant harness loads.
    """
    return LedgerDumpTarget(
        CASE_ACTOR_SLUG,
        case_actor_client,
        replica_route_key(case_actor_client),
    )


def _fetch_entries(
    client: DataLayerClient, log_path: str, actor_name: str
) -> list[dict[str, Any]]:
    """Fetch ledger entries, treating a 404 as an empty ledger.

    A 404 means the container does not hold this case at all — a scenario that
    never delivered the case to that participant. The caller reports the empty
    ledger as a failed target (:func:`_dump_one_target`); any other HTTP error is
    a real failure and propagates.

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


def case_ledger_length(
    case_actor_client: DataLayerClient, case_id: str
) -> int:
    """Return how many entries the canonical ledger of *case_id* holds now.

    Reads the CaseActor's own ledger, the canonical one (DEMOMA-06-009),
    through the same route :func:`dump_case_ledgers` exports it from.  Unlike
    the dump, a 404 is not read as an empty ledger: the case exists when a
    scenario follows its ledger, so a 404 means the client or the case is
    wrong, and a tail of 0 would mark the step at the wrong place.

    Args:
        case_actor_client: Client for the dedicated case-actor container,
            bound to its CaseActor.
        case_id: The case whose ledger is read.

    Raises:
        httpx.HTTPStatusError: When the container answers with an error,
            a 404 included.
    """
    route_key = replica_route_key(case_actor_client)
    return len(
        case_actor_client.get_list(
            f"/actors/{route_key}/demo/cases/{strip_id_prefix(case_id)}/log"
        )
    )


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
    unreplicated: dict[str, str] | None = None,
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
        unreplicated: ``{actorName: routeKey}`` of actors that acted in the
            case but have no replica to dump; written to the manifest so
            their entries' recorded actor still resolves to a name.

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

    report = LedgerDumpReport(
        demo_name=demo_name,
        case_id=case_id or None,
        unreplicated=dict(unreplicated or {}),
    )
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
    if not entries:
        raise ValueError(
            f"No case ledger entries for actor={target.actor_name!r}, "
            f"case_id={case_id!r}"
        )

    out_file = _write_ledger_file(entries, out_dir, slug)
    record.captured = True
    record.entry_count = len(entries)
    record.ledger_file = f"{target.actor_name}/{out_file.name}"
