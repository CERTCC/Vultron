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

import logging
import os
import shutil
import signal
import tempfile
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType

#: The name every private temporary directory starts with.
TEMPDIR_PREFIX = "vultron-shadow-"

_TMPDIR = "TMPDIR"

logger = logging.getLogger(__name__)

#: A thread's set of blocked signals, as :func:`signal.pthread_sigmask` gives it.
_Mask = set[int | signal.Signals]


def _exit_on_sigterm(signal_number: int, _frame: FrameType | None) -> None:
    """Turn ``SIGTERM`` into ``SystemExit``, so cleanup code runs."""
    raise SystemExit(128 + signal_number)


def _on_main_thread() -> bool:
    """Whether a signal handler can be set from here: only the main thread."""
    return threading.current_thread() is threading.main_thread()


@contextmanager
def _sigterm_exits() -> Generator[None]:
    """Stop the process on ``SIGTERM`` by unwinding it, not by killing it.

    Python's default ``SIGTERM`` ends the process with no ``finally``
    block run.  Streamlit replaces this handler with its own once its
    server starts; that one stops the server, and the run then returns.
    A handler can only be set from the main thread; elsewhere this does
    nothing.
    """
    if not _on_main_thread():
        yield
        return
    previous = signal.signal(signal.SIGTERM, _exit_on_sigterm)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _hold_sigterm() -> _Mask | None:
    """Block ``SIGTERM`` and return the mask it replaced.

    A blocked signal is not lost: it is delivered once the mask is set
    back.  Off the main thread no handler is set, so nothing is blocked
    and ``None`` is returned.
    """
    if not _on_main_thread():
        return None
    return signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})


def _set_mask(mask: _Mask | None) -> None:
    """Put back a mask :func:`_hold_sigterm` returned."""
    if mask is not None:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)


@contextmanager
def _sigterm_delivered(mask: _Mask | None) -> Generator[None]:
    """Let ``SIGTERM`` through for the block, then hold it again."""
    _set_mask(mask)
    try:
        yield
    finally:
        _hold_sigterm()


def _log_unremoved(
    _function: Callable[..., object], path: str, error: BaseException
) -> None:
    logger.warning(
        "Could not remove %s from the case shadow tool's temporary"
        " directory: %s",
        path,
        error,
    )


def _remove(path: Path) -> None:
    """Remove *path* and all it holds; log each part that stays."""
    shutil.rmtree(path, onexc=_log_unremoved)


@contextmanager
def private_tempdir() -> Generator[Path]:
    """A temporary directory for the run's transient files, removed after.

    For the length of the ``with`` block, :mod:`tempfile` and any child
    process (through ``TMPDIR``) put temporary files in the new directory.
    When the block ends, by return, exception or ``SIGTERM``, the
    directory and everything in it is removed, and the previous temporary
    directory is restored.

    ``SIGTERM`` is held from before the directory is made until it is
    removed, except while the block runs.  So a ``SIGTERM`` that comes
    while the directory is set up or removed waits, and cannot stop the
    run between making the directory and removing it.
    """
    saved_env = os.environ.get(_TMPDIR)
    saved_tempdir = tempfile.tempdir
    with _sigterm_exits():
        mask = _hold_sigterm()
        try:
            private = Path(tempfile.mkdtemp(prefix=TEMPDIR_PREFIX))
            try:
                os.environ[_TMPDIR] = str(private)
                tempfile.tempdir = str(private)
                with _sigterm_delivered(mask):
                    yield private
            finally:
                # A SIGTERM delivered as the block began finds it unheld.
                _hold_sigterm()
                tempfile.tempdir = saved_tempdir
                if saved_env is None:
                    os.environ.pop(_TMPDIR, None)
                else:
                    os.environ[_TMPDIR] = saved_env
                _remove(private)
        finally:
            _set_mask(mask)


__all__ = ["TEMPDIR_PREFIX", "private_tempdir"]
