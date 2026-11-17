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

"""What the case shadow tool leaves on the host when it exits: nothing.

The tool holds a case it read, and its translation, in memory only
(SHD-01-003, ADR-0190).  :func:`private_tempdir` gives a run's transient
working files one directory of their own, and removes it when the run
ends: when it returns, when it raises, and when it is stopped with
``SIGTERM``.  The Compose service mounts no volume, so the container has
nowhere persistent to write either (SHD-02-001).
"""

from __future__ import annotations

import os
import signal
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType

#: The name every private temporary directory starts with.
TEMPDIR_PREFIX = "vultron-shadow-"

_TMPDIR = "TMPDIR"


def _exit_on_sigterm(signal_number: int, frame: FrameType | None) -> None:
    """Turn ``SIGTERM`` into ``SystemExit``, so cleanup code runs."""
    raise SystemExit(128 + signal_number)


@contextmanager
def _sigterm_exits() -> Iterator[None]:
    """Stop the process on ``SIGTERM`` by unwinding it, not by killing it.

    Python's default ``SIGTERM`` ends the process with no ``finally``
    block run.  Streamlit replaces this handler with its own once its
    server starts; that one stops the server, and the run then returns.
    A handler can only be set from the main thread; elsewhere this does
    nothing.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(signal.SIGTERM, _exit_on_sigterm)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@contextmanager
def private_tempdir() -> Iterator[Path]:
    """A temporary directory for the run's transient files, removed after.

    For the length of the ``with`` block, :mod:`tempfile` and any child
    process (through ``TMPDIR``) put temporary files in the new directory.
    When the block ends, by return, exception or ``SIGTERM``, the
    directory and everything in it is removed, and the previous temporary
    directory is restored.
    """
    saved_env = os.environ.get(_TMPDIR)
    saved_tempdir = tempfile.tempdir
    with (
        _sigterm_exits(),
        tempfile.TemporaryDirectory(prefix=TEMPDIR_PREFIX) as name,
    ):
        os.environ[_TMPDIR] = name
        tempfile.tempdir = name
        try:
            yield Path(name)
        finally:
            tempfile.tempdir = saved_tempdir
            if saved_env is None:
                os.environ.pop(_TMPDIR, None)
            else:
                os.environ[_TMPDIR] = saved_env


__all__ = ["TEMPDIR_PREFIX", "private_tempdir"]
