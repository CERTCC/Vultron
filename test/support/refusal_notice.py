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

"""Read the refusal notice a CASE_MANAGER queued for a refused activity.

When a precondition guard at the CASE_MANAGER refuses an assertion, the
CASE_MANAGER queues one ``Reject`` of it to the asserter (CLP-02-005,
CLP-05-001).  Its id is derived from the CASE_MANAGER and the refused
activity, so a test finds it from those two alone and checks its shape.
"""

from typing import Any

from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence


def refusal_notice_id(manager: str, refused_id: str) -> str:
    """The id of *manager*'s refusal notice for *refused_id* (ID-04-004)."""
    return derived_activity_id("refusal-notice", manager, refused_id)


def assert_refusal_notice(
    dl: CaseOutboxPersistence,
    *,
    manager: str,
    refused_id: str,
    asserter: str,
    reason: str,
) -> dict[str, Any]:
    """Assert *manager* queued one refusal notice of *refused_id*.

    The notice is a ``Reject`` of the refused activity, inline, threaded by
    ``inReplyTo``, addressed to *asserter* alone, with the refusing guard's
    reason in ``summary``; *reason* must appear in it (CLP-05-001).

    Returns:
        The notice's sealed body.
    """
    notice_id = refusal_notice_id(manager, refused_id)
    assert notice_id in dl.outbox_list(), (
        f"no refusal notice of '{refused_id}' queued"
    )
    body = read_sealed_body_dict(dl, notice_id)
    assert body is not None, f"'{notice_id}' was never sealed"
    assert body["type"] == "Reject"
    assert body["actor"] == manager
    assert body["to"] == [asserter]
    assert body["inReplyTo"] == refused_id
    assert body["object"]["id"] == refused_id
    assert reason in body["summary"], body["summary"]
    return body


def assert_no_refusal_notice(
    dl: CaseOutboxPersistence, *, manager: str, refused_id: str
) -> None:
    """Assert *manager* queued no refusal notice of *refused_id*."""
    assert refusal_notice_id(manager, refused_id) not in dl.outbox_list()
