#!/usr/bin/env python
"""
Unit tests for vultron.adapters.driving.fastapi.routers.actors._inbox.

Tests inbox processing helpers in isolation from the HTTP layer.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import pytest
from fastapi import HTTPException

from typing import cast

from vultron.adapters.driving.fastapi.routers.actors._inbox import (
    _activity_addressed_to,
    _activity_already_received,
    _collect_addresses,
    _get_body,
    _names_an_individual_actor,
    _record_inbox_receipt,
    _reparse_as_specific_type,
    _store_inbox_activity,
    _store_nested_inbox_object,
    parse_activity,
)
from vultron.core.models.actor import CoreActor
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Create,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ACTOR_URI = "https://example.org/actors/alice"
_ACTIVITY_URI = "https://example.org/activities/create-001"


# ---------------------------------------------------------------------------
# parse_activity
# ---------------------------------------------------------------------------


def test_parse_activity_returns_typed_activity_for_valid_body():
    note = as_Note(content="hello")
    create = as_Create(
        actor=_ACTOR_URI,
        object_=note,
    )
    body = create.model_dump(mode="json", by_alias=True, exclude_none=True)
    result = parse_activity(body)
    assert isinstance(result, as_Create)


def test_parse_activity_raises_400_when_type_missing():
    with pytest.raises(HTTPException) as exc_info:
        parse_activity({"actor": _ACTOR_URI, "object": {}})
    assert exc_info.value.status_code == 400


def test_parse_activity_raises_422_for_unknown_type():
    with pytest.raises(HTTPException) as exc_info:
        parse_activity(
            {"type": "NonExistentActivityType", "actor": _ACTOR_URI}
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# _get_body
# ---------------------------------------------------------------------------


def test_get_body_returns_dict_unchanged():
    body = {"type": "Create", "actor": _ACTOR_URI}
    assert _get_body(body) is body


# ---------------------------------------------------------------------------
# _activity_already_received
# ---------------------------------------------------------------------------


def test_activity_already_received_returns_true_when_in_inbox():
    actor = as_Organization(id_=_ACTOR_URI, name="Alice")
    actor.inbox.items.append(_ACTIVITY_URI)
    assert (
        _activity_already_received(cast(CoreActor, actor), _ACTIVITY_URI)
        is True
    )


def test_activity_already_received_returns_false_when_not_in_inbox():
    actor = as_Organization(id_=_ACTOR_URI, name="Alice")
    assert (
        _activity_already_received(cast(CoreActor, actor), _ACTIVITY_URI)
        is False
    )


def test_activity_already_received_returns_false_when_inbox_is_none():
    actor = CoreActor(id_=_ACTOR_URI, name="Alice")
    assert _activity_already_received(actor, _ACTIVITY_URI) is False


# ---------------------------------------------------------------------------
# _reparse_as_specific_type
# ---------------------------------------------------------------------------


def test_reparse_as_specific_type_returns_specific_class_for_known_type():
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    case = as_VulnerabilityCase(
        id_="urn:uuid:test-case-001",
        name="Test CVD Case",
    )
    raw_obj = case.model_dump(mode="json", by_alias=True, exclude_none=True)
    # Pass as base as_Object to simulate what the wire parser produces
    nested = as_Object.model_validate(raw_obj)
    result = _reparse_as_specific_type(nested, raw_obj)
    assert isinstance(result, as_VulnerabilityCase)


def test_reparse_as_specific_type_returns_base_when_type_is_none():
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    nested = as_Object()
    result = _reparse_as_specific_type(nested, {})
    assert result is nested  # type: ignore[comparison-overlap]


def test_reparse_as_specific_type_returns_same_object_when_already_specific_class():
    """Guard branch: nested is already the specific class → return unchanged."""
    case = as_VulnerabilityCase(
        id_="urn:uuid:test-case-already-specific",
        name="Already Specific",
    )
    raw_obj = case.model_dump(mode="json", by_alias=True, exclude_none=True)
    result = _reparse_as_specific_type(case, raw_obj)
    assert result is case


# ---------------------------------------------------------------------------
# _store_inbox_activity
# ---------------------------------------------------------------------------


def test_store_inbox_activity_persists_activity(datalayer):
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note)
    _store_inbox_activity(datalayer, activity)
    stored = datalayer.read(activity.id_)
    assert stored is not None


def test_store_inbox_activity_is_idempotent(datalayer):
    note = as_Note(content="test")
    activity = as_Create(actor=_ACTOR_URI, object_=note)
    # Second call must not raise
    _store_inbox_activity(datalayer, activity)
    _store_inbox_activity(datalayer, activity)


# ---------------------------------------------------------------------------
# _store_nested_inbox_object
# ---------------------------------------------------------------------------


def test_store_nested_inbox_object_stores_inline_case(datalayer):
    case = as_VulnerabilityCase(
        id_="urn:uuid:case-nest-001",
        name="Nested Case",
    )
    activity = as_Announce(
        actor=_ACTOR_URI,
        object_=case,
    )
    raw_body = {
        "object": case.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
    }
    _store_nested_inbox_object(datalayer, activity, raw_body)
    stored = datalayer.read(case.id_)
    assert stored is not None


def test_store_nested_inbox_object_skips_string_object(datalayer):
    """When object_ is a URI string, no persistence should happen."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Announce,
    )

    activity = as_Announce(actor=_ACTOR_URI, object_="urn:uuid:some-id")
    # Should not raise; DL should remain empty
    _store_nested_inbox_object(datalayer, activity, None)


