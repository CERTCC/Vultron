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
"""Per-message encryption `main` does not do yet (ENC-02-002).

A strict ``xfail``: nothing in ``vultron/`` encrypts a message, so the
CASE_MANAGER's outbox hands the emitter the sealed body in cleartext.
The encryption scheme is not chosen yet (ENC-02-002's rationale), and no
actor profile can publish an encryption key (``notes/encryption.md``); both
are #5388. When it lands, the test XPASSes and ``strict=True`` fails the
build, so the builder adds a check against the chosen scheme and the
recipient's published key.
"""

import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole

_MANAGER = "https://example.org/actors/coordinator"
_PARTICIPANT = "https://example.org/actors/vendor"
_CASE_ID = "urn:uuid:per-message-encryption-case"
#: Text only the Invite's case stub carries, so finding it in a delivered
#: body means the body is readable by anyone who holds it. ASCII only, so
#: no serializer's escaping of non-ASCII text can hide it from the check.
_CLEARTEXT = "Security issue 7f3c - details shared after acceptance"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    yield _dl
    _dl.clear_all()
    _dl.close()


def _readable(body: str) -> bool:
    """Whether *body* shows the Invite's cleartext to anyone who holds it.

    An encrypted message can still be a JSON object with a ``type`` (an AS2
    envelope around the ciphertext, #5388), so the check is on content.
    """
    return _CLEARTEXT in body


def test_a_readable_body_is_recognized():
    """The check finds the cleartext, so a failing run is not vacuous."""
    assert _readable(f'{{"type": "Invite", "summary": "{_CLEARTEXT}"}}')
    assert not _readable('{"type": "Note", "content": "eyJhbGciOi..."}')


@pytest.mark.spec("ENC-02-002")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="ENC-02-002: nothing in vultron/ encrypts a message, so the"
    " CASE_MANAGER delivers each one in cleartext. Tracked by #5388.",
)
def test_the_case_manager_encrypts_each_message_to_its_recipient(dl):
    """The CASE_MANAGER's Invite reaches the emitter encrypted, not readable."""
    manager = make(
        CaseParticipant,
        id_=f"{_CASE_ID}/participants/cm",
        attributed_to=_MANAGER,
        case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
    )
    case = make(
        VulnerabilityCase,
        id_=_CASE_ID,
        name="CVE-2026-0099",
        attributed_to=_MANAGER,
        stub_summary=_CLEARTEXT,
        case_participants=[manager],
        actor_participant_index={_MANAGER: str(manager.id_)},
    )
    for obj in (manager, case):
        dl.create(obj)
    activity_id, _ = TriggerActivityAdapter(dl).invite_actor_to_case(
        invitee_id=_PARTICIPANT,
        case_id=_CASE_ID,
        actor=_MANAGER,
        to=[_PARTICIPANT],
    )
    stored = dl.read(activity_id)
    if stored is None or _CLEARTEXT not in stored.model_dump_json():
        pytest.fail("the stored Invite does not carry the case stub's text")
    emitter = AsyncMock()

    asyncio.run(oh.handle_outbox_item(_MANAGER, activity_id, dl, emitter))

    if emitter.emit.call_count != 1:
        pytest.fail(f"the outbox delivered {emitter.emit.call_count} time(s)")
    _, body, recipients = emitter.emit.call_args[0]
    if list(recipients) != [_PARTICIPANT]:
        pytest.fail(f"the Invite went to {recipients}, not the participant")
    assert not _readable(body), (
        "the delivered Invite shows its case stub in cleartext"
    )
