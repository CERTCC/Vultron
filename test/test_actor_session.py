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

"""Unit tests for :class:`vultron.demo.actor_session.ActorSession`."""

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.actor_session import (
    ActivityResult,
    ActorSession,
    NoteResult,
    SyncLogEntryResult,
)
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_BASE = "http://vendor:7999/api/v2"
_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
_CASE_ID = "http://case-actor:7999/api/v2/VulnerabilityCases/abc"


def _session(base_url: str = _BASE, actor_id: str = _ACTOR_ID) -> ActorSession:
    return ActorSession(
        client=DataLayerClient(base_url=base_url),
        actor=as_Actor(id_=actor_id),
    )


def _case() -> as_VulnerabilityCase:
    return as_VulnerabilityCase(id_=_CASE_ID)


# -- construction / authority (DEMOMA-26-002) ----------------------------


def test_is_frozen():
    session = _session()
    with pytest.raises(dataclasses.FrozenInstanceError):
        session.narrate = False  # type: ignore[misc]


def test_post_init_rejects_client_that_does_not_host_actor():
    with pytest.raises(ValueError, match="not hosted by"):
        ActorSession(
            client=DataLayerClient(base_url="http://coordinator:7999/api/v2"),
            actor=as_Actor(id_=_ACTOR_ID),
        )


def test_post_init_accepts_the_actors_own_container():
    # Same authority (scheme+netloc): constructs without raising.
    _session()


def test_post_init_skips_check_for_non_absolute_uris():
    # A bare-slug actor id and a MagicMock client cannot mis-address a
    # container, so the check is skipped rather than raising.
    ActorSession(client=MagicMock(), actor=as_Actor(id_="vendor"))


# -- immutable copies (DEMOMA-26-003) ------------------------------------


def test_with_case_returns_new_instance_and_leaves_receiver_unchanged():
    session = _session()
    case = _case()
    bound = session.with_case(case)
    assert bound is not session
    assert session.case is None
    assert bound.case is case


def test_quiet_returns_new_silent_instance():
    session = _session()
    quiet = session.quiet()
    assert quiet is not session
    assert session.narrate is True
    assert quiet.narrate is False


# -- case-scoped guard (DEMOMA-26-003) -----------------------------------


def test_case_scoped_method_raises_without_a_bound_case():
    session = _session()
    with pytest.raises(ValueError, match="case-scoped"):
        session.engage_case()


# -- posting / result typing --------------------------------------------


def test_verb_posts_expected_behavior_body_and_prefix():
    session = _session().with_case(_case())
    with patch(
        "vultron.demo.actor_session.post_to_trigger", return_value={}
    ) as post:
        session.quiet().notify_fix_ready()
    post.assert_called_once()
    kwargs = post.call_args.kwargs
    assert kwargs["behavior"] == "notify-fix-ready"
    assert kwargs["path_prefix"] == "demo"
    assert kwargs["body"] == {"case_id": _CASE_ID}
    assert kwargs["actor_id"] == _ACTOR_ID


def test_invite_actor_to_case_returns_typed_activity_result():
    session = _session().with_case(_case())
    raw = {
        "activity": {
            "type": "Invite",
            "id": "http://case-actor:7999/api/v2/Invites/1",
            "actor": _ACTOR_ID,
            "object": "http://v2:7999/api/v2/actors/v2",
        },
        "emitting_actor_id": _ACTOR_ID,
    }
    with patch(
        "vultron.demo.actor_session.post_to_trigger", return_value=raw
    ) as post:
        result = session.quiet().invite_actor_to_case(
            invitee_id="http://v2:7999/api/v2/actors/v2",
            roles=[CVDRole.VENDOR],
        )
    assert isinstance(result, ActivityResult)
    assert result.activity.id_ == "http://case-actor:7999/api/v2/Invites/1"
    # roles serialize to their string values in the posted body.
    assert post.call_args.kwargs["body"]["roles"] == ["vendor"]


def test_sync_log_entry_returns_entry_hash():
    session = _session(
        base_url="http://case-actor:7999/api/v2",
        actor_id="http://case-actor:7999/api/v2/actors/case-actor",
    ).with_case(_case())
    raw = {"entry_hash": "abcd1234", "log_index": 3}
    with patch("vultron.demo.actor_session.post_to_trigger", return_value=raw):
        result = session.quiet().sync_log_entry(
            object_id=_CASE_ID, event_type="close_case"
        )
    assert isinstance(result, SyncLogEntryResult)
    assert result.entry_hash == "abcd1234"
    assert result.log_index == 3


def test_add_note_to_case_returns_note_payload():
    session = _session().with_case(_case())
    raw = {"note": {"id": "http://vendor:7999/api/v2/Notes/1"}}
    with patch("vultron.demo.actor_session.post_to_trigger", return_value=raw):
        result = session.quiet().add_note_to_case(
            note_name="n", note_content="c"
        )
    assert isinstance(result, NoteResult)
    assert result.note == {"id": "http://vendor:7999/api/v2/Notes/1"}


def test_optional_note_omitted_from_body_when_absent():
    session = _session()
    with patch(
        "vultron.demo.actor_session.post_to_trigger", return_value={}
    ) as post:
        session.quiet().validate_report(offer_id="offer-1")
    assert post.call_args.kwargs["body"] == {"offer_id": "offer-1"}
