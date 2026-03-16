"""
CLI driving adapter.

Translates command-line invocations into core use-case calls by routing
ActivityStreams JSON through the same parse → rehydrate → extract → dispatch
pipeline used by the HTTP inbox adapter.

Usage:
    python -m vultron.adapters.driving.cli deliver ACTOR_ID [ACTIVITY_JSON]
    vultron-cli deliver ACTOR_ID < activity.json
"""

import json
import logging
import sys

import click

from vultron.adapters.driven.datalayer_tinydb import get_datalayer
from vultron.api.v2.backend.inbox_handler import (
    handle_inbox_item,
    init_dispatcher,
)
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.parser import parse_activity

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Vultron CLI driving adapter — deliver activities directly to use cases."""


@cli.command()
@click.argument("actor_id")
@click.argument("activity_json", type=click.File("r"), default="-")
def deliver(actor_id: str, activity_json) -> None:
    """Deliver an AS2 activity JSON to an actor's inbox.

    Runs the same parse → rehydrate → extract → dispatch pipeline as
    the HTTP inbox adapter, but without going through HTTP.

    ACTOR_ID  The actor receiving the activity.
    ACTIVITY_JSON  Path to a JSON file (or '-' for stdin).
    """
    raw = json.load(activity_json)
    dl = get_datalayer()
    init_dispatcher()

    try:
        activity = parse_activity(raw)
    except Exception as e:
        click.echo(f"Parse error: {e}", err=True)
        sys.exit(1)

    activity = rehydrate(activity)
    handle_inbox_item(actor_id=actor_id, obj=activity, dl=dl)
    click.echo("Activity delivered.")


if __name__ == "__main__":
    cli()
