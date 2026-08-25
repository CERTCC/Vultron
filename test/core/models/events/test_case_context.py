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

"""Unit tests for case-context resolution (``events.case_context``)."""

import pytest

from vultron.core.models.events import (
    CASE_BOOTSTRAP_SEMANTICS,
    MessageSemantics,
    VultronEvent,
    is_case_bootstrap,
    resolve_case_context_id,
)
from vultron.core.models.events.base import VultronObject

ACTOR_ID = "https://example.org/actors/actor-1"
ACTIVITY_ID = "urn:uuid:11111111-1111-1111-1111-111111111111"
CASE_ID = "urn:uuid:22222222-2222-2222-2222-222222222222"
ACCEPT_ACTIVITY_ID = "urn:uuid:33333333-3333-3333-3333-333333333333"
AS2_NS = "https://www.w3.org/ns/activitystreams"


def _event(
    semantic_type: MessageSemantics,
    object_id: str | None = None,
    context_id: str | None = None,
) -> VultronEvent:
    return VultronEvent(
        activity_id=ACTIVITY_ID,
        actor_id=ACTOR_ID,
        semantic_type=semantic_type,
        object_=(
            VultronObject(id_=object_id, type_=None) if object_id else None
        ),
        context=(
            VultronObject(id_=context_id, type_=None) if context_id else None
        ),
    )


class TestIsCaseBootstrap:
    @pytest.mark.parametrize("semantic_type", sorted(CASE_BOOTSTRAP_SEMANTICS))
    def test_bootstrap_semantics(self, semantic_type):
        assert is_case_bootstrap(_event(semantic_type))

    @pytest.mark.parametrize(
        "semantic_type",
        [
            MessageSemantics.ENGAGE_CASE,
            MessageSemantics.CLOSE_CASE,
            MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY,
        ],
    )
    def test_non_bootstrap_semantics(self, semantic_type):
        assert not is_case_bootstrap(_event(semantic_type))


class TestResolveCaseContextIdBootstrap:
    def test_create_case_prefers_inline_case_over_accept_context(self):
        """CP-05-003 regression: ``context`` is the Accept URI, not the case.

        ``Create(VulnerabilityCase)`` sets ``context`` to the URI of the
        preceding ``Accept(CaseProposal)`` as CP-05-003 requires.  Resolving
        from ``context`` yields an activity URI that will never name a known
        case, which previously made the bootstrap defer itself forever.  The
        inline case object is authoritative.
        """
        event = _event(
            MessageSemantics.CREATE_CASE,
            object_id=CASE_ID,
            context_id=ACCEPT_ACTIVITY_ID,
        )

        resolved = resolve_case_context_id(
            event, wire_context=ACCEPT_ACTIVITY_ID
        )

        assert resolved == CASE_ID

    def test_announce_case_resolves_from_inline_case(self):
        event = _event(
            MessageSemantics.ANNOUNCE_VULNERABILITY_CASE, object_id=CASE_ID
        )

        assert resolve_case_context_id(event) == CASE_ID

    def test_bootstrap_without_inline_object_falls_back_to_context(self):
        """A bootstrap with no inline object still uses its context, if any."""
        event = _event(MessageSemantics.CREATE_CASE, context_id=CASE_ID)

        assert resolve_case_context_id(event) == CASE_ID


class TestResolveCaseContextIdNonBootstrap:
    def test_event_context_wins_over_wire_context(self):
        event = _event(MessageSemantics.ENGAGE_CASE, context_id=CASE_ID)

        resolved = resolve_case_context_id(
            event, wire_context="https://example.org/cases/other"
        )

        assert resolved == CASE_ID

    def test_non_bootstrap_ignores_inline_object_id(self):
        """``object_id`` is only authoritative for bootstrap semantics.

        For e.g. ENGAGE_CASE the object is the case, but resolution must stay
        driven by ``context`` so that non-case-shaped objects (notes, statuses)
        are never mistaken for case IDs.
        """
        event = _event(MessageSemantics.ENGAGE_CASE, object_id=CASE_ID)

        assert resolve_case_context_id(event) is None

    def test_wire_context_string_fallback(self):
        event = _event(MessageSemantics.ENGAGE_CASE)

        assert resolve_case_context_id(event, wire_context=CASE_ID) == CASE_ID

    def test_as2_namespace_wire_context_is_not_a_case_id(self):
        """The JSON-LD ``@context`` namespace URI is never a case reference."""
        event = _event(MessageSemantics.ENGAGE_CASE)

        assert resolve_case_context_id(event, wire_context=AS2_NS) is None

    def test_empty_wire_context_string(self):
        event = _event(MessageSemantics.ENGAGE_CASE)

        assert resolve_case_context_id(event, wire_context="") is None

    def test_wire_context_object_with_id(self):
        event = _event(MessageSemantics.ENGAGE_CASE)
        wire_context = VultronObject(id_=CASE_ID, type_=None)

        assert resolve_case_context_id(event, wire_context) == CASE_ID

    def test_no_context_anywhere(self):
        event = _event(MessageSemantics.ENGAGE_CASE)

        assert resolve_case_context_id(event) is None
