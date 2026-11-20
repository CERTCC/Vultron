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

"""The content rows: vuls and posts (VINCE-CT-01, VINCE-CT-02, and
VINCE-CT-04's ``pinned``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from vultron.adapters.connectors.vince.acts import Act
from vultron.adapters.connectors.vince.records import VincePost, VinceVul
from vultron.adapters.connectors.vince.translation import CaseTranslation
from vultron.core.models.case_reading import UntranslatedReason as Reason
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.note import VultronNote
from vultron.core.models.vulnerability_item import (
    CVE_SYSTEM_NAME,
    VulnerabilityItem,
)

#: The id system a vul's VINCE name is recorded under.
VINCE_ID_SYSTEM = "VINCE"


def vuls(t: CaseTranslation) -> None:
    """VINCE-CT-01: one vulnerability item per vul."""
    names: set[str] = set()
    for index, vul in t.items("vuls", VinceVul):
        source = t.ids.record("vuls", index)
        t.vul_names.add(vul.name)
        if vul.name in names:
            t.not_translated(
                source,
                "vul listed more than once on the case",
                Reason.RULE_CONFLICT,
            )
            continue
        if vul.date_added is None:
            t.not_translated(source, "vul with no date_added", Reason.NO_TIME)
            continue
        if t.before_opening(source, vul.date_added, "date_added"):
            continue
        names.add(vul.name)
        t.act(
            Act(
                at=vul.date_added,
                semantic_type=MessageSemantics.ADD_VULNERABILITY_ITEM_TO_CASE,
                activity_type="Add",
                actor=t.ids.coordinator,
                object_=_item(t, vul, vul.date_added, source),
                source_record=source,
                label=f"vul:{index}",
                target=t.case_id,
            )
        )


def _item(
    t: CaseTranslation, vul: VinceVul, at: datetime, source: str
) -> VulnerabilityItem:
    """*vul* as a vulnerability item; its CVE id, if any, is an ``ids``
    entry with system ``CVE`` before its VINCE id (CM-05-018).  A CVE id the
    item refuses is returned untranslated, and the item kept without it."""
    vince_id = {"systemName": VINCE_ID_SYSTEM, "identifier": vul.name}
    data: dict[str, object] = {
        "id": t.ids.minted(f"vul:{vul.name}"),
        "name": vul.name,
        "ids": [vince_id],
        "vulNotes": (
            [{"category": "description", "content": vul.description}]
            if vul.description
            else []
        ),
        "attributedTo": t.ids.coordinator,
        "published": at,
        "updated": at,
    }
    if vul.cve is None:
        return VulnerabilityItem.model_validate(data)
    cve_id = {"systemName": CVE_SYSTEM_NAME, "identifier": vul.cve}
    try:
        return VulnerabilityItem.model_validate(
            {**data, "ids": [cve_id, vince_id]}
        )
    except ValidationError:
        t.not_translated(source, f"cve = {vul.cve}", Reason.UNKNOWN_VALUE)
        return VulnerabilityItem.model_validate(data)


def posts(t: CaseTranslation) -> None:
    """VINCE-CT-02 and VINCE-CT-04 (``pinned``): one case note per post,
    credited to the participant whose organization wrote it."""
    for index, post in t.items("posts", VincePost):
        source = t.ids.record("posts", index)
        if post.pinned:
            t.not_translated(source, "pinned = true", Reason.NO_COUNTERPART)
        org = post.author.org if post.author else None
        actor = t.orgs.get(org) if org else None
        if org in t.shared_orgs:
            t.not_translated(
                source,
                "post whose author's org names more than one participant",
                Reason.RULE_CONFLICT,
            )
        elif actor is None:
            t.not_translated(
                source,
                "post whose author's org matches no participant",
                Reason.NO_COUNTERPART,
            )
        elif post.content is None:
            t.not_translated(
                source, "post with no content", Reason.NO_COUNTERPART
            )
        elif post.created is None:
            t.not_translated(source, "post with no created", Reason.NO_TIME)
        elif not t.before_opening(source, post.created, "created"):
            t.act(
                Act(
                    at=post.created,
                    semantic_type=MessageSemantics.ADD_NOTE_TO_CASE,
                    activity_type="Add",
                    actor=actor,
                    object_=VultronNote(
                        id_=t.ids.minted(f"post:{index}"),
                        content=post.content,
                        attributed_to=actor,
                        context=t.case_id,
                        published=post.created,
                        updated=post.created,
                    ),
                    source_record=source,
                    label=f"post:{index}",
                    target=t.case_id,
                )
            )


__all__ = ["VINCE_ID_SYSTEM", "posts", "vuls"]
