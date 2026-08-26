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

"""Narrow outbound port for use cases and BT nodes that enqueue outbound activities.

:class:`CaseOutboxPersistence` extends :class:`CasePersistence` for the small
number of use cases and BT nodes that also call ``outbox_append``.  Declaring
``CaseOutboxPersistence`` on a ``Received`` use case is an architectural smell —
it signals that the handler mixes inbound processing with outbound broadcast.

``SqliteDataLayer`` satisfies this Protocol structurally with no declaration
needed (Python structural subtyping).

See also:
    - ``specs/datalayer.yaml`` DL-03-001, DL-03-002
    - ``vultron/core/ports/case_persistence.py`` for the base :class:`CasePersistence` port
    - GitHub issue #403
"""

from typing import Protocol

from vultron.core.ports.case_persistence import CasePersistence


class CaseOutboxPersistence(CasePersistence, Protocol):
    """CasePersistence extended for use cases that enqueue outbound activities.

    Only use cases and BT nodes that call ``outbox_append`` declare this type.
    If a ``ReceivedUseCase`` declares ``CaseOutboxPersistence``, that is a
    signal that it mixes received-message handling with outbound broadcast — an
    architectural smell worth investigating.

    The explicit-actor forms ``record_outbox_item(actor_id, activity_id)`` and
    ``outbox_list_for_actor(actor_id)`` are gone. They existed so that an
    *unscoped* DataLayer could name the actor whose queue to touch; every call
    site passed the executing actor's own id, so with a mandatory actor scope
    they are exactly ``outbox_append`` and ``outbox_list`` (ADR-0073).

    ``SqliteDataLayer`` satisfies this Protocol structurally — no declaration
    needed.
    """

    def outbox_append(self, activity_id: str) -> None: ...

    def outbox_list(self) -> list[str]: ...
