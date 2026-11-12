"""The frozen ``(client, actor, case?)`` binding every trigger verb posts through.

:class:`SessionBinding` holds the session's fields, checks the
``(client, actor)`` pairing once at construction (DEMOMA-26-008), and owns
:meth:`SessionBinding._post`, the one call site of the private
``post_to_trigger`` transport (DEMOMA-26-001).  The verb families subclass it
and :class:`~vultron.demo.actor_session.session.ActorSession` combines them.
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

import logging
from dataclasses import dataclass, replace
from typing import Any, Self
from urllib.parse import urlsplit

from vultron.core.behaviors.store_scope import same_authority
from vultron.demo.actor_session.results import WireTriggerResult
from vultron.demo.utils import DataLayerClient, post_to_trigger, ref_id
from vultron.demo.utils.served import from_server
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


def _is_absolute_uri(value: str) -> bool:
    """True when *value* parses as a URI carrying both a scheme and a netloc.

    Only a real absolute URI can mis-address a live container; a ``MagicMock``
    ``base_url`` repr or a bare unit-test actor slug cannot, so a pair where
    either side is not absolute is left unchecked (see :meth:`__post_init__`).
    """
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return bool(parts.scheme and parts.netloc)


@dataclass(frozen=True)
class SessionBinding:
    """The fields and transport shared by every :class:`ActorSession` verb.

    See :class:`~vultron.demo.actor_session.session.ActorSession` for what each
    field means; this base exists so the verb families can live in their own
    modules and still post through one :meth:`_post`.
    """

    client: DataLayerClient
    actor: as_Actor
    case_id: str | None = None
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
        (DEMOMA-26-008).

        Also refuses a blank ``case_id``: a bound case ID is non-empty
        (CS-08-002), or the trigger URL would name no case.
        """
        if self.case_id is not None and not self.case_id.strip():
            raise ValueError("case_id must be a non-empty case ID when bound")
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

    def with_case(self, case: as_VulnerabilityCase | str) -> Self:
        """Return a new session bound to *case* (a case or its ID).

        Does not modify the receiver.
        """
        case_id = case if isinstance(case, str) else case.id_
        return replace(self, case_id=case_id)

    def quiet(self) -> Self:
        """Return a new session that does not log per-verb banners."""
        return replace(self, narrate=False)

    # -- internals --------------------------------------------------------

    def _require_case_id(self) -> str:
        """Return the bound case's URI, or raise if no case is bound."""
        if self.case_id is None:
            raise ValueError(
                "this trigger is case-scoped; bind a case with"
                " ActorSession.with_case(case) before calling it"
            )
        return self.case_id

    def _post(
        self,
        behavior: str,
        body: dict[str, Any],
        path_prefix: str = "trigger",
        *,
        result_cls: type[WireTriggerResult] = WireTriggerResult,
    ) -> WireTriggerResult:
        """Post *behavior* for this session's actor and type the response.

        Wraps :func:`post_to_trigger` — the one permitted call site outside
        ``utils`` — and validates the raw response ``dict`` into *result_cls*
        (a :class:`WireTriggerResult` or subtype).
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
        return from_server(result_cls, raw)

    @staticmethod
    def _roles_body(roles: list[CVDRole] | None) -> dict[str, Any]:
        """Body fragment carrying an optional roles list, omitted when absent."""
        return {"roles": [r.value for r in roles]} if roles is not None else {}
