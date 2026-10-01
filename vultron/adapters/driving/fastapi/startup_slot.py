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

"""A holder for a process-wide default that startup installs after import.

The inbox dispatcher and the outbox's default emitter are both built during
application startup, long after their modules are imported. Each module owns
one :class:`StartupSlot` and installs into it, so the value is changed by
mutating the slot rather than by rebinding a module global (ruff ``PLW0603``,
#3985). Tests swap the value with
``monkeypatch.setattr(slot, "value", replacement)``.
"""


class StartupSlot[T]:
    """Hold one value installed at startup; ``None`` until installed.

    Attributes:
        value: The installed value, or ``None`` when nothing has been
            installed yet (or a test has cleared it).
    """

    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value: T | None = None

    def install(self, value: T) -> None:
        """Replace the held value with *value*."""
        self.value = value

    def clear(self) -> None:
        """Forget the held value, as before anything was installed."""
        self.value = None
