"""The ``seed`` sub-command, which bootstraps actor records (D5-1-G2)."""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging

import click

from vultron.demo.cli.group import main
from vultron.demo.seed_config import SeedConfig
from vultron.demo.utils import BASE_URL, DataLayerClient, seed_actor, seed_peer

# ---------------------------------------------------------------------------
# Seed sub-command — bootstrap actor records (D5-1-G2)
# ---------------------------------------------------------------------------


@main.command(name="seed")
@click.option(
    "--config",
    "config_path",
    envvar="VULTRON_SEED_CONFIG",
    default=None,
    metavar="PATH",
    help="Path to a YAML seed config file. Overrides individual options.",
)
@click.option(
    "--actor-name",
    envvar="VULTRON_ACTOR_NAME",
    default=None,
    help="Display name for the local actor (env: VULTRON_ACTOR_NAME).",
)
@click.option(
    "--actor-type",
    envvar="VULTRON_ACTOR_TYPE",
    default=None,
    help="ActivityStreams type for the local actor (env: VULTRON_ACTOR_TYPE).",
)
@click.option(
    "--actor-id",
    envvar="VULTRON_ACTOR_ID",
    default=None,
    help="Full URI for the local actor (env: VULTRON_ACTOR_ID).",
)
@click.option(
    "--api-url",
    envvar="VULTRON_API_BASE_URL",
    default=BASE_URL,
    show_default=True,
    help="Base URL of the Vultron API server (env: VULTRON_API_BASE_URL).",
)
def seed(
    config_path: str | None,
    actor_name: str | None,
    actor_type: str | None,
    actor_id: str | None,
    api_url: str,
) -> None:
    """Bootstrap actor records in the local DataLayer (D5-1-G2).

    Creates the local actor and any configured peer actors in the DataLayer
    via ``POST /actors/``.  Safe to re-run: existing records are returned
    unchanged (idempotent).

    Configuration is loaded from (in decreasing priority):

    \b
    1. A YAML config file (``--config`` / ``VULTRON_SEED_CONFIG``).
    2. Individual CLI options / environment variables.
    """
    logger = logging.getLogger(__package__)

    cfg = SeedConfig.load(
        config_path=config_path,
        actor_name=actor_name,
        actor_type=actor_type,
        actor_id=actor_id,
    )

    client = DataLayerClient(base_url=api_url)

    # Create local actor.
    local = cfg.local_actor
    click.echo(f"🌱 Seeding local actor: {local.name!r} ({local.actor_type})")
    actor = seed_actor(
        client=client,
        name=local.name,
        actor_type=local.actor_type,
        actor_id=local.id_,
    )
    click.echo(f"   → {actor.id_}")
    logger.info("Local actor seeded: %s", actor.id_)

    # Register peer actors as address-book entries in the local actor's store.
    for peer in cfg.peers:
        click.echo(f"🌱 Registering peer: {peer.name!r} ({peer.actor_type})")
        peer_actor = seed_peer(
            client=client,
            local_actor_id=actor.id_,
            peer_id=peer.id_,
            name=peer.name,
            actor_type=peer.actor_type,
        )
        click.echo(f"   → {peer_actor.id_}")
        logger.info("Peer registered: %s", peer_actor.id_)

    click.echo("✅ Seed complete.")
