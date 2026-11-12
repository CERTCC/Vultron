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

"""A process-wide value that a reproducible run replaces for one block.

A scenario recording and the docs-example generator need repeatable ids and
times, so each replaces the source the application draws from, for the
length of one block (ADR-0185, ADR-0176).  :class:`ScopedInstall` is that
replacement, written once: it holds a default, lets one install replace it,
refuses a second install while the first is active, and puts back what it
held when the block ends, also when the block raises.

It lives in the core model helpers, beside its first user (the id source),
because the wire layer's docs-example generator installs through it and the
wire layer may import only ``vultron.core.models`` and ``vultron.core.states``
(ARCH-22-001).
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from vultron.errors import VultronWiringError


@dataclass
class ScopedInstall[T]:
    """Hold *value*, which one :meth:`install` at a time may replace.

    A reader reads :attr:`value` once per use; the lock serializes installs,
    not reads.  A dataclass, so it has no hand-written ``__init__`` for a scan
    that follows methods by name.

    Attributes:
        value: What a reader gets: the default, or the installed value
            inside an :meth:`install` block.
        refusal: Builds the error a nested install raises.  Two
            reproducible runs in one block would share one source, and
            nobody would see it.
    """

    value: T
    refusal: Callable[[], VultronWiringError]
    installed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    @contextmanager
    def install(self, value: T) -> Iterator[T]:
        """Make *value* the held value for the block, then restore it.

        Process-wide: every thread that reads while the block runs reads
        *value*.  Yields *value*, so a caller may bind it with ``as``.

        Raises:
            VultronWiringError: another install is active (the subtype
                :attr:`refusal` builds).
        """
        with self.lock:
            if self.installed:
                raise self.refusal()
            self.installed = True
            previous = self.value
            self.value = value
        try:
            yield value
        finally:
            with self.lock:
                self.value = previous
                self.installed = False


__all__ = ["ScopedInstall"]
