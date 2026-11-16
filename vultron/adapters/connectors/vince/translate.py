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

"""The VINCE translation: one VINCE case's records, as a case reading.

:func:`translate_case` is a pure function.  It takes the records the VINCE
API serves for one case, keyed by their path below ``case/<vuid>/``, and
returns the :class:`~vultron.core.models.case_reading.CaseReading` the VINCE
crosswalk (``docs/reference/vince_crosswalk.md``) makes of them
(CRD-03-001).  It fetches nothing, stores nothing and reads no clock: every
time an entry carries is a time a VINCE record states (CRD-02-006), and
every id is minted from the VINCE instance and the case, so the same
records always give the same reading.

The ledger is built from core objects, and each entry's payload is that
object's dump (ADR-0191 point 2).  An entry names as its actor the
participant who acted in VINCE (CRD-01-006) and cites the VINCE record it
came from (CRD-01-004), as ``case/<vuid>/<read>`` with ``[<index>]`` for
an item of a list read.  The entries are in time order, ties kept in the
order the crosswalk's tables list their rows.

Participant ids are ``urn:uuid`` values minted from the VINCE instance and
a VINCE name, never the name itself, so an id is safe to log while what a
case holds is not (VSD-01-003).  The translation logs nothing but the case's
VINCE id and counts.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError

from vultron.adapters.connectors.vince.crosswalk import (
    AFFECTED,
    CASE_ACTIVE,
    CASE_INACTIVE,
    COORDINATOR_ORG,
    INFERRED_ROWS,
    NOT_AFFECTED,
    VENDOR_STATUSES,
    VINCE_UNOBSERVABLE,
)
from vultron.adapters.connectors.vince.records import (
    VinceCase,
    VinceNote,
    VincePost,
    VinceReport,
    VinceVendor,
    VinceVendorVul,
    VinceVul,
    parse_case,
    parse_list,
    parse_one,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_reading import (
    CaseReading,
    EntryCitation,
    Inference,
    UntranslatedFact,
    UntranslatedReason,
)
from vultron.core.models.case_reference import (
    CVE_REFERENCE_TAG_RELS,
    CaseReference,
    CaseReferenceLink,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_item import VulnerabilityItem

logger = logging.getLogger(__name__)

#: The link relation of the case's reference to its VINCE page
#: (VINCE-CA-02, CRD-03-002).
ISSUE_TRACKING_REL = CVE_REFERENCE_TAG_RELS["issue-tracking"]

#: The roles VINCE-PA-01 gives CERT/CC.
_COORDINATOR_ROLES = ("coordinator", "case_owner", "case_manager")

#: The RM states a vendor or the coordinator passes through on its way to
#: each state a row sets: a step that skips a state passes through it at the
#: same time (crosswalk § Report management).
_RM_PATH = {
    "RECEIVED": ("RECEIVED",),
    "VALID": ("RECEIVED", "VALID"),
    "ACCEPTED": ("RECEIVED", "VALID", "ACCEPTED"),
    "INVALID": ("RECEIVED", "INVALID"),
    "CLOSED": ("CLOSED",),
}

_Reason = UntranslatedReason


def vince_case_url(comm_url: str, case: VinceCase) -> str:
    """The VINCE web address of *case*, under the VINCE Comm root *comm_url*.

    VINCE Comm serves a case's page at ``case/<pk>/`` (VINCE-CA-02).
    """
    return f"{comm_url.rstrip('/')}/case/{case.pk}/"


def _urn(namespace: UUID, name: str) -> str:
    return f"urn:uuid:{uuid5(namespace, name)}"


@dataclass(frozen=True)
class _Ids:
    """Every id the translation mints, from the instance and the case."""

    comm_url: str
    case: VinceCase

    @property
    def _instance(self) -> UUID:
        return uuid5(NAMESPACE_URL, self.comm_url.rstrip("/"))

    @property
    def case_url(self) -> str:
        return vince_case_url(self.comm_url, self.case)

    @property
    def _case(self) -> UUID:
        return uuid5(NAMESPACE_URL, self.case_url)

    @property
    def case_id(self) -> str:
        return _urn(self._case, "case")

    @property
    def coordinator(self) -> str:
        return _urn(self._instance, "coordinator")

    def vendor(self, name: str) -> str:
        return _urn(self._instance, f"vendor:{name}")

    def reporter(self, report: VinceReport) -> str:
        """The shared contact's id (VINCE-PA-03), or the case's withheld
        reporter (VINCE-PA-04)."""
        if not report.shares_contact:
            return _urn(self._case, "reporter:withheld")
        contact = (
            report.contact_email
            or report.contact_name
            or report.contact_org
            or report.contact_phone
        )
        return _urn(self._instance, f"reporter:{contact}")

    def minted(self, label: str) -> str:
        """The id of the case's object *label* names."""
        return _urn(self._case, label)

    def record(self, read: str, index: int | None = None) -> str:
        """The VINCE record *read* (an item of it when *index* is set)."""
        path = "" if read == "case" else f"{read}/"
        where = f"case/{self.case.vuid}/{path}"
        return where if index is None else f"{where}[{index}]"