def test_store_nested_inbox_object_skips_when_no_body(datalayer):
    case = as_VulnerabilityCase(
        id_="urn:uuid:case-nobody-001",
        name="No Body Case",
    )
    activity = as_Announce(actor=_ACTOR_URI, object_=case)
    # body=None: should fall back to base as_Object storage without crashing
    _store_nested_inbox_object(datalayer, activity, None)


def test_store_nested_inbox_object_logs_a_projection_failure(
    datalayer, caplog
):
    """An unpersistable inline object must be logged at ERROR (issue #2232).

    A projection failure and an "already exists" collision both used to surface
    as ``ValueError`` and were swallowed together at DEBUG, so the row was
    silently absent and downstream BT nodes reported a misleading "participant
    not found".  The distinct ``VultronValidationError`` is now logged loudly.
    """
    import logging

    from vultron.wire.as2.vocab.objects.case_participant import (
        as_CaseParticipant,
    )

    # NonEmptyString rejects "" on the core class but not the wire class, so
    # this participant is constructible yet cannot be projected to core.
    unprojectable = as_CaseParticipant(
        id_="urn:uuid:participant-2232-unprojectable",
        attributed_to=_ACTOR_URI,
        context="https://example.org/cases/case-2232",
        accepted_embargo_ids=[""],
    )
    activity = as_Announce(actor=_ACTOR_URI, object_=unprojectable)

    with caplog.at_level(logging.ERROR):
        _store_nested_inbox_object(datalayer, activity, None)

    assert datalayer.read(unprojectable.id_) is None
    assert "cannot be projected" in caplog.text


def test_store_nested_inbox_object_duplicate_stays_at_debug(datalayer, caplog):
    """A genuine duplicate is not an error — it must not be logged as one."""
    import logging

    case = as_VulnerabilityCase(
        id_="urn:uuid:case-dup-2232",
        name="Duplicate Case",
    )
    activity = as_Announce(actor=_ACTOR_URI, object_=case)
    _store_nested_inbox_object(datalayer, activity, None)

    with caplog.at_level(logging.DEBUG):
        _store_nested_inbox_object(datalayer, activity, None)

    assert "already exists" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


# ---------------------------------------------------------------------------
# _record_inbox_receipt
# ---------------------------------------------------------------------------


