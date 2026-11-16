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
"""What each field of a VINCE case response is, to the sanitizer (#6348).

:data:`READS` classifies every field each per-case read's VINCE Comm
serializer (``vinny/serializers.py``) returns, and the constants name the
values the VINCE API itself defines, which the sanitizer keeps
(``vinny/models.py``). A field missing from :data:`READS` is refused
(VSD-02-007).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto

#: ``Case.STATUS_CHOICES`` in ``vinny/models.py``.
CASE_STATUSES = frozenset({"Active", "Inactive"})

#: ``CaseMemberStatus.STATUS_CHOICES``, and the three values
#: ``VendorSerializer.get_status`` returns.
VENDOR_STATUSES = frozenset({"Affected", "Not Affected", "Unknown"})

#: The labels ``Post.get_org_name`` returns in place of an organization.
POST_ORG_LABELS = frozenset(
    {"Coordinator", "Reporter", "VINCE User", "(Removed from case)", "Removed"}
)

#: The suffix ``Post.get_org_name`` adds to the organization of an author
#: no longer in it.
INACTIVE_SUFFIX = " (Inactive User)"

#: The name and email ``PostSerializer.get_author`` gives a removed author.
REMOVED_AUTHOR_NAME = "User removed"
REMOVED_AUTHOR_EMAIL = "unknown@example.com"

#: Every enumerated value the VINCE API defines, which the sanitizer keeps.
ENUMERATED_VALUES = (
    CASE_STATUSES
    | VENDOR_STATUSES
    | POST_ORG_LABELS
    | {REMOVED_AUTHOR_NAME, REMOVED_AUTHOR_EMAIL}
)


class Leaf(Enum):
    """How the sanitizer treats one field's value."""

    TEXT = auto()
    TEXT_LIST = auto()
    ORG = auto()
    POST_ORG = auto()
    NAME = auto()
    EMAIL = auto()
    PHONE = auto()
    VUID = auto()
    PK = auto()
    VUL_NAME = auto()
    CVE = auto()
    TIME = auto()
    BOOL = auto()
    COUNT = auto()
    CASE_STATUS = auto()
    VENDOR_STATUS = auto()


@dataclass(frozen=True)
class Obj:
    """An object whose every field is classified."""

    fields: Mapping[str, Leaf | Obj]


@dataclass(frozen=True)
class ListOf:
    """A list of objects of one class."""

    item: Obj


Shape = Leaf | Obj | ListOf

_AUTHOR = Obj(
    {
        "org": Leaf.POST_ORG,
        "active": Leaf.BOOL,
        "name": Leaf.NAME,
        "email": Leaf.EMAIL,
    }
)

#: Each per-case read, in the order the sanitizer reads it, and the class
#: of every field its VINCE Comm serializer (``vinny/serializers.py``)
#: returns. A ``null`` read is one VINCE answered with 404.
READS: Mapping[str, Obj | ListOf] = {
    # CaseSerializer
    "case": Obj(
        {
            "vuid": Leaf.VUID,
            "created": Leaf.TIME,
            "status": Leaf.CASE_STATUS,
            "summary": Leaf.TEXT,
            "title": Leaf.TEXT,
            "due_date": Leaf.TIME,
            "modified": Leaf.TIME,
            "pk": Leaf.PK,
        }
    ),
    # PostSerializer
    "posts": ListOf(
        Obj(
            {
                "created": Leaf.TIME,
                "author": _AUTHOR,
                "pinned": Leaf.BOOL,
                "content": Leaf.TEXT,
            }
        )
    ),
    # OrigReportSerializer
    "report": Obj(
        {
            "vendor_name": Leaf.ORG,
            "product_name": Leaf.TEXT,
            "product_version": Leaf.TEXT,
            "vul_description": Leaf.TEXT,
            "vul_exploit": Leaf.TEXT,
            "vul_impact": Leaf.TEXT,
            "vul_discovery": Leaf.TEXT,
            "vul_public": Leaf.BOOL,
            "public_references": Leaf.TEXT,
            "vul_exploited": Leaf.BOOL,
            "exploit_references": Leaf.TEXT,
            "vul_disclose": Leaf.BOOL,
            "disclosure_plans": Leaf.TEXT,
            "date_submitted": Leaf.TIME,
            "share_release": Leaf.BOOL,
            "contact_name": Leaf.NAME,
            "contact_phone": Leaf.PHONE,
            "contact_email": Leaf.EMAIL,
            "contact_org": Leaf.ORG,
        }
    ),
    # VulSerializer
    "vuls": ListOf(
        Obj(
            {
                "name": Leaf.VUL_NAME,
                "cve": Leaf.CVE,
                "description": Leaf.TEXT,
                "date_added": Leaf.TIME,
            }
        )
    ),
    # VendorSerializer
    "vendors": ListOf(
        Obj(
            {
                "vendor": Leaf.ORG,
                "status": Leaf.VENDOR_STATUS,
                "statement": Leaf.TEXT,
                "references": Leaf.TEXT,
                "date_added": Leaf.TIME,
                "cert_addendum": Leaf.TEXT,
                "statement_date": Leaf.TIME,
            }
        )
    ),
    # VendorStatusSerializer
    "vendors/vuls": ListOf(
        Obj(
            {
                "vulnerability": Leaf.VUL_NAME,
                "vendor": Leaf.ORG,
                "status": Leaf.VENDOR_STATUS,
                "statement": Leaf.TEXT,
                "references": Leaf.TEXT,
                "statement_date": Leaf.TIME,
            }
        )
    ),
    # VulNoteSerializer
    "note": Obj(
        {
            "vuid": Leaf.VUID,
            "title": Leaf.TEXT,
            "content": Leaf.TEXT,
            "references": Leaf.TEXT_LIST,
            "datefirstpublished": Leaf.TIME,
            "dateupdated": Leaf.TIME,
            "published": Leaf.BOOL,
            "revision": Leaf.COUNT,
        }
    ),
}


__all__ = [
    "CASE_STATUSES",
    "ENUMERATED_VALUES",
    "INACTIVE_SUFFIX",
    "Leaf",
    "ListOf",
    "Obj",
    "POST_ORG_LABELS",
    "READS",
    "REMOVED_AUTHOR_EMAIL",
    "REMOVED_AUTHOR_NAME",
    "Shape",
    "VENDOR_STATUSES",
]
