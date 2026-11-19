"""Typed ``(container, actor, case)`` binding for demo trigger calls.

:class:`ActorSession` is the single API through which demo scenarios and
exchanges invoke trigger endpoints (DEMOMA-26-007).  It replaces the
stringly-typed :func:`vultron.demo.utils.post_to_trigger` at every call site:

- The ``(client, actor)`` pairing is checked **once** at construction rather
  than on every call, so a mismatched pair is unconstructible instead of a
  guard that silently passes in unit tests (DEMOMA-26-008).
- Each trigger verb is a typed method: a misspelled behavior name is now a
  ``AttributeError`` at import/lint time, and a misspelled body key is
  impossible because the method's keyword parameters are fixed (DEMOMA-26-011).
  ``test/architecture/test_actor_session_kwargs_match_request_models.py``
  ratchets those parameters against the trigger request models.
- The case is bound separately with :meth:`with_case`, because a case does not
  exist when the actor is first constructed (DEMOMA-26-003).

``post_to_trigger`` remains the private transport, wrapped by :meth:`_post`;
it MUST NOT be imported anywhere except :mod:`.binding` and
:mod:`vultron.demo.utils` (DEMOMA-26-001).
"""

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

from vultron.demo.actor_session.results import (
    WireActivityResult,
    WireNoteResult,
    WireSyncLogEntryResult,
    WireTriggerResult,
)
from vultron.demo.actor_session.session import ActorSession

__all__ = [
    "ActorSession",
    "WireActivityResult",
    "WireNoteResult",
    "WireSyncLogEntryResult",
    "WireTriggerResult",
]
