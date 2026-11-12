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

"""Hand-built case-ledger fixtures for the shapes no committed recording holds.

Each builder writes the camelCase wire spelling a CASE_MANAGER's ledger dump
uses, with only the fields the event history reads.  ``Ledger`` numbers its
entries and gives each a one-second-apart commit stamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vultron.measure.history import CaseEventHistory, case_event_history
from vultron.measure.ledger import (
    LedgerFile,
    LedgerRow,
    case_ledgers_from_files,
)

CASE = "urn:uuid:case-1"
CM = "https://example.org/actors/case-manager"
OWNER = "https://example.org/actors/owner"
REPORTER = "https://example.org/actors/reporter"
VENDOR = "https://example.org/actors/vendor"
VENDOR_2 = "https://example.org/actors/vendor-2"
DEPLOYER = "https://example.org/actors/deployer"
INVITEE = "https://example.org/actors/invitee"
EMBARGO = "urn:uuid:embargo-1"
EMBARGO_2 = "urn:uuid:embargo-2"

#: The default embargo's end time on every hand-built ledger.
EMBARGO_END = "2026-01-04T00:00:00+00:00"


def stamp(second: int) -> str:
    """An ISO 8601 time *second* seconds into the fixture day."""
    minutes, seconds = divmod(second, 60)
    return f"2026-01-01T00:{minutes:02d}:{seconds:02d}+00:00"


def status(
    status_id: str,
    actor: str,
    rm: str,
    *,
    vf: str | None = None,
    d: str | None = None,
    roles: tuple[str, ...] = (),
    case_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A ``ParticipantStatus`` for *actor*."""
    out: dict[str, Any] = {
        "id": status_id,
        "type": "ParticipantStatus",
        "attributedTo": actor,
        "rmState": rm,
        "cvdRole": list(roles),
    }
    if vf is not None:
        out["vfState"] = vf
    if d is not None:
        out["dState"] = d
    if case_status is not None:
        out["caseStatus"] = case_status
    return out


