"""Typed views of a trigger endpoint's HTTP response body (UCORG-05-014)."""

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

from typing import Any

from pydantic import BaseModel, ConfigDict

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)


class WireTriggerResult(BaseModel):
    """Typed view of a trigger endpoint's HTTP response body (UCORG-05-014).

    This is the demo layer's reading of the JSON a trigger route returned,
    not a use-case return value: the core ``TriggerResult`` hierarchy in
    ``vultron/core/models/use_case_result.py`` is what the use cases return
    and forbids unknown keys, while this view is built by
    ``model_validate``-ing the raw response ``dict`` and MUST tolerate the
    keys a given verb does not carry (``extra="ignore"``).  Every field is
    optional for the same reason: one view validates any verb's body.  The
    ``Wire`` prefix keeps the names disjoint from core's (``WireCaseLedgerEntry``
    follows the same convention).
    """

    model_config = ConfigDict(extra="ignore")

    activity: dict[str, Any] | None = None
    case_id: NonEmptyString | None = None
    emitting_actor_id: NonEmptyString | None = None
    offer: dict[str, Any] | None = None


class WireActivityResult(WireTriggerResult):
    """Trigger response whose emitted activity is typed (UCORG-05-014).

    Overrides the base ``activity: dict | None`` with a required, validated
    :class:`as_TransitiveActivity`.  Built by ``model_validate``-ing the raw
    trigger response, so the ``activity`` key is coerced from its wire ``dict``
    into the typed object.  It lives here in the demo layer rather than in
    ``vultron/core/`` because :class:`as_TransitiveActivity` is a wire-only
    class and core MUST NOT import wire (ARCH-01-001); the core
    ``ActivityResult`` captures ``activity`` as a ``dict`` from the blackboard.
    """

    activity: as_TransitiveActivity  # type: ignore[assignment]


class WireSyncLogEntryResult(WireTriggerResult):
    """Response of the ``sync-log-entry`` demo trigger.

    Adds the committed ledger entry's hash, which the sync helpers assert
    against a participant replica's tail hash, and the entry's log index.
    """

    entry_hash: NonEmptyString
    log_index: int | None = None


class WireNoteResult(WireTriggerResult):
    """Response of the ``add-note-to-case`` demo trigger.

    Carries the freshly minted note object so the note helper can recover its
    id — the note did not exist before the trigger, so there is no other source
    for it.
    """

    note: dict[str, Any] | None = None
