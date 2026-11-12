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
"""A cache on disk, kept across processes, of what a reader made of a text.

For a reader whose result depends only on a text and on the reader's own
code, and whose cost every process that reads an unchanged tree pays again:
the spec-marker reader parses about 900 test files, about 8 s of CPU, in every
pytest worker and every ``spec-lint`` run, which a loaded host turns into a
timeout (#5880).

An entry is keyed by the SHA-256 of the text, under a *version* that names the
reader's code. An edited text gets a new key and is read again; an edited
reader gets a new version and reads every text again. So an entry is never
stale, and the cache needs no invalidation. Entries are small and the whole
directory may be deleted at any time.

The cache is an optimization only. An entry that cannot be read or decoded is
a miss, and a write that fails is skipped (DEBUG log), so an unwritable home
directory costs the read, never a wrong answer. A write is atomic (a temporary
file, then :func:`os.replace`), so concurrent workers never see a partial
entry.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Environment variable naming the cache root, for tests and for CI.
CACHE_DIR_ENV = "VULTRON_CACHE_DIR"


def cache_root() -> Path:
    """The directory every namespace's entries live under.

    ``$VULTRON_CACHE_DIR`` when set, else ``vultron`` under
    ``$XDG_CACHE_HOME`` (default ``~/.cache``). It is shared by every
    worktree on the host, which is the point: an entry is keyed by content,
    so a tree read in one worktree is free in the next.
    """
    if explicit := os.environ.get(CACHE_DIR_ENV):
        return Path(explicit)
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "vultron"


def code_version(*sources: Path) -> str:
    """A version string for a reader made of the modules *sources*.

    The SHA-256 of the files' bytes and the running Python's major and minor
    version, whose grammar the reader's ``ast.parse`` follows.
    """
    digest = hashlib.sha256(f"{sys.version_info[:2]}".encode())
    for source in sources:
        digest.update(source.read_bytes())
    return digest.hexdigest()[:16]


def _entry(namespace: str, version: str, text: str) -> Path:
    key = hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()
    return cache_root() / namespace / version / key[:2] / key


def _write(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(temp, path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
    except OSError as error:
        logger.debug("text cache: not writing %s: %s", path, error)


def cached_read(
    namespace: str,
    version: str,
    text: str,
    read: Callable[[str], T],
    *,
    encode: Callable[[T], str],
    decode: Callable[[str], T],
) -> T:
    """``read(text)``, kept on disk across processes.

    Args:
        namespace: The reader's directory under :func:`cache_root`.
        version: The reader's :func:`code_version`; it also names the
            encoding, since the reader's module holds *encode* and *decode*.
        text: The input whose content keys the entry.
        read: The reader.
        encode: Turns a result into the entry's text.
        decode: Turns an entry's text back into the result; a
            ``ValueError``, ``KeyError`` or ``TypeError`` it raises makes the
            entry a miss.

    Raises:
        Whatever *read* raises; nothing is written for it, so a fault is
        raised again on the next call.
    """
    try:
        path = _entry(namespace, version, text)
    except RuntimeError as error:
        # Path.home() finds no home directory: no cache, the read still runs.
        logger.debug("text cache: no cache root: %s", error)
        return read(text)
    try:
        return decode(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    result = read(text)
    _write(path, encode(result))
    return result