def participant(
    actor: str,
    statuses: list[dict[str, Any]],
    *,
    roles: tuple[str, ...] = (),
    joined: bool = True,
    consents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A ``CaseParticipant`` record for *actor*."""
    return {
        "id": f"{actor}#participant",
        "type": "CaseParticipant",
        "attributedTo": actor,
        "caseRoles": [r.lower() for r in roles],
        "participantStatuses": statuses,
        "embargoConsents": consents or [],
        "joined": joined,
    }


def consent(
    actor: str,
    state: str,
    embargo_id: str = EMBARGO,
    *,
    rsvp_deadline: str | None = None,
) -> dict[str, Any]:
    """An ``EmbargoConsent`` row of *actor* for *embargo_id*."""
    row: dict[str, Any] = {
        "id": f"{actor}#consent#{embargo_id}",
        "type": "EmbargoConsent",
        "attributedTo": actor,
        "embargoId": embargo_id,
        "state": state,
    }
    if rsvp_deadline is not None:
        row["rsvpDeadline"] = rsvp_deadline
    return row


def case_status(
    status_id: str, pxa: str, em: str = "ACTIVE"
) -> dict[str, Any]:
    """A ``CaseStatus`` with public state *pxa*."""
    return {
        "id": status_id,
        "type": "CaseStatus",
        "attributedTo": CM,
        "emState": em,
        "pxaState": pxa,
    }


def embargo(
    embargo_id: str = EMBARGO, end_time: str = EMBARGO_END
) -> dict[str, Any]:
    """An ``EmbargoEvent``."""
    return {
        "id": embargo_id,
        "type": "EmbargoEvent",
        "startTime": stamp(0),
        "endTime": end_time,
    }


@dataclass
class Ledger:
    """A case ledger built one entry at a time, in log-index order."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        semantic_type: str,
        activity: str,
        actor: str,
        obj: object = None,
        *,
        claimed: str | bool | None = True,
        **activity_fields: Any,
    ) -> int:
        """Append an entry; return its log index.

        *claimed* is the activity's ``published``: ``True`` for half a second
        before the commit stamp, ``None`` or ``False`` to leave it out.
        """
        index = len(self.entries)
        payload: dict[str, Any] = {
            "id": f"urn:uuid:activity-{index}",
            "type": activity,
            "actor": actor,
            **activity_fields,
        }
        if obj is not None:
            payload["object"] = obj
        if claimed is True:
            payload["published"] = stamp(index * 2)
        elif isinstance(claimed, str):
            payload["published"] = claimed
        self.entries.append(
            {
                "type": "CaseLedgerEntry",
                "caseId": CASE,
                "logIndex": index,
                "entryHash": f"hash-{index}",
                "semanticType": semantic_type,
                "published": stamp(index * 2 + 1),
                "payloadSnapshot": payload,
            }
        )
        return index

    def genesis(
        self,
        participants: list[dict[str, Any]],
        *,
        pxa: str = "pxa",
        with_embargo: bool = True,
    ) -> int:
        """The CASE_MANAGER's ``Create(VulnerabilityCase)``."""
        case: dict[str, Any] = {
            "id": CASE,
            "type": "VulnerabilityCase",
            "caseParticipants": participants,
            "caseStatuses": [case_status("cs-genesis", pxa)],
            "embargoRegister": (
                [{"embargo": embargo(), "status": "ACTIVE"}]
                if with_embargo
                else []
            ),
        }
        return self.add("create_case", "Create", CM, case)

    def standard_genesis(self) -> int:
        """A genesis seating the CASE_MANAGER at R, V and A, the Case Owner
        at R and the reporter at A, all three signatories of the default
        embargo (CM-14-009, CM-14-012)."""
        return self.genesis(
            [
                participant(
                    CM,
                    [
                        status("cm-r", CM, "RECEIVED"),
                        status("cm-v", CM, "VALID"),
                        status("cm-a", CM, "ACCEPTED"),
                    ],
                    roles=("CASE_MANAGER",),
                    consents=[consent(CM, "AGREED")],
                ),
                participant(
                    OWNER,
                    [status("owner-r", OWNER, "RECEIVED")],
                    roles=("CASE_OWNER",),
                    consents=[consent(OWNER, "AGREED")],
                ),
                participant(
                    REPORTER,
                    [status("reporter-a", REPORTER, "ACCEPTED")],
                    roles=("REPORTER",),
                    consents=[consent(REPORTER, "AGREED")],
                ),
            ]
        )

    def add_status(self, actor: str, new_status: dict[str, Any]) -> int:
        """An ``Add(ParticipantStatus)`` entry by *actor*."""
        return self.add(
            "add_participant_status_to_participant", "Add", actor, new_status
        )

    def seat(self, record: dict[str, Any]) -> int:
        """The CASE_MANAGER's ``Create(CaseParticipant)``."""
        return self.add("create_case_participant", "Create", CM, record)

    def stub_invite(self, invitee: str) -> dict[str, Any]:
        """A stub ``Invite`` of *invitee*, naming the default embargo."""
        return {
            "id": f"urn:uuid:invite-{invitee}",
            "type": "Invite",
            "actor": CM,
            "object": {"id": invitee, "type": "Organization"},
            "target": {"id": CASE, "activeEmbargo": embargo()},
        }

    def history(self) -> CaseEventHistory:
        """The event history of the entries so far."""
        path = Path("hand-built.jsonl")
        ledger_file = LedgerFile(
            path=path,
            rows=[
                LedgerRow(path=path, line=i + 1, data=e)
                for i, e in enumerate(self.entries)
            ],
        )
        read = case_ledgers_from_files([ledger_file])
        return case_event_history(read.cases[CASE])


def seat_vendor(
    ledger: Ledger, actor: str, vf: str, *, deployer: bool = False
) -> int:
    """Seat *actor* as a Vendor (and a Deployer when *deployer*) at *vf*."""
    roles = ("VENDOR", "DEPLOYER") if deployer else ("VENDOR",)
    return ledger.seat(
        participant(
            actor,
            [
                status(
                    f"{actor}-r",
                    actor,
                    "RECEIVED",
                    vf=vf,
                    d="d" if deployer else None,
                    roles=roles,
                )
            ],
            roles=roles,
        )
    )


def publish(ledger: Ledger, pxa: str) -> int:
    """The CASE_MANAGER adopts public state *pxa*."""
    return ledger.add(
        "add_case_status_to_case", "Add", CM, case_status(f"cs-{pxa}", pxa)
    )
