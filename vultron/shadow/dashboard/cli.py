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
"""

from __future__ import annotations

import click
from streamlit.web import cli as streamlit_cli

from vultron.shadow.dashboard.app import APP_PATH

#: The port the page listens on by default.
DEFAULT_PORT = 8501


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
def main(address: str, port: int) -> None:
    """Start the case shadow tool's dashboard."""
    streamlit_cli.main(
        args=streamlit_args(address, port), prog_name="streamlit"
    )


__all__ = ["DEFAULT_PORT", "main", "streamlit_args"]
