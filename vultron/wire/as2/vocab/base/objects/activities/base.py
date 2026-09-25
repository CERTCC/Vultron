#!/usr/bin/env python
"""This module provides base activity classes"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import json
from typing import Any

from pydantic import Field, PrivateAttr

from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_ActorRef
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.enums import as_ObjectType as O_type


class as_Activity(as_Object):
    """https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity
    An Activity is a subtype of Object that describes some form of action that may happen, is
    currently happening, or has already happened. The Activity type itself serves as an abstract
    base type for all types of activities. It is important to note that an Activity is not a
    representation of a currently executing process, but rather a statement about that process.
    For example, a person walking down the street is not an Activity unless they are posting a
    picture of themselves walking down the street. The Activity in that case would be the posting
    of the picture, not the person walking down the street.
    """

    type_: str = Field(
        default=O_type.ACTIVITY,
        validation_alias="type",
        serialization_alias="type",
    )

    # All four slots admit a core object, not just ``actor``.
    #
    # Widening only ``actor`` (and ``as_ObjectRef``, for ``object_``) left
    # ``target``/``origin``/``instrument`` declaring a wire-only union while the
    # adapters put promoted core classes in them.  A value outside its declared
    # union escapes in both directions: outbound, Pydantic emits
    # ``PydanticSerializationUnexpectedValue`` and ships a payload shaped by the
    # wrong schema; inbound, a payload from an unmodified peer is refused. That is
    # what made every recipient answer ``422`` to ``Create(VulnerabilityCase)`` and
    # never seed the case replica (ADR-0041, PCR-01-003).
    #
    # The type errors this produced on the subclass overrides were suppressed with
    # ``# type: ignore[assignment]`` rather than fixed, which is why mypy and
    # pyright stayed green while the wire protocol did not work. Widening here is
    # what lets those suppressions be deleted: a subclass narrowing
    # ``target`` to ``VulnerabilityCase | as_Link | str | None`` is now a genuine
    # narrowing of this union rather than an incompatible override.
    actor: as_ActorRef | CoreActor
    target: as_Object | as_Link | str | CoreObject | None = None
    origin: as_Object | as_Link | str | CoreObject | None = None
    instrument: as_Object | as_Link | str | CoreObject | None = None
    result: as_Object | as_Link | str | None = None

    #: The JSON body as received, decoded and re-serialized to text by
    #: ``parse_activity`` before anything reads or expands it (VM-08-002).
    #: Keys, key order and values are the sender's; whitespace, number
    #: spelling and escapes are not kept, because the body arrives decoded.
    #: ``frozen=True`` covers this activity's own fields, but it does not reach
    #: the nested objects: since ADR-0099 detail 3 most of those are mutable core
    #: classes.  So the received evidence is kept here as an immutable ``str``,
    #: independent of the object graph, rather than being inferred from the
    #: graph's class configuration (ISSUE-3584).  ``None`` on an activity this
    #: process authored or rebuilt from storage.
    _received_evidence: str | None = PrivateAttr(default=None)

    @property
    def received_evidence_json(self) -> str | None:
        """The received JSON as the text it was sealed with, or ``None``."""
        return self._received_evidence

    @property
    def received_evidence(self) -> dict[str, Any] | None:
        """A fresh copy of the received JSON, or ``None`` if none was sealed.

        Every call decodes a new ``dict``, so what a caller does to the result
        cannot reach the sealed evidence or any other caller's copy.
        """
        if self._received_evidence is None:
            return None
        evidence: dict[str, Any] = json.loads(self._received_evidence)
        return evidence

    def seal_received_evidence(self, evidence_json: str) -> None:
        """Attach the received JSON to this activity, exactly once.

        Pydantic leaves private attributes writable on a frozen model, so the
        write-once rule is enforced here: resealing with the same text is a
        no-op (a routing copy inheriting its artifact's evidence), and any other
        text raises, because two different claims about what arrived cannot both
        be the evidence.

        Raises:
            ValueError: If different evidence is already sealed.
        """
        current = self._received_evidence
        if current is not None and current != evidence_json:
            raise ValueError(
                f"{type(self).__name__} {self.id_!r} already carries different "
                "received evidence; received evidence is sealed once (VM-08-002)."
            )
        self._received_evidence = evidence_json

    def description(self):
        raise NotImplementedError


def main():
    x = as_Activity(actor="https://example.org/actor")
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
