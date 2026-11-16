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
"""The committed VINCE fixture generator (#5961, ADR-0189 rule 4).

Writes one file per synthetic VINCE case into :data:`~.marker.FIXTURE_DIR`,
each carrying the synthetic marker with ``producer`` set to
:data:`~.marker.GENERATOR`. A file holds every per-case read the VINCE case
reader makes, under ``reads`` keyed by the read's path below ``case/<vuid>/``
(``case`` for the case itself)::

    {
      "synthetic": {"producer": "generator"},
      "reads": {"case": {...}, "posts": [...], "report": {...},
                "vuls": [...], "vendors": [...], "vendors/vuls": [...],
                "note": {...} | null}
    }

Each read holds exactly what the VINCE Comm serializer for that path returns
(``vinny/serializers.py``); a ``null`` read is one VINCE answers with 404,
such as the note of a case with no vulnerability note. Every value is
invented here: the case ids sit in a range no VINCE case uses, the CVE ids
in the year 2099, and every address under ``example.com`` or
``example.org``. Nothing here was read from a VINCE instance.

The three cases exercise the VINCE crosswalk rows
(``docs/reference/vince_crosswalk.md``):

- ``999901``, active with an embargo: a shared reporter contact
  (VINCE-PA-03), vendors at Affected (VINCE-RM-05), all Not Affected
  (VINCE-RM-06) and Unknown (VINCE-RM-07), a vul with and one without a CVE
  (VINCE-CT-01), a ``due_date`` (VINCE-EM-01, VINCE-EM-02), and a post whose
  author's organization matches no participant (VINCE-CT-02, no
  counterpart).
- ``999902``, inactive and published: closure (VINCE-CA-03), a withheld
  reporter contact (VINCE-PA-04), the report's P, X and A answers
  (VINCE-CS-01 to VINCE-CS-03), a published note (VINCE-CS-04,
  VINCE-CT-04), no ``due_date``, a pinned post, and a vendor statement dated
  before its vendor was added (rule conflict).
- ``999903``, unknown values: a case ``status`` and a vendor status no row
  names (unknown value, CRD-03-003, CRD-03-004), and a vendor whose
  statuses mix Not Affected and Unknown (VINCE-RM-07).

Usage::

    uv run vince-data generate    # rewrite the generator's fixtures
    uv run vince-data check       # the committed-data check, see .check
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Any

from vultron.metadata.generated_files import serialize_json
from vultron.metadata.vince_data.marker import (
    FIXTURE_DIR,
    GENERATOR,
    marker_for,
)

Json = dict[str, Any]

#: The coordinator's organization name, as VINCE's posts carry it.
COORDINATOR_ORG = "CERT/CC"


def _case(
    vuid: str, *, status: str, due_date: str | None, modified: str
) -> Json:
    return {
        "vuid": vuid,
        "created": "2026-01-05T14:00:00Z",
        "status": status,
        "summary": f"Synthetic case {vuid}: a made-up flaw in a made-up "
        "product, for tests only.",
        "title": f"Synthetic Widget flaw {vuid}",
        "due_date": due_date,
        "modified": modified,
        "pk": int(vuid) - 990000,
    }


def _post(
    org: str, name: str, created: str, content: str, *, pinned: bool = False
) -> Json:
    handle = name.lower().replace(" ", ".")
    return {
        "created": created,
        "author": {
            "org": org,
            "active": True,
            "name": name,
            "email": f"{handle}@example.com",
        },
        "pinned": pinned,
        "content": content,
    }


def _report(*, shared: bool, public: bool, exploited: bool) -> Json:
    report: Json = {
        "vendor_name": "Synthetic Vendor Alpha",
        "product_name": "Synthetic Widget",
        "product_version": "1.0",
        "vul_description": "A made-up overflow in the widget's parser.",
        "vul_exploit": "Send the widget an oversized synthetic header.",
        "vul_impact": "The widget stops.",
        "vul_discovery": "Reading synthetic source code.",
        "vul_public": public,
        "public_references": "https://example.com/advisory" if public else "",
        "vul_exploited": exploited,
        "exploit_references": (
            "https://example.com/exploit-writeup" if exploited else ""
        ),
        "vul_disclose": True,
        "disclosure_plans": "Publish once the vendors are ready.",
        "date_submitted": "2026-01-02T10:00:00Z",
    }
    if shared:
        report |= {
            "share_release": True,
            "contact_name": "Synthetic Reporter",
            "contact_phone": "+1-555-0100",
            "contact_email": "reporter@example.org",
            "contact_org": "Example Research Lab",
        }
    return report


def _vul(vuid: str, number: int, cve: str | None, added: str) -> Json:
    return {
        "name": f"VU#{vuid}.{number}",
        "cve": cve,
        "description": f"Synthetic flaw {number} of case {vuid}.",
        "date_added": added,
    }


def _vendor(name: str, status: str, added: str, stated: str | None) -> Json:
    shared = stated is not None
    return {
        "vendor": name,
        "status": status,
        "statement": f"{name} reviewed the synthetic report."
        if shared
        else None,
        "references": "https://example.com/vendor-notes" if shared else None,
        "date_added": added,
        "cert_addendum": None,
        "statement_date": stated,
    }


def _vendor_vul(vul: str, vendor: str, status: str, stated: str) -> Json:
    shared = status != "Unknown"
    return {
        "vulnerability": vul,
        "vendor": vendor,
        "status": status,
        "statement": f"{vendor} marked {vul} {status}." if shared else "",
        "references": "https://example.com/vendor-notes" if shared else "",
        "statement_date": stated,
    }


def _note(vuid: str) -> Json:
    return {
        "vuid": vuid,
        "title": f"Synthetic Widget flaw {vuid}",
        "content": "A synthetic vulnerability note.",
        "references": ["https://example.com/advisory"],
        "datefirstpublished": "2026-05-01T12:00:00Z",
        "dateupdated": "2026-05-03T12:00:00Z",
        "published": True,
        "revision": 2,
    }


def _active_embargoed() -> Json:
    vuid = "999901"
    one, two = f"VU#{vuid}.1", f"VU#{vuid}.2"
    added = "2026-01-06T09:00:00Z"
    return {
        "case": _case(
            vuid,
            status="Active",
            due_date="2026-04-06T00:00:00Z",
            modified="2026-02-10T09:30:00Z",
        ),
        "posts": [
            _post(
                COORDINATOR_ORG,
                "Synthetic Coordinator",
                "2026-01-06T10:00:00Z",
                "Vendors added to the case.",
            ),
            _post(
                "Synthetic Vendor Alpha",
                "Alpha Responder",
                "2026-01-21T08:00:00Z",
                "A fix is in progress.",
            ),
            _post(
                "Synthetic Unlisted Org",
                "Unlisted Person",
                "2026-01-23T08:00:00Z",
                "A post from no participant.",
            ),
        ],
        "report": _report(shared=True, public=False, exploited=False),
        "vuls": [
            _vul(vuid, 1, "CVE-2099-0001", added),
            _vul(vuid, 2, None, added),
        ],
        "vendors": [
            _vendor(
                "Synthetic Vendor Alpha",
                "Affected",
                added,
                "2026-01-20T12:00:00Z",
            ),
            _vendor(
                "Synthetic Vendor Beta",
                "Not Affected",
                added,
                "2026-01-25T12:00:00Z",
            ),
            _vendor("Synthetic Vendor Gamma", "Unknown", added, None),
        ],
        "vendors/vuls": [
            _vendor_vul(
                one,
                "Synthetic Vendor Alpha",
                "Affected",
                "2026-01-20T12:00:00Z",
            ),
            _vendor_vul(two, "Synthetic Vendor Alpha", "Unknown", added),
            _vendor_vul(
                one,
                "Synthetic Vendor Beta",
                "Not Affected",
                "2026-01-22T12:00:00Z",
            ),
            _vendor_vul(
                two,
                "Synthetic Vendor Beta",
                "Not Affected",
                "2026-01-25T12:00:00Z",
            ),
            _vendor_vul(one, "Synthetic Vendor Gamma", "Unknown", added),
            _vendor_vul(two, "Synthetic Vendor Gamma", "Unknown", added),
        ],
        "note": None,
    }


def _inactive_published() -> Json:
    vuid = "999902"
    added = "2026-03-10T09:00:00Z"
    early = "2026-03-01T12:00:00Z"
    return {
        "case": _case(
            vuid,
            status="Inactive",
            due_date=None,
            modified="2026-05-20T16:00:00Z",
        ),
        "posts": [
            _post(
                COORDINATOR_ORG,
                "Synthetic Coordinator",
                "2026-03-10T10:00:00Z",
                "Publication is planned.",
                pinned=True,
            ),
        ],
        "report": _report(shared=False, public=True, exploited=True),
        "vuls": [_vul(vuid, 1, "CVE-2099-0002", added)],
        "vendors": [
            _vendor("Synthetic Vendor Delta", "Affected", added, early),
        ],
        "vendors/vuls": [
            _vendor_vul(
                f"VU#{vuid}.1", "Synthetic Vendor Delta", "Affected", early
            ),
        ],
        "note": _note(vuid),
    }


def _unknown_values() -> Json:
    vuid = "999903"
    one, two = f"VU#{vuid}.1", f"VU#{vuid}.2"
    added = "2026-02-02T09:00:00Z"
    return {
        "case": _case(
            vuid,
            status="Pending",
            due_date="2026-06-01T00:00:00Z",
            modified="2026-02-20T09:30:00Z",
        ),
        "posts": [
            _post(
                "Synthetic Vendor Zeta",
                "Zeta Responder",
                "2026-02-05T08:00:00Z",
                "One product is not affected.",
            ),
        ],
        "report": _report(shared=True, public=False, exploited=False),
        "vuls": [
            _vul(vuid, 1, "CVE-2099-0003", added),
            _vul(vuid, 2, "CVE-2099-0004", added),
        ],
        "vendors": [
            _vendor(
                "Synthetic Vendor Epsilon",
                "Unknown",
                added,
                "2026-02-10T12:00:00Z",
            ),
            _vendor(
                "Synthetic Vendor Zeta",
                "Unknown",
                added,
                "2026-02-05T12:00:00Z",
            ),
        ],
        "vendors/vuls": [
            _vendor_vul(
                one,
                "Synthetic Vendor Epsilon",
                "Fixed",
                "2026-02-10T12:00:00Z",
            ),
            _vendor_vul(
                one,
                "Synthetic Vendor Zeta",
                "Not Affected",
                "2026-02-05T12:00:00Z",
            ),
            _vendor_vul(two, "Synthetic Vendor Zeta", "Unknown", added),
        ],
        "note": None,
    }


#: Each synthetic case's reads, by the file stem it is written under.
SYNTHETIC_CASES: Mapping[str, Json] = {
    "999901-active-embargoed": _active_embargoed(),
    "999902-inactive-published": _inactive_published(),
    "999903-unknown-values": _unknown_values(),
}


def fixture_path(stem: str) -> str:
    """The repository-relative path the case *stem* is written to."""
    return f"{FIXTURE_DIR}/{stem}.json"


@cache
def generated_fixtures() -> Mapping[str, str]:
    """Every fixture file the generator writes: its path and exact text."""
    return {
        fixture_path(stem): serialize_json(
            {**marker_for(GENERATOR), "reads": reads}
        )
        for stem, reads in SYNTHETIC_CASES.items()
    }


def verify_generated(path: str, text: str) -> str | None:
    """``None`` when the generator writes exactly *text* to *path*.

    The generator's :data:`~.marker.ProducerVerifier`: a file marked with the
    generator as producer that a fresh generation does not reproduce byte
    for byte was not written by it, or was edited since (VSD-02-005).
    """
    desired = generated_fixtures().get(path)
    if desired is None:
        return (
            "the generator writes no file at this path; run "
            "`uv run vince-data generate` and remove the file"
        )
    if desired != text:
        return (
            "differs from what the generator writes; run "
            "`uv run vince-data generate` instead of editing it"
        )
    return None


__all__ = [
    "COORDINATOR_ORG",
    "SYNTHETIC_CASES",
    "fixture_path",
    "generated_fixtures",
    "verify_generated",
]
