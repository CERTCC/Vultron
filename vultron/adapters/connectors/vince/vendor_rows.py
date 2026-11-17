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

"""The vendor rows: each vendor's seat, RM and embargo consent (VINCE-PA-02,
VINCE-RM-04 to VINCE-RM-07, VINCE-EM-02)."""

from __future__ import annotations

from datetime import datetime

from vultron.adapters.connectors.vince.acts import Act, Participant
from vultron.adapters.connectors.vince.crosswalk import (
    AFFECTED,
    NOT_AFFECTED,
    VENDOR_STATUSES,
)
from vultron.adapters.connectors.vince.records import (
    VinceVendor,
    VinceVendorVul,
)
from vultron.adapters.connectors.vince.translation import CaseTranslation
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_reading import UntranslatedReason as Reason
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics

_STATUSES = "vendors/vuls"


def vendors(t: CaseTranslation) -> None:
    """VINCE-PA-02, VINCE-RM-04 and VINCE-EM-02, one vendor at a time."""
    for index, vendor in t.items("vendors", VinceVendor):
        source = t.ids.record("vendors", index)
        actor = t.ids.vendor(vendor.vendor)
        if actor in t.participants:
            t.not_translated(
                source,
                "vendor listed more than once on the case",
                Reason.RULE_CONFLICT,
            )
            continue
        at = vendor.date_added
        if at is None:
            t.not_translated(
                source, "vendor with no date_added", Reason.NO_TIME
            )
            continue
        participant = Participant(actor=actor, roles=("vendor",), vendor=True)
        t.claim_org(vendor.vendor, actor)
        t.seat(
            participant,
            vendor.vendor,
            t.ids.coordinator,
            at,
            source,
            ["VINCE-RM-04"],
            ("RECEIVED",),
        )
        consent_at = max(t.case.created, at)
        end = t.embargo_end
        # VINCE-EM-02 needs an embargo in force: a vendor added after
        # VINCE-EM-03 ended it has none to agree to.
        if t.embargo is not None and (end is None or consent_at <= end):
            _consent(t, participant, t.embargo, consent_at, source)


def _consent(
    t: CaseTranslation,
    vendor: Participant,
    embargo: EmbargoEvent,
    at: datetime,
    source: str,
) -> None:
    """VINCE-EM-02: *vendor* accepts the embargo CERT/CC set."""
    invite = VultronActivity(
        id_=t.ids.minted(f"embargo-invite:{vendor.actor}"),
        type_="Invite",
        actor=t.ids.coordinator,
        object_=embargo.id_,
        target=t.case_id,
        published=at,
        updated=at,
    )
    t.act(
        Act(
            at=at,
            semantic_type=MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
            activity_type="Accept",
            actor=vendor.actor,
            object_=invite,
            source_record=source,
            label="embargo-consent",
            rules=["VINCE-EM-02"],
        )
    )


def vendor_statuses(t: CaseTranslation) -> None:
    """VINCE-RM-05 to VINCE-RM-07, from each vendor's per-vul statuses.

    A status that is unknown, dated before its vendor was added, undated
    where its row needs a time, or of a vendor not on the case is returned
    untranslated; the rest decide the vendor's RM.  Runs after
    :func:`~.content_rows.vuls`, since VINCE-RM-06 needs every vul.
    """
    usable: dict[str, list[tuple[str, VinceVendorVul]]] = {}
    dropped: set[str] = set()
    for index, row in t.items(_STATUSES, VinceVendorVul):
        source = t.ids.record(_STATUSES, index)
        actor = t.ids.vendor(row.vendor)
        seat = t.seats.get(actor)
        if seat is None:
            t.not_translated(
                source,
                "status of a vendor that is not on the case",
                Reason.NO_COUNTERPART,
            )
        elif problem := _status_problem(row, seat):
            t.not_translated(source, *problem)
            dropped.add(actor)
        else:
            usable.setdefault(actor, []).append((source, row))
    for actor, participant in t.participants.items():
        if participant.vendor:
            _vendor_rm(
                t,
                participant,
                t.seats[actor],
                usable.get(actor, []),
                complete=actor not in dropped,
            )


def _status_problem(
    row: VinceVendorVul, seat: Act
) -> tuple[str, Reason] | None:
    """Why a vendor status of a seated vendor is untranslated, if it is."""
    if row.status not in VENDOR_STATUSES:
        return f"status = {row.status}", Reason.UNKNOWN_VALUE
    if row.statement_date is not None and row.statement_date < seat.at:
        return (
            "statement_date is earlier than the vendor's date_added",
            Reason.RULE_CONFLICT,
        )
    if row.statement_date is None and row.status in (AFFECTED, NOT_AFFECTED):
        return f"status = {row.status} with no statement_date", Reason.NO_TIME
    return None


def _vendor_rm(
    t: CaseTranslation,
    vendor: Participant,
    seat: Act,
    rows: list[tuple[str, VinceVendorVul]],
    *,
    complete: bool,
) -> None:
    """One vendor's RM from its usable per-vul statuses.

    VINCE-RM-06 needs a usable ``Not Affected`` for every vul the case
    lists, so a vendor with a status dropped or a vul unstated is any other
    mix (VINCE-RM-07), as is a vendor with no usable status at all.
    """
    dated = sorted(
        (row.statement_date, source, row.status)
        for source, row in rows
        if row.statement_date is not None
    )
    affected = [d for d in dated if d[2] == AFFECTED]
    if affected:
        at, source, _ = affected[0]
        t.rm_steps(vendor, "ACCEPTED", at, source, ["VINCE-RM-05"], "affected")
    elif (
        rows
        and complete
        and all(row.status == NOT_AFFECTED for _, row in rows)
        and t.vul_names <= {row.vulnerability for _, row in rows}
    ):
        at, source, _ = dated[-1]
        t.rm_steps(
            vendor, "INVALID", at, source, ["VINCE-RM-06"], "not-affected"
        )
    else:
        # VINCE-RM-07 writes no entry: its inference names the Received
        # entry VINCE-RM-04 wrote for the vendor.
        seat.rules.append("VINCE-RM-07")


__all__ = ["vendor_statuses", "vendors"]