@dataclass
class _Act:
    """One act the translation found, before it takes its log index."""

    at: datetime
    semantic_type: str
    activity_type: str
    actor: str
    object_: CoreObject
    source_record: str
    label: str
    rules: list[str] = field(default_factory=list)
    target: str | None = None


@dataclass
class _Participant:
    """A participant the translation seated, and its RM steps so far."""

    actor: str
    seated: _Act | None
    roles: tuple[str, ...]
    vendor: bool = False
    rm: list[tuple[datetime, str]] = field(default_factory=list)
    statuses: list[ParticipantStatus] = field(default_factory=list)

    def rm_at(self, at: datetime) -> str:
        """The participant's RM state at *at*, from the steps so far."""
        reached = [state for when, state in self.rm if when <= at]
        return reached[-1] if reached else "START"


@dataclass
class _Translation:
    """The translation of one case, built row group by row group."""

    ids: _Ids
    reads: Mapping[str, Any]
    acts: list[_Act] = field(default_factory=list)
    untranslated: list[UntranslatedFact] = field(default_factory=list)
    participants: dict[str, _Participant] = field(default_factory=dict)
    #: The participant each organization name on a post credits.
    orgs: dict[str, str] = field(default_factory=dict)
    embargo: EmbargoEvent | None = None

    @property
    def case(self) -> VinceCase:
        return self.ids.case

    @property
    def case_id(self) -> str:
        return self.ids.case_id

    @property
    def coordinator(self) -> _Participant:
        return self.participants[self.ids.coordinator]

    # -- helpers ---------------------------------------------------------

    def _untranslated(
        self, source_record: str, fact: str, reason: UntranslatedReason
    ) -> None:
        self.untranslated.append(
            UntranslatedFact(
                source_record=source_record, fact=fact, reason=reason
            )
        )

    def _act(self, act: _Act) -> _Act:
        self.acts.append(act)
        return act

    def _status(
        self,
        participant: _Participant,
        rm: str,
        at: datetime,
        label: str,
        *,
        pxa: str | None = None,
    ) -> ParticipantStatus:
        """A participant status of *participant* at RM *rm*, as of *at*."""
        data: dict[str, Any] = {
            "id": self.ids.minted(f"status:{participant.actor}:{label}"),
            "context": self.case_id,
            "attributedTo": participant.actor,
            "rmState": rm,
            "cvdRole": [role.upper() for role in participant.roles],
            "published": at,
            "updated": at,
        }
        if participant.vendor:
            # A vendor is aware from its RM Received on (crosswalk § Case
            # state), and the flag stays up on every later status.
            data["vfState"] = "Vf"
        if pxa is not None:
            data["caseStatus"] = self._case_status(
                pxa, at, f"{label}:case-status", participant.actor
            )
        return ParticipantStatus.model_validate(data)

    def _case_status(
        self, pxa: str, at: datetime, label: str, actor: str
    ) -> CaseStatus:
        """A case status reporting public state *pxa* as of *at*."""
        return CaseStatus.model_validate(
            {
                "id": self.ids.minted(label),
                "context": self.case_id,
                "attributedTo": actor,
                "emState": "ACTIVE" if self.embargo is not None else "NONE",
                "pxaState": pxa,
                "published": at,
                "updated": at,
            }
        )

    def _rm_steps(
        self,
        participant: _Participant,
        to: str,
        at: datetime,
        source_record: str,
        rules: Sequence[str],
        label: str,
    ) -> None:
        """Move *participant* to RM *to* at *at*, one entry per state it
        passes through, each by the participant itself."""
        current = participant.rm_at(at)
        path = _RM_PATH[to]
        start = path.index(current) + 1 if current in path else 0
        for rm in path[start:]:
            status = self._status(participant, rm, at, f"{label}:{rm}")
            participant.rm.append((at, rm))
            participant.statuses.append(status)
            self._act(
                _Act(
                    at=at,
                    semantic_type="add_participant_status_to_participant",
                    activity_type="Add",
                    actor=participant.actor,
                    object_=status,
                    source_record=source_record,
                    label=f"{label}:{rm}",
                    rules=list(rules),
                    target=self.ids.minted(f"participant:{participant.actor}"),
                )
            )

    def _seat(
        self,
        participant: _Participant,
        name: str,
        actor: str,
        at: datetime,
        source_record: str,
        rules: Sequence[str],
        statuses: Sequence[str] = (),
    ) -> _Act:
        """The ``Create(CaseParticipant)`` that seats *participant*, carrying
        a status for each RM state in *statuses*."""
        records = []
        for rm in statuses:
            records.append(self._status(participant, rm, at, f"seat:{rm}"))
            participant.rm.append((at, rm))
        participant.statuses.extend(records)
        record = CaseParticipant.model_validate(
            {
                "id": self.ids.minted(f"participant:{participant.actor}"),
                "name": name,
                "context": self.case_id,
                "attributedTo": participant.actor,
                "caseRoles": list(participant.roles),
                "participantStatuses": [
                    status.model_dump(by_alias=True) for status in records
                ],
                "published": at,
                "updated": at,
            }
        )
        act = self._act(
            _Act(
                at=at,
                semantic_type="create_case_participant",
                activity_type="Create",
                actor=actor,
                object_=record,
                source_record=source_record,
                label=f"seat:{participant.actor}",
                rules=list(rules),
                target=self.case_id,
            )
        )
        participant.seated = act
        return act

    # -- the rows, table by table ----------------------------------------

    def coordinator_seat(self) -> None:
        """VINCE-PA-01: CERT/CC, which the case's other rows name, before
        the case entry that seats it (:meth:`the_case`)."""
        cert = _Participant(
            actor=self.ids.coordinator, seated=None, roles=_COORDINATOR_ROLES
        )
        self.participants[cert.actor] = cert
        self.orgs[COORDINATOR_ORG] = cert.actor

    def the_case(self) -> None:
        """VINCE-CA-01, VINCE-CA-02 and VINCE-PA-01: the case, its VINCE
        reference and CERT/CC, at ``created``.

        CERT/CC's record carries the statuses it reached by then, the
        Received of VINCE-RM-01, so the case does not seat it again at
        Start.  VINCE-CA-03 is placed by :meth:`closure`, once every earlier
        RM step is known.
        """
        case, at, cert = self.case, self.case.created, self.coordinator
        reference = CaseReference(
            id_=self.ids.minted("reference:vince"),
            url=CaseReferenceLink(
                href=self.ids.case_url, rel=[ISSUE_TRACKING_REL]
            ),
            name=f"VINCE case VU#{case.vuid}",
            published=at,
            updated=at,
        )
        record = CaseParticipant.model_validate(
            {
                "id": self.ids.minted(f"participant:{cert.actor}"),
                "name": COORDINATOR_ORG,
                "context": self.case_id,
                "attributedTo": cert.actor,
                "caseRoles": list(cert.roles),
                "participantStatuses": [
                    status.model_dump(by_alias=True)
                    for status in cert.statuses
                ],
                "published": at,
                "updated": at,
            }
        )
        genesis = VulnerabilityCase(
            id_=self.case_id,
            name=case.title or f"VU#{case.vuid}",
            summary=case.summary,
            attributed_to=cert.actor,
            case_participants=[record],
            case_references=[reference],
            case_statuses=[
                self._case_status("pxa", at, "case-status:created", cert.actor)
            ],
            published=at,
            updated=at,
        )
        cert.seated = self._act(
            _Act(
                at=at,
                semantic_type="create_case",
                activity_type="Create",
                actor=cert.actor,
                object_=genesis,
                source_record=self.ids.record("case"),
                label="case",
            )
        )

    def report(self) -> None:
        """VINCE-PA-03/04, VINCE-RM-01, VINCE-RM-03, VINCE-CS-01 to
        VINCE-CS-03 and VINCE-CT-03, all at ``date_submitted``."""
        source = self.ids.record("report")
        report = parse_one("report", self.reads.get("report"), VinceReport)
        if report is None:
            return
        if isinstance(report, str):
            self._untranslated(source, report, _Reason.UNKNOWN_VALUE)
            return
        at = report.date_submitted
        if at is None:
            self._untranslated(
                source, "report with no date_submitted", _Reason.NO_TIME
            )
            return
        reporter = _Participant(
            actor=self.ids.reporter(report), seated=None, roles=("reporter",)
        )
        self.participants[reporter.actor] = reporter
        self._act(
            _Act(
                at=at,
                semantic_type="submit_report",
                activity_type="Offer",
                actor=reporter.actor,
                object_=VulnerabilityReport(
                    id_=self.ids.minted("report"),
                    name=f"VU#{self.case.vuid} report",
                    content=_report_content(report),
                    attributed_to=reporter.actor,
                    published=at,
                    updated=at,
                ),
                source_record=source,
                label="report",
                target=self.ids.coordinator,
            )
        )
        rules = ["VINCE-RM-03"]
        if report.shares_contact:
            name = report.contact_org or report.contact_name or "reporter"
            if report.contact_org:
                self.orgs.setdefault(report.contact_org, reporter.actor)
        else:
            name = "withheld"
            rules.insert(0, "VINCE-PA-04")
        self._seat(
            reporter,
            name,
            reporter.actor,
            at,
            source,
            rules,
            statuses=_RM_PATH["ACCEPTED"],
        )
        pxa = "".join(
            letter.upper() if up else letter
            for letter, up in (
                ("p", report.vul_public is True),
                ("x", report.exploit_references is not None),
                ("a", report.vul_exploited is True),
            )
        )
        if pxa != "pxa":
            status = self._status(
                reporter, reporter.rm_at(at), at, "report:pxa", pxa=pxa
            )
            self._act(
                _Act(
                    at=at,
                    semantic_type="add_participant_status_to_participant",
                    activity_type="Add",
                    actor=reporter.actor,
                    object_=status,
                    source_record=source,
                    label="report:pxa",
                    target=self.ids.minted(f"participant:{reporter.actor}"),
                )
            )
        if at > self.case.created:
            self._untranslated(
                source,
                "date_submitted is later than the case's created",
                _Reason.RULE_CONFLICT,
            )
            return
        self._rm_steps(
            self.coordinator, "RECEIVED", at, source, (), "report:received"
        )

    def opening(self) -> None:
        """VINCE-RM-02 and VINCE-EM-01, at ``created``."""
        at, source = self.case.created, self.ids.record("case")
        self._rm_steps(
            self.coordinator,
            "ACCEPTED",
            at,
            source,
            ["VINCE-RM-02"],
            "opening",
        )
        if self.case.due_date is None:
            return
        self.embargo = EmbargoEvent(
            id_=self.ids.minted("embargo"),
            start_time=None,
            end_time=self.case.due_date,
            context=self.case_id,
            attributed_to=self.ids.coordinator,
            published=at,
            updated=at,
        )
        self._act(
            _Act(
                at=at,
                semantic_type="activate_embargo_on_case",
                activity_type="Add",
                actor=self.ids.coordinator,
                object_=self.embargo,
                source_record=source,
                label="embargo",
                rules=["VINCE-EM-01"],
                target=self.case_id,
            )
        )

    def status(self) -> None:
        """The case ``status``: ``Active`` adds nothing, ``Inactive`` is
        VINCE-CA-03 (:meth:`closure`), any other value is unknown."""
        status = self.case.status
        if status is None or status in (CASE_ACTIVE, CASE_INACTIVE):
            return
        self._untranslated(
            self.ids.record("case"),
            f"status = {status}",
            _Reason.UNKNOWN_VALUE,
        )

    def vendors(self) -> None:
        """VINCE-PA-02, VINCE-RM-04 and VINCE-EM-02, one vendor at a time."""
        parsed = parse_list("vendors", self.reads.get("vendors"), VinceVendor)
        for index, problem in parsed.problems:
            self._untranslated(
                self.ids.record("vendors", index if index >= 0 else None),
                problem,
                _Reason.UNKNOWN_VALUE,
            )
        for index, vendor in parsed.items:
            source = self.ids.record("vendors", index)
            actor = self.ids.vendor(vendor.vendor)
            if actor in self.participants:
                self._untranslated(
                    source,
                    "vendor listed more than once on the case",
                    _Reason.RULE_CONFLICT,
                )
                continue
            at = vendor.date_added
            if at is None:
                self._untranslated(
                    source, "vendor with no date_added", _Reason.NO_TIME
                )
                continue
            participant = _Participant(
                actor=actor, seated=None, roles=("vendor",), vendor=True
            )
            self.participants[actor] = participant
            self.orgs.setdefault(vendor.vendor, actor)
            self._seat(
                participant,
                vendor.vendor,
                self.ids.coordinator,
                at,
                source,
                ["VINCE-RM-04"],
                statuses=("RECEIVED",),
            )
            if self.embargo is not None:
                self._consent(participant, max(self.case.created, at), source)

    def _consent(
        self, vendor: _Participant, at: datetime, source: str
    ) -> None:
        """VINCE-EM-02: *vendor* accepts the embargo CERT/CC set."""
        assert self.embargo is not None
        invite = VultronActivity(
            id_=self.ids.minted(f"embargo-invite:{vendor.actor}"),
            type_="Invite",
            actor=self.ids.coordinator,
            object_=self.embargo.id_,
            target=self.case_id,
            published=at,
            updated=at,
        )
        self._act(
            _Act(
                at=at,
                semantic_type="accept_invite_to_embargo_on_case",
                activity_type="Accept",
                actor=vendor.actor,
                object_=invite,
                source_record=source,
                label=f"embargo-consent:{vendor.actor}",
                rules=["VINCE-EM-02"],
            )
        )

    def vendor_statuses(self) -> None:
        """VINCE-RM-05 to VINCE-RM-07, from each vendor's per-vul statuses."""
        read = "vendors/vuls"
        parsed = parse_list(read, self.reads.get(read), VinceVendorVul)
        for index, problem in parsed.problems:
            self._untranslated(
                self.ids.record(read, index if index >= 0 else None),
                problem,
                _Reason.UNKNOWN_VALUE,
            )
        usable: dict[str, list[tuple[str, VinceVendorVul]]] = {}
        for index, row in parsed.items:
            source = self.ids.record(read, index)
            vendor = self.participants.get(self.ids.vendor(row.vendor))
            if vendor is None or not vendor.vendor or vendor.seated is None:
                self._untranslated(
                    source,
                    "status of a vendor that is not on the case",
                    _Reason.NO_COUNTERPART,
                )
            elif row.status not in VENDOR_STATUSES:
                self._untranslated(
                    source, f"status = {row.status}", _Reason.UNKNOWN_VALUE
                )
            elif (
                row.statement_date is not None
                and row.statement_date < vendor.seated.at
            ):
                self._untranslated(
                    source,
                    "statement_date is earlier than the vendor's date_added",
                    _Reason.RULE_CONFLICT,
                )
            elif row.statement_date is None and row.status in (
                AFFECTED,
                NOT_AFFECTED,
            ):
                self._untranslated(
                    source,
                    f"status = {row.status} with no statement_date",
                    _Reason.NO_TIME,
                )
            else:
                usable.setdefault(vendor.actor, []).append((source, row))
        for actor, rows in usable.items():
            self._vendor_rm(self.participants[actor], rows)

    def _vendor_rm(
        self, vendor: _Participant, rows: list[tuple[str, VinceVendorVul]]
    ) -> None:
        dated = [
            (row.statement_date, source, row.status)
            for source, row in rows
            if row.statement_date is not None
        ]
        affected = sorted(d for d in dated if d[2] == AFFECTED)
        if affected:
            at, source, _ = affected[0]
            self._rm_steps(
                vendor, "ACCEPTED", at, source, ["VINCE-RM-05"], "affected"
            )
        elif all(row.status == NOT_AFFECTED for _, row in rows):
            at, source, _ = max(dated)
            self._rm_steps(
                vendor,
                "INVALID",
                at,
                source,
                ["VINCE-RM-06"],
                "not-affected",
            )
        else:
            # VINCE-RM-07 writes no entry: its inference names the Received
            # entry VINCE-RM-04 wrote for the vendor.
            assert vendor.seated is not None
            vendor.seated.rules.append("VINCE-RM-07")

    def vuls(self) -> None:
        """VINCE-CT-01: one vulnerability item per vul."""
        parsed = parse_list("vuls", self.reads.get("vuls"), VinceVul)
        for index, problem in parsed.problems:
            self._untranslated(
                self.ids.record("vuls", index if index >= 0 else None),
                problem,
                _Reason.UNKNOWN_VALUE,
            )
        for index, vul in parsed.items:
            source = self.ids.record("vuls", index)
            if vul.date_added is None:
                self._untranslated(
                    source, "vul with no date_added", _Reason.NO_TIME
                )
                continue
            item = self._item(vul, vul.date_added, source)
            self._act(
                _Act(
                    at=vul.date_added,
                    semantic_type="add_vulnerability_item_to_case",
                    activity_type="Add",
                    actor=self.ids.coordinator,
                    object_=item,
                    source_record=source,
                    label=f"vul:{index}",
                    target=self.case_id,
                )
            )

    def _item(
        self, vul: VinceVul, at: datetime, source: str
    ) -> VulnerabilityItem:
        data: dict[str, Any] = {
            "id": self.ids.minted(f"vul:{vul.name}"),
            "title": vul.name,
            "ids": [{"systemName": "VINCE", "text": vul.name}],
            "notes": (
                [{"category": "description", "text": vul.description}]
                if vul.description
                else []
            ),
            "attributedTo": self.ids.coordinator,
            "published": at,
            "updated": at,
        }
        if vul.cve is None:
            return VulnerabilityItem.model_validate(data)
        try:
            return VulnerabilityItem.model_validate({**data, "cve": vul.cve})
        except ValidationError:
            self._untranslated(
                source, f"cve = {vul.cve}", _Reason.UNKNOWN_VALUE
            )
            return VulnerabilityItem.model_validate(data)

    def posts(self) -> None:
        """VINCE-CT-02 and VINCE-CT-04 (``pinned``): one note per post."""
        parsed = parse_list("posts", self.reads.get("posts"), VincePost)
        for index, problem in parsed.problems:
            self._untranslated(
                self.ids.record("posts", index if index >= 0 else None),
                problem,
                _Reason.UNKNOWN_VALUE,
            )
        for index, post in parsed.items:
            source = self.ids.record("posts", index)
            if post.pinned:
                self._untranslated(
                    source, "pinned = true", _Reason.NO_COUNTERPART
                )
            org = post.author.org if post.author else None
            actor = self.orgs.get(org) if org else None
            if actor is None:
                self._untranslated(
                    source,
                    "post whose author's org matches no participant",
                    _Reason.NO_COUNTERPART,
                )
            elif post.content is None:
                self._untranslated(
                    source, "post with no content", _Reason.NO_COUNTERPART
                )
            elif post.created is None:
                self._untranslated(
                    source, "post with no created", _Reason.NO_TIME
                )
            else:
                self._act(
                    _Act(
                        at=post.created,
                        semantic_type="add_note_to_case",
                        activity_type="Add",
                        actor=actor,
                        object_=VultronNote(
                            id_=self.ids.minted(f"post:{index}"),
                            content=post.content,
                            attributed_to=actor,
                            context=self.case_id,
                            published=post.created,
                            updated=post.created,
                        ),
                        source_record=source,
                        label=f"post:{index}",
                        target=self.case_id,
                    )
                )

    def closure(self) -> None:
        """VINCE-CA-03: an ``Inactive`` case closes CERT/CC's RM at
        ``modified``."""
        if self.case.status != CASE_INACTIVE:
            return
        source, at = self.ids.record("case"), self.case.modified
        if at is None:
            self._untranslated(
                source, "status = Inactive with no modified", _Reason.NO_TIME
            )
            return
        cert = self.coordinator
        latest = max(when for when, _ in cert.rm)
        if at < latest:
            self._untranslated(
                source,
                "modified is earlier than CERT/CC's last RM step",
                _Reason.RULE_CONFLICT,
            )
            return
        self._rm_steps(cert, "CLOSED", at, source, ["VINCE-CA-03"], "closure")

    def note(self) -> None:
        """VINCE-CS-04 and VINCE-CT-04 (``revision``, ``dateupdated``)."""
        source = self.ids.record("note")
        note = parse_one("note", self.reads.get("note"), VinceNote)
        if note is None:
            return
        if isinstance(note, str):
            self._untranslated(source, note, _Reason.UNKNOWN_VALUE)
            return
        if note.revision is not None:
            self._untranslated(
                source, f"revision = {note.revision}", _Reason.NO_COUNTERPART
            )
        if note.dateupdated is not None:
            self._untranslated(
                source,
                f"dateupdated = {note.dateupdated.isoformat()}",
                _Reason.NO_COUNTERPART,
            )
        if not note.published:
            return
        at = note.datefirstpublished
        if at is None:
            self._untranslated(
                source,
                "published = true with no datefirstpublished",
                _Reason.NO_TIME,
            )
            return
        cert = self.coordinator
        status = self._status(cert, cert.rm_at(at), at, "published", pxa="Pxa")
        self._act(
            _Act(
                at=at,
                semantic_type="add_participant_status_to_participant",
                activity_type="Add",
                actor=cert.actor,
                object_=status,
                source_record=source,
                label="published:status",
                target=self.ids.minted(f"participant:{cert.actor}"),
            )
        )
        self._act(
            _Act(
                at=at,
                semantic_type="add_case_status_to_case",
                activity_type="Add",
                actor=cert.actor,
                object_=self._case_status(
                    "Pxa", at, "case-status:published", cert.actor
                ),
                source_record=source,
                label="published:case-status",
                target=self.case_id,
            )
        )

    # -- the reading -----------------------------------------------------

    def reading(self) -> CaseReading:
        """The acts in time order, as a case reading."""
        ledger: list[CaseLedgerEntry] = []
        citations: list[EntryCitation] = []
        inferences: list[Inference] = []
        for index, act in enumerate(sorted(self.acts, key=lambda a: a.at)):
            entry = self._entry(index, act)
            ledger.append(entry)
            citations.append(
                EntryCitation(
                    entry_id=entry.id_, source_record=act.source_record
                )
            )
            inferences.extend(
                Inference(
                    entry_id=entry.id_,
                    rule_id=rule,
                    caveat=INFERRED_ROWS[rule],
                )
                for rule in act.rules
            )
        return CaseReading(
            ledger=tuple(ledger),
            citations=tuple(citations),
            inferences=tuple(inferences),
            untranslated=tuple(self.untranslated),
            unobservable=VINCE_UNOBSERVABLE,
        )

    def _entry(self, index: int, act: _Act) -> CaseLedgerEntry:
        activity = VultronActivity(
            id_=self.ids.minted(f"activity:{act.label}"),
            type_=act.activity_type,
            actor=act.actor,
            object_=act.object_,
            target=act.target,
            context=self.case_id,
            published=act.at,
            updated=act.at,
        )
        payload = activity.model_dump(
            by_alias=True, mode="json", exclude_none=True
        )
        return CaseLedgerEntry(
            case_id=self.case_id,
            log_index=index,
            log_object_id=activity.id_,
            semantic_type=act.semantic_type,
            payload_snapshot=payload,
            entry_hash=_content_digest(
                self.case_id, index, act.semantic_type, act.at, payload
            ),
            published=act.at,
            received_at=act.at,
        )