def test_record_inbox_receipt_appends_to_inbox_items(datalayer):
    from vultron.adapters.driven.db_record import object_to_record

    actor = as_Organization(id_=_ACTOR_URI, name="Alice")
    datalayer.create(object_to_record(actor))

    _record_inbox_receipt(
        datalayer, cast(CoreActor, actor), _ACTIVITY_URI, _ACTOR_URI
    )
    assert _ACTIVITY_URI in actor.inbox.items


def test_record_inbox_receipt_is_noop_when_inbox_has_no_items_attr(datalayer):
    """Actor with string inbox URI should not raise."""
    actor = CoreActor(id_=_ACTOR_URI, name="Alice", inbox="https://inbox.url")
    # Should not raise
    _record_inbox_receipt(datalayer, actor, _ACTIVITY_URI, _ACTOR_URI)


# ---------------------------------------------------------------------------
# _collect_addresses
# ---------------------------------------------------------------------------

_OTHER_ACTOR_URI = "https://example.org/actors/bob"


def test_collect_addresses_returns_empty_when_all_fields_absent():
    activity = as_Create(actor=_ACTOR_URI, object_=as_Note(content="hi"))
    assert _collect_addresses(activity) == []


def test_collect_addresses_returns_uri_from_to_string():
    activity = as_Create(actor=_ACTOR_URI, object_=as_Note(content="hi"))
    activity.to = _ACTOR_URI
    assert _ACTOR_URI in _collect_addresses(activity)


def test_collect_addresses_returns_uris_from_list():
    activity = as_Create(actor=_ACTOR_URI, object_=as_Note(content="hi"))
    activity.to = [_ACTOR_URI, _OTHER_ACTOR_URI]
    addrs = _collect_addresses(activity)
    assert _ACTOR_URI in addrs
    assert _OTHER_ACTOR_URI in addrs


def test_collect_addresses_extracts_id_from_object():
    from vultron.wire.as2.vocab.base.objects.actors import as_Organization

    actor_obj = as_Organization(id_=_ACTOR_URI, name="Alice")
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = actor_obj
    assert _ACTOR_URI in _collect_addresses(activity)


def test_collect_addresses_covers_all_four_fields():
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = "https://example.org/actors/to"
    activity.cc = "https://example.org/actors/cc"
    activity.bto = "https://example.org/actors/bto"
    activity.bcc = "https://example.org/actors/bcc"
    addrs = _collect_addresses(activity)
    assert len(addrs) == 4


# ---------------------------------------------------------------------------
# _activity_addressed_to  (AC-1 through AC-4)
# ---------------------------------------------------------------------------


def test_activity_addressed_to_returns_true_when_absent_addressing():
    """AC-3: absent addressing → Liberal Accept."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_returns_true_when_in_to():
    """AC-2: actor named in to → accepted."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = _ACTOR_URI
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_returns_true_when_in_cc():
    """AC-2: actor named in cc → accepted."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.cc = _ACTOR_URI
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_returns_true_when_in_bto():
    """AC-2: actor named in bto → accepted."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.bto = _ACTOR_URI
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_returns_true_when_in_bcc():
    """AC-2: actor named in bcc → accepted."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.bcc = _ACTOR_URI
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_returns_false_when_addressed_exclusively_to_other():
    """AC-1: Activity addressed only to another actor → refused."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = _OTHER_ACTOR_URI
    assert _activity_addressed_to(activity, _ACTOR_URI) is False


def test_activity_addressed_to_returns_false_when_list_has_only_other_actors():
    """AC-1: list-form addressing that excludes actor → refused."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = [_OTHER_ACTOR_URI, "https://example.org/actors/charlie"]
    assert _activity_addressed_to(activity, _ACTOR_URI) is False


def test_activity_addressed_to_returns_true_with_canonical_uri_in_list():
    """AC-2: canonical actor URI in a list is accepted."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = [_OTHER_ACTOR_URI, _ACTOR_URI]
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_returns_true_when_short_id_matches():
    """AC-4: short-ID form of actor URI is treated as a match."""
    # _ACTOR_URI = "https://example.org/actors/alice"
    # strip_id_prefix("alice") == strip_id_prefix(_ACTOR_URI) == "alice"
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = "alice"
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_short_id_of_other_actor_does_not_match():
    """AC-4 negative: short ID of a different actor does not satisfy the check."""
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = "bob"  # strip_id_prefix(_OTHER_ACTOR_URI) == "bob"
    assert _activity_addressed_to(activity, _ACTOR_URI) is False


