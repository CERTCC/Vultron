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

"""The case's own rows: the case, the report, the opening, the case
status, the closure and the vulnerability note (crosswalk § The case,
§ Participants and roles, § Report management, § Embargo, § Case state)."""

from __future__ import annotations

from vultron.adapters.connectors.vince.acts import RM_PATH, Act, Participant
from vultron.adapters.connectors.vince.crosswalk import (
    CASE_ACTIVE,
    CASE_INACTIVE,
    COORDINATOR_ORG,
)
from vultron.adapters.connectors.vince.records import VinceNote, VinceReport
from vultron.adapters.connectors.vince.translation import CaseTranslation
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_reading import UntranslatedReason as Reason
from vultron.core.models.case_reference import (
    CVE_REFERENCE_TAG_RELS,
    CaseReference,
    CaseReferenceLink,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.embargo_register import TerminationReason

#: The link relation of the case's reference to its VINCE page
#: (VINCE-CA-02, CRD-03-002).
ISSUE_TRACKING_REL = CVE_REFERENCE_TAG_RELS["issue-tracking"]

#: The roles VINCE-PA-01 gives CERT/CC.
COORDINATOR_ROLES = ("coordinator", "case_owner", "case_manager")

#: The public state VINCE-CS-04 states: P.  CERT/CC states no X or A,
#: since VINCE-CS-02 and VINCE-CS-03 are the Reporter's own statements.
PUBLISHED_PXA = "Pxa"


def coordinator_seat(t: CaseTranslation) -> None:
    """VINCE-PA-01: CERT/CC, which every other row names, before the case
    entry that seats it (:func:`the_case`)."""
    cert = Participant(actor=t.ids.coordinator, roles=COORDINATOR_ROLES)
    t.participants[cert.actor] = cert
    t.claim_org(COORDINATOR_ORG, cert.actor)


def the_case(t: CaseTranslation) -> None:
    """VINCE-CA-01, VINCE-CA-02 and VINCE-PA-01: the case, its VINCE
    reference and CERT/CC, at ``created``.

    CERT/CC's record carries the statuses it reached by then, the Received
    of VINCE-RM-01, so the case does not seat it again at Start.
    """
    case, at, cert = t.case, t.case.created, t.coordinator
    reference = CaseReference(
        id_=t.ids.minted("reference:vince"),
        url=CaseReferenceLink(href=t.ids.case_url, rel=[ISSUE_TRACKING_REL]),
        name=f"VINCE case VU#{case.vuid}",
        published=at,
        updated=at,
    )
    genesis = VulnerabilityCase(
        id_=t.case_id,
        name=case.title or f"VU#{case.vuid}",
        summary=case.summary,
        attributed_to=cert.actor,
        case_participants=[t.participant_record(cert, COORDINATOR_ORG, at)],
        case_references=[reference],
        case_statuses=[
            t.case_status("pxa", at, "case-status:created", cert.actor)
        ],
        published=at,
        updated=at,
    )
    t.seats[cert.actor] = t.act(
        Act(
            at=at,
            semantic_type=MessageSemantics.CREATE_CASE,
            activity_type="Create",
            actor=cert.actor,
            object_=genesis,
            source_record=t.ids.record("case"),
            label="case",
        )
    )


def report(t: CaseTranslation) -> None:
    """VINCE-PA-03/04, VINCE-RM-01, VINCE-RM-03, VINCE-CS-01 to
    VINCE-CS-03 and VINCE-CT-03, all at ``date_submitted``."""
    source = t.ids.record("report")
    record = t.one("report", VinceReport)
    if record is None:
        return
    at = record.date_submitted
    if at is None:
        t.not_translated(
            source, "report with no date_submitted", Reason.NO_TIME
        )
        return
    shared = record.shares_contact
    reporter = Participant(
        actor=t.ids.reporter(shared=shared), roles=("reporter",)
    )
    t.act(
        Act(
            at=at,
            semantic_type=MessageSemantics.SUBMIT_REPORT,
            activity_type="Offer",
            actor=reporter.actor,
            object_=VulnerabilityReport(
                id_=t.ids.minted("report"),
                name=f"VU#{t.case.vuid} report",
                content=report_content(record),
                attributed_to=reporter.actor,
                published=at,
                updated=at,
            ),
            source_record=source,
            label="report",
            target=t.ids.coordinator,
        )
    )
    if shared:
        name = (
            record.contact_org
            or record.contact_name
            or record.contact_email
            or "reporter"
        )
        if record.contact_org:
            t.claim_org(record.contact_org, reporter.actor)
        rules = ["VINCE-RM-03"]
    else:
        name, rules = "withheld", ["VINCE-PA-04", "VINCE-RM-03"]
    t.seat(
        reporter, name, reporter.actor, at, source, rules, RM_PATH["ACCEPTED"]
    )
    pxa = _stated_pxa(record)
    if pxa != "pxa":
        status = t.status(
            reporter, reporter.rm_at(at), at, "report:pxa", pxa=pxa
        )
        t.add_status(reporter, status, at, source, "report:pxa")
    if at > t.case.created:
        t.not_translated(
            source,
            "date_submitted is later than the case's created",
            Reason.RULE_CONFLICT,
        )
        return
    t.rm_steps(t.coordinator, "RECEIVED", at, source, (), "report:received")


def _stated_pxa(record: VinceReport) -> str:
    """VINCE-CS-01 to VINCE-CS-03: the public state the report form
    states, one letter each, upper-case when raised."""
    return "".join(
        letter.upper() if up else letter
        for letter, up in (
            ("p", record.vul_public is True),
            ("x", record.exploit_references is not None),
            ("a", record.vul_exploited is True),
        )
    )


def report_content(record: VinceReport) -> str | None:
    """VINCE-CT-03: the report's vendor, product and vulnerability
    description fields, one labeled line each."""
    product = " ".join(
        part for part in (record.product_name, record.product_version) if part
    )
    lines = [
        f"{label}: {value}"
        for label, value in (
            ("Vendor", record.vendor_name),
            ("Product", product or None),
            ("Description", record.vul_description),
            ("Exploit", record.vul_exploit),
            ("Impact", record.vul_impact),
            ("Discovery", record.vul_discovery),
        )
        if value
    ]
    return "\n".join(lines) or None


def opening(t: CaseTranslation) -> None:
    """VINCE-RM-02 and VINCE-EM-01, at ``created``."""
    at, source = t.case.created, t.ids.record("case")
    t.rm_steps(
        t.coordinator, "ACCEPTED", at, source, ["VINCE-RM-02"], "opening"
    )
    if t.case.due_date is None:
        return
    t.embargo = EmbargoEvent(
        id_=t.ids.minted("embargo"),
        start_time=None,
        end_time=t.case.due_date,
        context=t.case_id,
        attributed_to=t.ids.coordinator,
        published=at,
        updated=at,
    )
    t.act(
        Act(
            at=at,
            semantic_type=MessageSemantics.ACTIVATE_EMBARGO_ON_CASE,
            activity_type="Add",
            actor=t.ids.coordinator,
            object_=t.embargo,
            source_record=source,
            label="embargo",
            rules=["VINCE-EM-01"],
            target=t.case_id,
        )
    )


def embargo_exit(t: CaseTranslation) -> None:
    """VINCE-EM-03: the embargo ends at ``due_date`` once the time of
    reading the caller supplied has reached it, committed at ``due_date``.
    """
    end = t.embargo_end
    if t.embargo is None or end is None:
        return
    t.act(
        Act(
            at=end,
            semantic_type=MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
            activity_type="Remove",
            actor=t.ids.coordinator,
            object_=t.embargo,
            source_record=t.ids.record("case"),
            label="embargo-exit",
            rules=["VINCE-EM-03"],
            target=t.case_id,
            content=TerminationReason.END_TIME_REACHED.value,
        )
    )


def case_status(t: CaseTranslation) -> None:
    """The case ``status``: ``Active`` adds nothing, ``Inactive`` is
    VINCE-CA-03 (:func:`closure`), any other value is unknown."""
    status = t.case.status
    if status is None or status in (CASE_ACTIVE, CASE_INACTIVE):
        return
    t.not_translated(
        t.ids.record("case"), f"status = {status}", Reason.UNKNOWN_VALUE
    )


def closure(t: CaseTranslation) -> None:
    """VINCE-CA-03: an ``Inactive`` case closes CERT/CC's RM at
    ``modified``, placed once every earlier RM step is known."""
    if t.case.status != CASE_INACTIVE:
        return
    source, at = t.ids.record("case"), t.case.modified
    if at is None:
        t.not_translated(
            source, "status = Inactive with no modified", Reason.NO_TIME
        )
        return
    cert = t.coordinator
    if any(at < when for when, _ in cert.rm):
        t.not_translated(
            source,
            "modified is earlier than CERT/CC's last RM step",
            Reason.RULE_CONFLICT,
        )
        return
    t.rm_steps(cert, "CLOSED", at, source, ["VINCE-CA-03"], "closure")


def note(t: CaseTranslation) -> None:
    """VINCE-CS-04 and VINCE-CT-04 (``revision``, ``dateupdated``)."""
    source = t.ids.record("note")
    record = t.one("note", VinceNote)
    if record is None:
        return
    if record.revision is not None:
        t.not_translated(
            source, f"revision = {record.revision}", Reason.NO_COUNTERPART
        )
    if record.dateupdated is not None:
        t.not_translated(
            source,
            f"dateupdated = {record.dateupdated.isoformat()}",
            Reason.NO_COUNTERPART,
        )
    if not record.published:
        return
    at = record.datefirstpublished
    if at is None:
        t.not_translated(
            source,
            "published = true with no datefirstpublished",
            Reason.NO_TIME,
        )
        return
    if t.before_opening(source, at, "datefirstpublished"):
        return
    cert = t.coordinator
    status = t.status(cert, cert.rm_at(at), at, "published", pxa=PUBLISHED_PXA)
    t.add_status(cert, status, at, source, "published:status")
    # CERT/CC is the Case Manager, so its statement is the case's too.
    t.act(
        Act(
            at=at,
            semantic_type=MessageSemantics.ADD_CASE_STATUS_TO_CASE,
            activity_type="Add",
            actor=cert.actor,
            object_=t.case_status(
                PUBLISHED_PXA, at, "case-status:published", cert.actor
            ),
            source_record=source,
            label="published:case-status",
            target=t.case_id,
        )
    )


__all__ = [
    "COORDINATOR_ROLES",
    "ISSUE_TRACKING_REL",
    "case_status",
    "closure",
    "coordinator_seat",
    "embargo_exit",
    "note",
    "opening",
    "report",
    "report_content",
    "the_case",
]
