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

"""Read a stub Invite's case preview as it travels, in tests (ADR-0217).

The preview carries the embargo in force as the one entry of its
``embargoRegister`` and the case's EM state in the last item of its
``caseStatuses`` (CM-17-002, CM-17-013).  These read both from the wire
JSON, so a test asserts what the invitee is sent.
"""

from typing import Any


def wire_preview(invite: dict[str, Any]) -> dict[str, Any]:
    """The case preview a stub Invite's JSON carries."""
    preview = invite["object"]["preview"]
    assert isinstance(preview, dict), preview
    return preview


def in_force_embargo(preview: dict[str, Any]) -> dict[str, Any] | None:
    """The embargo of *preview*'s in-force register entry, or ``None``.

    The register a preview carries holds that entry alone (CM-17-014), so a
    second entry is a failure, not a choice.
    """
    register = preview.get("embargoRegister")
    if register is None:
        return None
    (entry,) = register
    assert entry["status"] == "ACTIVE", entry
    embargo = entry["embargo"]
    assert isinstance(embargo, dict), (
        "the preview carries the embargo whole (CM-17-011)"
    )
    return embargo


def current_em_state(preview: dict[str, Any]) -> str | None:
    """The EM state of *preview*'s current status, or ``None``."""
    statuses = preview.get("caseStatuses")
    if not statuses:
        return None
    state = statuses[-1].get("emState")
    return state if isinstance(state, str) else None
