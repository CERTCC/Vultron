#!/usr/bin/env python

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

"""``vultron-shadow``: start the case shadow tool's dashboard.

Runs :mod:`~vultron.shadow.dashboard.app` under ``streamlit run`` with the
settings the tool needs whatever the host's Streamlit configuration says:
headless, no file watcher, no usage statistics and no welcome message.  The
usage statistics are a request to a host that is neither the configured
outside system nor a Vultron node (SHD-01-001), and so is the welcome
message: a headless start prints an "External URL" it looks up at
``checkip.amazonaws.com``.  The browser address is pinned to loopback, the
only address the page is published on.

The page listens on ``127.0.0.1`` unless told otherwise.  The Compose
service listens on every interface inside its container and publishes the
port on the host's loopback only (SHD-02-002).

The run holds what it reads in memory, and its transient files in a
private temporary directory removed when the run ends
(:func:`~vultron.shadow.dashboard.lifecycle.private_tempdir`), so a case
it read is left nowhere on the host after it exits (SHD-01-003).

Its log records go to standard error, and carry case, activity and actor
ids, never case content (:func:`~vultron.shadow.log_content.shadow_logging`,
VSD-01-003).  Streamlit's rich traceback printer is turned off: it prints an
uncaught exception straight to the console, past any logging.
"""

from __future__ import annotations

import logging

import click
from streamlit.web import cli as streamlit_cli

from vultron.shadow.dashboard.app import APP_PATH
from vultron.shadow.dashboard.lifecycle import private_tempdir
from vultron.shadow.log_content import shadow_logging

#: The port the page listens on by default.
DEFAULT_PORT = 8501

#: The log levels ``--log-level`` takes.
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def streamlit_args(address: str, port: int) -> list[str]:
    """The ``streamlit`` command line that runs the page."""
    return [
        "run",
        str(APP_PATH),
        "--server.address",
        address,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
        "--browser.serverAddress",
        "127.0.0.1",
        "--logger.hideWelcomeMessage",
        "true",
        "--logger.enableRich",
        "false",
        "--global.developmentMode",
        "false",
    ]


@click.command()
@click.option(
    "--address",
    default="127.0.0.1",
    show_default=True,
    help="The interface the page listens on.",
)
@click.option(
    "--port",
    default=DEFAULT_PORT,
    show_default=True,
    type=click.IntRange(1, 65535),
    help="The port the page listens on.",
)
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    type=click.Choice(LOG_LEVELS, case_sensitive=False),
    help="The lowest level of the tool's own log records to write.",
)
def main(address: str, port: int, log_level: str) -> None:
    """Start the case shadow tool's dashboard."""
    # Every log record is cleaned of case content (VSD-01-003), and any
    # transient file the run writes goes in a directory removed when the
    # run ends, by return, error or SIGTERM (SHD-01-003).
    level = logging.getLevelNamesMapping()[log_level.upper()]
    with shadow_logging(level), private_tempdir():
        streamlit_cli.main(
            args=streamlit_args(address, port), prog_name="streamlit"
        )


__all__ = ["DEFAULT_PORT", "LOG_LEVELS", "main", "streamlit_args"]
