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
"""One seam for the ``gh`` CLI, shared by the planning scripts.

The scripts that read or write GitHub (``theme-labels``, ``theme-fit``) take a
:data:`Runner` so their tests fake ``gh`` instead of reaching the network;
:func:`run_gh` is the real runner they default to.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

DEFAULT_REPO = "CERTCC/Vultron"
"""The repository the planning scripts read when ``--repo`` is not given."""

Runner = Callable[[Sequence[str]], str]
"""Runs a ``gh`` argument list and returns its standard output.

Raises :class:`GhError` or ``subprocess.CalledProcessError`` on failure.
"""


class GhError(Exception):
    """``gh`` could not be run, or its output could not be read."""


GH_FAILURES = (GhError, subprocess.CalledProcessError)
"""The exceptions a :data:`Runner` call, or reading its output, may raise."""


def run_gh(args: Sequence[str]) -> str:
    """Run ``gh`` and return its standard output.

    Raises:
        GhError: If ``gh`` is not installed.
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    try:
        return subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True
        ).stdout
    except FileNotFoundError as exc:
        raise GhError("gh is not installed or not on PATH") from exc


def gh_failure_detail(exc: GhError | subprocess.CalledProcessError) -> str:
    """The text to show for a ``gh`` failure: its stderr when it has one."""
    if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
        return str(exc.stderr).strip()
    return str(exc)