def test_activity_addressed_to_returns_true_for_collection_uri():
    """IE-11-002: collection URI (unresolvable) → Liberal Accept.

    No DataLayer is involved.  This used to seed the receiving actor and pass a
    ``dl``, which read as though store contents mattered to the outcome; they
    never did for this case, and the parameter is gone.
    """
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    # Collection URI — the last segment "participants" won't resolve to any actor
    activity.to = "https://example.org/cases/case-001/participants"
    assert _activity_addressed_to(activity, _ACTOR_URI) is True


def test_activity_addressed_to_refuses_when_every_address_names_another_actor():
    """IE-11-001: every address names some other individual actor → refuse.

    "Known" is no longer part of the question — the predicate reads the address's
    shape, not any store's contents.
    """
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = _OTHER_ACTOR_URI  # addressed exclusively to bob
    assert _activity_addressed_to(activity, _ACTOR_URI) is False


def test_activity_addressed_to_refuses_peer_absent_from_the_receivers_store():
    """IE-11-001: a peer the receiver's store has never heard of is still a peer.

    Regression for the ADR-0072 interaction: resolvability used to be probed
    with ``dl.find_actor_by_short_id``, which asks the *receiving actor's own*
    store whether it knows the addressee.  Under per-actor isolation the answer
    is structurally "no" for every peer — a store holds its owner's knowledge,
    not the node's roster — so every misaddressed Activity naming a real peer
    fell through to Liberal Accept and IE-11-001 refused nothing at all.

    Nothing is seeded, because nothing can be: the predicate no longer takes a
    store.  Bob being absent from alice's store is the normal state of affairs,
    not an edge case, which is precisely why the lookup had to go.
    """
    activity = as_Create(actor=_OTHER_ACTOR_URI, object_=as_Note(content="x"))
    activity.to = _OTHER_ACTOR_URI
    assert _activity_addressed_to(activity, _ACTOR_URI) is False


# ---------------------------------------------------------------------------
# _names_an_individual_actor — the address-shape predicate behind IE-11-002
# ---------------------------------------------------------------------------


