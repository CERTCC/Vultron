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

"""Typed ``(container, actor, case)`` binding for demo trigger calls.

:class:`ActorSession` is the single API through which demo scenarios and
exchanges invoke trigger endpoints (DEMOMA-26-001).  It replaces the
stringly-typed :func:`vultron.demo.utils.post_to_trigger` at every call site:

- The ``(client, actor)`` pairing is checked **once** at construction rather
  than on every call, so a mismatched pair is unconstructible instead of a
  guard that silently passes in unit tests (DEMOMA-26-002).
- Each trigger verb is a typed method: a misspelled behavior name is now a
  ``AttributeError`` at import/lint time, and a misspelled body key is
  impossible because the method's keyword parameters are fixed (DEMOMA-26-004).
  ``test/architecture/test_actor_session_kwargs_match_request_models.py``
  ratchets those parameters against the trigger request models.
- The case is bound separately with :meth:`with_case`, because a case does not
  exist when the actor is first constructed (DEMOMA-26-003).

``post_to_trigger`` remains the private transport, wrapped by :meth:`_post`;
it MUST NOT be imported anywhere except this module and
:mod:`vultron.demo.utils` (DEMOMA-26-001).
"""

import logging
from dataclasses import dataclass, replace
from typing import Any, cast
from urllib.parse import urlsplit

from vultron.core.behaviors.store_scope import same_authority
from vultron.core.use_cases.triggers.results import TriggerResult
from vultron.demo.utils import DataLayerClient, post_to_trigger, ref_id
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


class ActivityResult(TriggerResult):
    """Trigger result whose emitted activity is typed (UCORG-05-014).

    Overrides the base ``activity: dict | None`` with a required, validated
    :class:`as_TransitiveActivity`.  Built by ``model_validate``-ing the raw
    trigger response, so the ``activity`` key is coerced from its wire ``dict``
    into the typed object.  It lives here in the demo layer rather than in
    ``vultron/core/`` because no core-layer activity type is reachable without
    the ``WireParsePort`` seam (ADR-0082) yet.
    """

    activity: as_TransitiveActivity  # type: ignore[assignment]


class SyncLogEntryResult(TriggerResult):
    """Result of the ``sync-log-entry`` demo trigger.

    Adds the committed ledger entry's hash, which the sync helpers assert
    against a participant replica's tail hash, and the entry's log index.
    """

    entry_hash: str
    log_index: int | None = None


class NoteResult(TriggerResult):
    """Result of the ``add-note-to-case`` demo trigger.

    Carries the freshly minted note object so the note helper can recover its
    id — the note did not exist before the trigger, so there is no other source
    for it.
    """

    note: dict[str, Any] | None = None


def _is_absolute_uri(value: str) -> bool:
    """True when *value* parses as a URI carrying both a scheme and a netloc.

    Only a real absolute URI can mis-address a live container; a ``MagicMock``
    ``base_url`` repr or a bare unit-test actor slug cannot, so a pair where
    either side is not absolute is left unchecked (see :meth:`_check_authority`).
    """
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return bool(parts.scheme and parts.netloc)


