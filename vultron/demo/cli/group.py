"""The top-level ``vultron-demo`` click group and its logging set-up (DC-01-001)."""

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

from vultron.logging_setup import suppress_third_party_info_noise


@click.group()
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable DEBUG-level logging to the console (default: INFO).",
)
@click.option(
    "--log-file",
    default=None,
    metavar="PATH",
    help="Also write log output to FILE.",
)
@click.pass_context
def main(ctx: click.Context, debug: bool, log_file: str | None) -> None:
    """Vultron demo CLI — run individual demos or all demos in sequence."""
    level = logging.DEBUG if debug else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    suppress_third_party_info_noise(level)
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
