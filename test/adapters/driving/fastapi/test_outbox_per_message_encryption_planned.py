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
CASE_MANAGER's outbox hands the emitter the sealed body as readable JSON.
The encryption scheme is not chosen yet (ENC-02-002's rationale), and no
actor profile can publish an encryption key (``notes/encryption.md``); both
are #5388. When it lands, the test XPASSes and ``strict=True`` fails the
build, so the builder replaces the readable-JSON check with one against the
chosen scheme and the recipient's published key.
"""

import asyncio
import json
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_MANAGER = "https://example.org/actors/coordinator"
_PARTICIPANT = "https://example.org/actors/vendor"
_CASE_NAME = "CVE-2026-0099"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    yield _dl
    _dl.clear_all()
    _dl.close()


def _readable_activity(body: str) -> dict[str, object] | None:
    """*body* as a JSON activity anyone holding it can read, else ``None``."""
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) and "type" in parsed else None


def test_a_readable_body_is_recognized():
    """The check finds plaintext, so a failing run is not vacuous."""
    assert _readable_activity('{"type": "Invite"}') == {"type": "Invite"}
    assert _readable_activity("eyJhbGciOiJFQ0RILUVTIn0..") is None


@pytest.mark.spec("ENC-02-002")
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="ENC-02-002: nothing in vultron/ encrypts a message, so the"
    " CASE_MANAGER delivers each one as readable JSON. Tracked by #5388.",
)
def test_the_case_manager_encrypts_each_message_to_its_recipient(dl):
    """The CASE_MANAGER's Invite reaches the emitter encrypted, not readable."""
    case = as_VulnerabilityCase(
        name=_CASE_NAME,
        attributed_to=_MANAGER,
        stub_summary="Security issue — details shared after acceptance",
    )
    dl.create(case)
    activity_id, _ = TriggerActivityAdapter(dl).invite_actor_to_case(
        invitee_id=_PARTICIPANT,
        case_id=case.id_,
        actor=_MANAGER,
        to=[_PARTICIPANT],
    )
    emitter = AsyncMock()

    asyncio.run(oh.handle_outbox_item(_MANAGER, activity_id, dl, emitter))

    if emitter.emit.call_count != 1:
        pytest.fail(f"the outbox delivered {emitter.emit.call_count} time(s)")
    _, body, recipients = emitter.emit.call_args[0]
    if list(recipients) != [_PARTICIPANT]:
        pytest.fail(f"the Invite went to {recipients}, not the participant")
    assert _readable_activity(str(body)) is None, (
        "the delivered body is a readable JSON activity"
    )