@dataclass(frozen=True)
class ActorSession:
    """A frozen ``(client, actor, case?)`` binding for demo trigger calls.

    Args:
        client: Client connected to the container that hosts *actor*.
        actor: The actor on whose behalf triggers are posted.
        case: The case trigger verbs operate on.  ``None`` at construction;
            set a copy with :meth:`with_case` once the case exists.
        narrate: When ``True`` (default), each verb logs an INFO banner naming
            the action and actor.  :meth:`quiet` returns a silent copy for calls
            that already sit inside a scenario ``demo_step`` banner.
    """

    client: DataLayerClient
    actor: as_Actor
    case: as_VulnerabilityCase | None = None
    narrate: bool = True

    def __post_init__(self) -> None:
        """Reject a ``(client, actor)`` pair naming different containers.

        The trigger URL keeps only the actor's bare object id and resolves it
        against ``client.base_url``, so a mismatched pair addresses whatever the
        target container hosts under that slug — a 404, or (worse) a foreign
        actor's store — with no error at the HTTP layer to notice.  Moving this
        check to construction (formerly ``_assert_client_hosts_actor``) makes a
        mismatched session unconstructible rather than a per-call guard that
        silently passes wherever neither side is a real absolute URI
        (DEMOMA-26-002).
        """
        actor_id = self.actor.id_
        base_url = str(getattr(self.client, "base_url", "") or "")
        if not isinstance(actor_id, str) or not _is_absolute_uri(actor_id):
            return
        if not _is_absolute_uri(base_url):
            return
        if not same_authority(base_url, actor_id):
            raise ValueError(
                f"actor '{actor_id}' is not hosted by '{base_url}' — build the"
                " ActorSession with that actor's own container client"
            )

    # -- immutable copies -------------------------------------------------

    def with_case(self, case: as_VulnerabilityCase) -> "ActorSession":
        """Return a new session bound to *case*; does not modify the receiver."""
        return replace(self, case=case)

    def quiet(self) -> "ActorSession":
        """Return a new session that does not log per-verb banners."""
        return replace(self, narrate=False)

    # -- internals --------------------------------------------------------

    def _require_case_id(self) -> str:
        """Return the bound case's URI, or raise if no case is bound."""
        if self.case is None:
            raise ValueError(
                "this trigger is case-scoped; bind a case with"
                " ActorSession.with_case(case) before calling it"
            )
        return cast(str, self.case.id_)

    def _post(
        self,
        behavior: str,
        body: dict[str, Any],
        path_prefix: str = "trigger",
        *,
        result_cls: type[TriggerResult] = TriggerResult,
    ) -> TriggerResult:
        """Post *behavior* for this session's actor and type the response.

        Wraps :func:`post_to_trigger` — the one permitted call site outside
        ``utils`` — and validates the raw response ``dict`` into *result_cls*
        (a :class:`TriggerResult` or subtype).
        """
        if self.narrate:
            logger.info(
                "Actor %s: %s", ref_id(self.actor), behavior.replace("-", " ")
            )
        raw = post_to_trigger(
            client=self.client,
            actor_id=self.actor.id_,
            behavior=behavior,
            body=body,
            path_prefix=path_prefix,
        )
        return result_cls.model_validate(raw)

    @staticmethod
    def _roles_body(roles: list[CVDRole] | None) -> dict[str, Any]:
        """Body fragment carrying an optional roles list, omitted when absent."""
        return {"roles": [r.value for r in roles]} if roles is not None else {}

    # -- report triggers --------------------------------------------------

    def submit_report(
        self, *, report_name: str, report_content: str, recipient_id: str
    ) -> TriggerResult:
        """Create a report and offer it to *recipient_id* (submit-report)."""
        return self._post(
            "submit-report",
            {
                "report_name": report_name,
                "report_content": report_content,
                "recipient_id": recipient_id,
            },
        )

    def validate_report(
        self, *, offer_id: str, note: str | None = None
    ) -> TriggerResult:
        """Advance the offered report to RM.VALID (validate-report)."""
        body: dict[str, Any] = {"offer_id": offer_id}
        if note is not None:
            body["note"] = note
        return self._post("validate-report", body)

    def invalidate_report(
        self, *, offer_id: str, note: str | None = None
    ) -> TriggerResult:
        """Mark the offered report RM.INVALID (invalidate-report)."""
        body: dict[str, Any] = {"offer_id": offer_id}
        if note is not None:
            body["note"] = note
        return self._post("invalidate-report", body)

    def close_report(
        self, *, offer_id: str, note: str | None = None
    ) -> TriggerResult:
        """Close the report after its RM lifecycle (close-report)."""
        body: dict[str, Any] = {"offer_id": offer_id}
        if note is not None:
            body["note"] = note
        return self._post("close-report", body)

    # -- case lifecycle triggers -----------------------------------------

    def create_case(
        self,
        *,
        name: str,
        content: str,
        report_id: str | None = None,
        to: list[str] | None = None,
    ) -> TriggerResult:
        """Create a local case and queue a CreateCaseActivity (create-case)."""
        body: dict[str, Any] = {"name": name, "content": content}
        if report_id is not None:
            body["report_id"] = report_id
        if to is not None:
            body["to"] = to
        return self._post("create-case", body)

    def engage_case(self) -> TriggerResult:
        """Engage the bound case, advancing RM to ACCEPTED (engage-case)."""
        return self._post("engage-case", {"case_id": self._require_case_id()})

    def invite_actor_to_case(
        self, *, invitee_id: str, roles: list[CVDRole] | None = None
    ) -> ActivityResult:
        """Invite *invitee_id* to the bound case (invite-actor-to-case)."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "invitee_id": invitee_id,
            **self._roles_body(roles),
        }
        return cast(
            ActivityResult,
            self._post(
                "invite-actor-to-case", body, result_cls=ActivityResult
            ),
        )

    def suggest_actor_to_case(
        self, *, suggested_actor_id: str, roles: list[CVDRole] | None = None
    ) -> TriggerResult:
        """Recommend *suggested_actor_id* to the bound case (suggest-actor-to-case)."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "suggested_actor_id": suggested_actor_id,
            **self._roles_body(roles),
        }
        return self._post("suggest-actor-to-case", body)

    def accept_case_invite(self, *, invite_id: str) -> TriggerResult:
        """Accept a case invitation identified by *invite_id* (accept-case-invite)."""
        return self._post("accept-case-invite", {"invite_id": invite_id})

    def reject_case_invite(self, *, invite_id: str) -> TriggerResult:
        """Reject a case invitation identified by *invite_id* (reject-case-invite)."""
        return self._post("reject-case-invite", {"invite_id": invite_id})

    def accept_actor_recommendation(
        self, *, cp_offer_id: str, case_actor_id: str
    ) -> TriggerResult:
        """Accept a forwarded Offer(CaseParticipant) (accept-actor-recommendation)."""
        return self._post(
            "accept-actor-recommendation",
            {"cp_offer_id": cp_offer_id, "case_actor_id": case_actor_id},
        )

    def offer_case_ownership_transfer(
        self, *, transferee_id: str, content: str | None = None
    ) -> ActivityResult:
        """Offer ownership of the bound case to *transferee_id* (offer-case-ownership-transfer)."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "transferee_id": transferee_id,
        }
        if content is not None:
            body["content"] = content
        return cast(
            ActivityResult,
            self._post(
                "offer-case-ownership-transfer",
                body,
                result_cls=ActivityResult,
            ),
        )

    def accept_case_ownership_transfer(
        self, *, offer_id: str
    ) -> ActivityResult:
        """Accept a case-ownership-transfer offer (accept-case-ownership-transfer)."""
        return cast(
            ActivityResult,
            self._post(
                "accept-case-ownership-transfer",
                {"offer_id": offer_id},
                result_cls=ActivityResult,
            ),
        )

    # -- demo-only triggers (path_prefix="demo") -------------------------

    def add_note_to_case(
        self,
        *,
        note_name: str,
        note_content: str,
        in_reply_to: str | None = None,
    ) -> NoteResult:
        """Attach a note to the bound case (add-note-to-case)."""
        body: dict[str, Any] = {
            "case_id": self._require_case_id(),
            "note_name": note_name,
            "note_content": note_content,
        }
        if in_reply_to is not None:
            body["in_reply_to"] = in_reply_to
        return cast(
            NoteResult,
            self._post(
                "add-note-to-case",
                body,
                path_prefix="demo",
                result_cls=NoteResult,
            ),
        )

    def notify_fix_ready(self) -> TriggerResult:
        """Self-report fix ready (CS.VFd) for the bound case (notify-fix-ready)."""
        return self._post(
            "notify-fix-ready",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def notify_fix_deployed(self) -> TriggerResult:
        """Self-report fix deployed (CS.VFD) for the bound case (notify-fix-deployed)."""
        return self._post(
            "notify-fix-deployed",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def notify_published(self) -> TriggerResult:
        """Self-report public disclosure for the bound case (notify-published)."""
        return self._post(
            "notify-published",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def close_case(self) -> TriggerResult:
        """Send Leave(VulnerabilityCase) for the bound case (close-case, ADR-0050)."""
        return self._post(
            "close-case",
            {"case_id": self._require_case_id()},
            path_prefix="demo",
        )

    def sync_log_entry(
        self, *, object_id: str, event_type: str
    ) -> SyncLogEntryResult:
        """Commit and fan out a canonical ledger entry (sync-log-entry)."""
        return cast(
            SyncLogEntryResult,
            self._post(
                "sync-log-entry",
                {
                    "case_id": self._require_case_id(),
                    "object_id": object_id,
                    "event_type": event_type,
                },
                path_prefix="demo",
                result_cls=SyncLogEntryResult,
            ),
        )
