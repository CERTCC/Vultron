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
"""A case and its ledger, cut for a projection, for tests (ADR-0219).

:func:`projected_case` holds a value in every case field the public profile
omits and the joined profile includes, each one a distinct string, so a test
can look for it in a rendered document.  :func:`projected_ledger` holds one
entry per act with a CSAF meaning, and one with none.
"""

from datetime import UTC, datetime
from typing import Any

from test.support.embargo_register import register
from test.support.objects import make
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_projection import ProjectingActor
from vultron.core.models.case_reference import CaseReference, CaseReferenceLink
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_item import (
    NoteCategory,
    VulnerabilityItem,
    VulnerabilityItemId,
    VulnerabilityItemNote,
)
from vultron.enums.roles import CVDRole

CASE_ID = "https://coordinator.example.org/cases/projected"
COORDINATOR = "https://coordinator.example.org/actors/coordinator"
VENDOR = "https://vendor.example.org/actors/vendor"
REPORTER = "https://reporter.example.org/actors/reporter"
#: The commit time of the ledger entry at the case's position.
COMMITTED_AT = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
POSITION = LedgerPosition(log_index=7, entry_hash="ab" * 32)
#: The end of the embargo in force, fixed so two cuts of the case agree.
EMBARGO_END = datetime(2099, 1, 1, tzinfo=UTC)

#: A value of each case field the public profile omits and the joined one
#: includes; none may appear in a public projection.
JOINED_ONLY_VALUES = {
    "content": "The coordinator's full write-up of the overflow.",
    "report": "The reporter's private proof of concept.",
    "reporter_name": "Pat Reporter of the private list",
}

PROJECTOR = ProjectingActor(
    id_=COORDINATOR,
    name="Example Coordinator",
    roles=(CVDRole.COORDINATOR, CVDRole.CASE_MANAGER),
)


def _participant(
    actor: str, *roles: CVDRole, name: str, embargo: EmbargoEvent
) -> CaseParticipant:
    participant = make(
        CaseParticipant,
        attributed_to=actor,
        context=CASE_ID,
        case_roles=list(roles),
        name=name,
    )
    participant.write_uninvited_rows([embargo.id_])
    return participant


def projected_case(**fields: Any) -> VulnerabilityCase:
    """A case with a value in every field group of the profile table."""
    embargo = make(EmbargoEvent, context=CASE_ID, end_time=EMBARGO_END)
    defaults: dict[str, Any] = {
        "id_": CASE_ID,
        "attributed_to": COORDINATOR,
        "name": "Widget buffer overflow",
        "summary": "A buffer overflow in the widget parser.",
        "content": JOINED_ONLY_VALUES["content"],
        "stub_summary": "The stub summary an invitee reads",
        "ledger_position": POSITION,
        "vulnerability_items": [
            make(
                VulnerabilityItem,
                context=CASE_ID,
                name="Parser overflow",
                ids=[
                    VulnerabilityItemId.cve("CVE-2026-1234"),
                    VulnerabilityItemId(
                        system_name="Example tracker", identifier="EX-17"
                    ),
                ],
                vul_notes=[
                    VulnerabilityItemNote(
                        category=NoteCategory.DESCRIPTION,
                        content="The parser overflows its buffer.",
                        name="What goes wrong",
                    )
                ],
            )
        ],
        "case_references": [
            make(
                CaseReference,
                context=CASE_ID,
                name="The vendor's bulletin",
                url=CaseReferenceLink(
                    href="https://vendor.example.org/bulletins/17"
                ),
            )
        ],
        "vulnerability_reports": [
            make(
                VulnerabilityReport,
                name="Initial report",
                content=JOINED_ONLY_VALUES["report"],
            )
        ],
        "case_participants": [
            _participant(
                COORDINATOR,
                CVDRole.COORDINATOR,
                name="Example Coordinator",
                embargo=embargo,
            ),
            _participant(
                VENDOR, CVDRole.VENDOR, name="Example Vendor", embargo=embargo
            ),
            _participant(
                REPORTER,
                CVDRole.REPORTER,
                name=JOINED_ONLY_VALUES["reporter_name"],
                embargo=embargo,
            ),
        ],
        "embargo_register": register(active=embargo),
    }
    return make(VulnerabilityCase, **{**defaults, **fields})


def ledger_entry(
    log_index: int,
    semantics: MessageSemantics,
    *,
    actor: str,
    to: list[str] | None = None,
    in_reply_to: str | None = None,
    extra: dict[str, Any] | None = None,
) -> CaseLedgerEntry:
    """A committed entry at *log_index* recording one act of *actor*."""
    act_id = f"https://example.org/activities/{log_index}"
    payload: dict[str, Any] = {
        "id": act_id,
        "type": "Activity",
        "actor": actor,
        "published": f"2026-10-{log_index + 1:02d}T00:00:00Z",
        **({"to": to} if to is not None else {}),
        **({"inReplyTo": in_reply_to} if in_reply_to else {}),
        **(extra or {}),
    }
    return make(
        CaseLedgerEntry,
        context=CASE_ID,
        log_index=log_index,
        log_object_id=act_id,
        semantic_type=semantics.value,
        payload_snapshot=payload,
        prev_log_hash="cd" * 32,
        entry_hash=f"{log_index:02d}" * 32,
        published=COMMITTED_AT,
        received_at=COMMITTED_AT,
    )


#: A value only a ledger payload's ``object`` holds, which no cut may show.
PAYLOAD_ONLY_VALUE = "A proposed embargo end only the payload holds"


def projected_ledger() -> list[CaseLedgerEntry]:
    """One entry per act with a CSAF meaning, in log order, and one entry
    of case bookkeeping with none."""
    return [
        ledger_entry(
            0,
            MessageSemantics.SUBMIT_REPORT,
            actor=REPORTER,
            to=[VENDOR],
            extra={"object": {"content": PAYLOAD_ONLY_VALUE}},
        ),
        ledger_entry(
            1,
            MessageSemantics.VALIDATE_REPORT,
            actor=VENDOR,
            in_reply_to="https://example.org/activities/0",
        ),
        ledger_entry(
            2,
            MessageSemantics.ADD_CASE_STATUS_TO_CASE,
            actor=COORDINATOR,
        ),
        ledger_entry(
            3,
            MessageSemantics.ACTIVATE_EMBARGO_ON_CASE,
            actor=COORDINATOR,
            to=[VENDOR, REPORTER, COORDINATOR],
        ),
    ]
