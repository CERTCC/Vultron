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

"""Hash refusal: the replica reports it, the CASE_MANAGER logs and self-checks.

Every test here is a strict ``xfail`` for unbuilt behaviour (SYNC-03-007,
SYNC-03-008). Each implementation issue removes the ``xfail`` from the tests
it makes pass, and replaces a probe with a full behaviour test where the probe
only pins a name.
"""

from typing import cast

import pytest

from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models import fault_classes
from vultron.core.models.events.fault import CreateProcessingFaultReceivedEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)
from vultron.wire.as2.factories import create_processing_fault_activity
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

_CASE_ID = "https://example.org/cases/case-hash-mismatch-001"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_STRANGER_ID = "https://example.org/actors/stranger"
_HASH_MISMATCH = "https://certcc.github.io/Vultron/ns/errors/LedgerEntryRefused/HashMismatch"


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-03-007: no hash-mismatch failure class yet. Tracked by #5093.",
)
@pytest.mark.spec("SYNC-03-007")
def test_hash_mismatch_failure_class_is_defined() -> None:
    """The replica's fault names the hash refusal by its own failure class."""
    # getattr until #5093 defines the name, so the type checkers pass now.
    constant = getattr(  # noqa: B009
        fault_classes,
        "VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH",
    )
    assert constant == _HASH_MISMATCH


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-03-008: the fault use case only logs. Tracked by #5094.",
)
@pytest.mark.spec("SYNC-03-008")
def test_hash_mismatch_fault_from_a_non_participant_is_refused() -> None:
    """Only an active participant's hash-mismatch fault is acted on."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    activity = create_processing_fault_activity(
        actor=_STRANGER_ID,
        fault=as_ProcessingFault(
            failure_class=_HASH_MISMATCH,
            in_reply_to=f"{_CASE_ID}/ledger/entries/7/announce",
        ),
        to=[_CASE_ACTOR_ID],
    )

    result = CreateProcessingFaultReceivedUseCase(
        dl, cast(CreateProcessingFaultReceivedEvent, received_event(activity))
    ).execute()

    assert result.disposition == HandlerDisposition.REFUSED
