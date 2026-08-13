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

"""Shared helpers for Announce(CaseLedgerEntry) ledger-apply modules.

Provides :func:`_extract_id_from_field`, used by the per-effect modules listed
below. Effect classes live in their own modules (BTND-07-004):

- :mod:`~vultron.core.behaviors.sync.nodes.note_effect` —
  :class:`~vultron.core.behaviors.sync.nodes.note_effect.ApplyNoteFromLedgerNode`
- :mod:`~vultron.core.behaviors.sync.nodes.invite_accept_effect` —
  :class:`~vultron.core.behaviors.sync.nodes.invite_accept_effect.ApplyInviteAcceptFromLedgerNode`
- :mod:`~vultron.core.behaviors.sync.nodes.close_case_effect` —
  :class:`~vultron.core.behaviors.sync.nodes.close_case_effect.ApplyCloseCaseFromLedgerNode`
- :mod:`~vultron.core.behaviors.sync.nodes.participant_status_effect` —
  :class:`~vultron.core.behaviors.sync.nodes.participant_status_effect.ApplyParticipantStatusFromLedgerNode`

Per specs/multi-actor-demo.yaml DEMOMA-07-003 step 3,
specs/sync-ledger-replication.yaml SYNC-02-002.
"""

from __future__ import annotations

from typing import Any


def _extract_id_from_field(value: Any) -> str | None:
    """Return the string ID from an AS2 object field.

    Handles None, bare string, inline dict (``{"id": ...}`` or ``{"id_": ...}``
    form), and object instances with ``id_`` or ``id`` attributes.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return value.get("id") or value.get("id_") or None
    return getattr(value, "id_", None) or getattr(value, "id", None) or None