class TestNamesAnIndividualActor:
    """IE-11-002 asks about the *address*, so each recognised shape is pinned.

    The predicate consults no store, which is what fixed the ADR-0072
    interaction: a store holds its owner's knowledge, not the node's roster, so
    "do I know this addressee?" answered "no" for every peer and IE-11-001
    refused nothing. Since the answer now comes entirely from the string, the
    string shapes are the contract.

    False means "unresolvable", which means Liberal Accept — so a bug here does
    not reject good traffic, it *accepts* misaddressed traffic. That asymmetry is
    why the negative cases below matter more than the positive ones.
    """

    @pytest.mark.parametrize(
        "addr",
        [
            "https://example.org/actors/alice",
            "http://vendor:7999/api/v2/actors/vendor",
            "https://example.org/actors/case-actor-abc123",
            "bob",
        ],
    )
    def test_recognises_an_individual_actor(self, addr):
        assert _names_an_individual_actor(addr) is True

    def test_a_sub_collection_of_an_actor_is_not_the_actor(self):
        """``{actor_id}/followers`` addresses a set, not the actor.

        The second-to-last segment is the actor slug, not ``actors``, so this is
        unresolvable and falls through to Liberal Accept. Treating it as
        individual would make IE-11-001 refuse an Activity addressed to alice's
        followers when alice is the receiver — a broadcast rejected as
        misaddressed.
        """
        assert (
            _names_an_individual_actor(
                "https://example.org/actors/alice/followers"
            )
            is False
        )

    @pytest.mark.parametrize(
        "sub", ["followers", "following", "inbox", "liked"]
    )
    def test_no_actor_sub_collection_is_treated_as_individual(self, sub):
        assert (
            _names_an_individual_actor(
                f"https://example.org/actors/alice/{sub}"
            )
            is False
        )

    def test_the_public_addressing_constant_is_not_an_individual(self):
        """``as:Public`` is the broadest possible address.

        Its path is ``/ns/activitystreams``, so the shape test rejects it — which
        is the required outcome: an Activity addressed only to Public must reach
        every receiver, and treating the constant as "some other individual actor"
        would refuse all of them.
        """
        assert (
            _names_an_individual_actor(
                "https://www.w3.org/ns/activitystreams#Public"
            )
            is False
        )

    @pytest.mark.parametrize(
        "addr",
        [
            "https://example.org/cases/case-001/participants",
            "https://example.org/cases/case-001",
            "https://remote.example/users/alice",
            "https://remote.example/u/alice",
        ],
    )
    def test_a_collection_or_unfamiliar_layout_is_unresolvable(self, addr):
        """A remote node's layout is not this node's to interpret."""
        assert _names_an_individual_actor(addr) is False

    @pytest.mark.parametrize("empty", ["", None])
    def test_an_absent_address_names_nobody(self, empty):
        assert _names_an_individual_actor(empty) is False

    def test_an_activity_addressed_only_to_public_is_accepted(self):
        """The branch that matters at the route level, not just the predicate."""
        activity = as_Create(
            actor=_OTHER_ACTOR_URI, object_=as_Note(content="x")
        )
        activity.to = "https://www.w3.org/ns/activitystreams#Public"
        assert _activity_addressed_to(activity, _ACTOR_URI) is True

    def test_an_activity_addressed_to_another_actors_followers_is_accepted(
        self,
    ):
        """Unresolvable, so Liberal Accept — not a refusal."""
        activity = as_Create(
            actor=_OTHER_ACTOR_URI, object_=as_Note(content="x")
        )
        activity.to = f"{_OTHER_ACTOR_URI}/followers"
        assert _activity_addressed_to(activity, _ACTOR_URI) is True

    def test_public_in_the_cc_makes_an_otherwise_refused_activity_acceptable(
        self,
    ):
        """Refusal requires *provable* exclusion of every address.

        ``to: bob`` alone is refused, but adding ``cc: as:Public`` makes the same
        Activity acceptable — one unresolvable address is enough uncertainty to
        accept the whole thing (IE-11-002). That is the right reading rather than
        a hole: ``as:Public`` means "everyone", so alice genuinely *is* addressed.

        Pinned as a pair so the contrast is the assertion. If a future change
        makes refusal the rule for any address naming another individual, this
        test fails and names the policy that changed.
        """
        aimed_at_bob = as_Create(
            actor=_OTHER_ACTOR_URI, object_=as_Note(content="x")
        )
        aimed_at_bob.to = _OTHER_ACTOR_URI
        assert _activity_addressed_to(aimed_at_bob, _ACTOR_URI) is False

        also_public = as_Create(
            actor=_OTHER_ACTOR_URI, object_=as_Note(content="x")
        )
        also_public.to = _OTHER_ACTOR_URI
        also_public.cc = "https://www.w3.org/ns/activitystreams#Public"
        assert _activity_addressed_to(also_public, _ACTOR_URI) is True

    def test_two_named_peers_are_still_refused(self):
        """Every address resolvable and none of them me → refuse (IE-11-001).

        The guard against reading the rule above as "any extra address accepts".
        """
        activity = as_Create(
            actor=_OTHER_ACTOR_URI, object_=as_Note(content="x")
        )
        activity.to = _OTHER_ACTOR_URI
        activity.cc = "https://example.org/actors/carol"
        assert _activity_addressed_to(activity, _ACTOR_URI) is False