def _content_digest(
    case_id: str,
    log_index: int,
    semantic_type: str,
    at: datetime,
    payload: Mapping[str, Any],
) -> str:
    """The SHA-256 digest, in hex, of what one translated entry says.

    A reading's entries are never committed, so they carry no CASE_MANAGER
    chain hash: the hash chain is the core ledger's, which a connector may
    not use (ARCH-05-002), and ``prev_log_hash`` stays empty.  The digest
    stands in its place, because a reader of the ledger tells two copies of
    an entry apart by their hashes, and two translations of the same records
    give the same digest.
    """
    content = {
        "caseId": case_id,
        "logIndex": log_index,
        "semanticType": semantic_type,
        "published": at.isoformat(),
        "payloadSnapshot": payload,
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _report_content(report: VinceReport) -> str | None:
    """VINCE-CT-03: the report's vendor, product and vulnerability
    description fields, one labeled line each."""
    product = " ".join(
        part for part in (report.product_name, report.product_version) if part
    )
    lines = [
        f"{label}: {value}"
        for label, value in (
            ("Vendor", report.vendor_name),
            ("Product", product or None),
            ("Description", report.vul_description),
            ("Exploit", report.vul_exploit),
            ("Impact", report.vul_impact),
            ("Discovery", report.vul_discovery),
        )
        if value
    ]
    return "\n".join(lines) or None


#: The row groups in the order the crosswalk lists them, which is the order
#: entries that share a time keep.  CERT/CC is seated first because every
#: later row names it, and the report precedes the case because the case
#: carries the RM state the report gave CERT/CC; the closure and the note
#: come last because each reads CERT/CC's RM steps the others wrote.
_STEPS: tuple[Callable[[_Translation], None], ...] = (
    _Translation.coordinator_seat,
    _Translation.report,
    _Translation.the_case,
    _Translation.opening,
    _Translation.status,
    _Translation.vendors,
    _Translation.vendor_statuses,
    _Translation.vuls,
    _Translation.posts,
    _Translation.closure,
    _Translation.note,
)


def translate_case(reads: Mapping[str, Any], *, comm_url: str) -> CaseReading:
    """Translate one VINCE case's records into a case reading (CRD-03-001).

    Args:
        reads: The JSON each per-case VINCE API read returned, keyed by the
            read's path below ``case/<vuid>/``: ``case`` (the case itself),
            ``report``, ``posts``, ``vuls``, ``vendors``, ``vendors/vuls``
            and ``note``.  A ``None`` value is a read VINCE answered with
            404; a missing list read reads as empty.
        comm_url: The VINCE Comm web root the case was read from, such as
            ``https://kb.cert.org/vince/comm`` (the API base without its
            trailing ``/api``).  It gives the case's VINCE URL and scopes
            every minted id.

    Returns:
        The reading: the ledger in time order, a citation per entry, the
        inferences by crosswalk row, the untranslated facts with their
        reasons, and :data:`VINCE_UNOBSERVABLE`.

    Raises:
        VinceCaseRecordsError: The ``case`` read is missing or lacks the
            ``vuid``, ``pk`` or ``created`` time every row needs.
    """
    case = parse_case(reads)
    translation = _Translation(
        ids=_Ids(comm_url=comm_url, case=case), reads=reads
    )
    for step in _STEPS:
        step(translation)
    reading = translation.reading()
    logger.debug(
        "Translated VINCE case %s: %d entries, %d inferences, %d untranslated",
        case.vuid,
        len(reading.ledger),
        len(reading.inferences),
        len(reading.untranslated),
    )
    return reading


__all__ = ["ISSUE_TRACKING_REL", "translate_case", "vince_case_url"]
