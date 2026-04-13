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
"""Persistable per-peer replication state for SYNC-3/4.

Spec: SYNC-04-001, SYNC-04-002.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from vultron.core.models._helpers import _now_utc
from vultron.core.models.base import VultronObject
from vultron.core.models.case_log import GENESIS_HASH


class VultronReplicationState(VultronObject):
    """Tracks per-peer replication state for the CaseActor log fan-out.

    The ``id_`` is auto-computed as
    ``{case_id}/replication/{url_encoded_peer_id}`` so that the same
    peer always resolves to a stable key in the DataLayer.

    Spec: SYNC-04-001, SYNC-04-002.
    """

    type_: Literal["ReplicationState"] = Field(  # type: ignore[assignment]
        default="ReplicationState",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: str = Field(
        ..., description="URI of the parent VulnerabilityCase"
    )
    peer_id: str = Field(..., description="Full URI of the participant actor")
    last_acknowledged_hash: str = Field(
        default=GENESIS_HASH,
        description=(
            "entry_hash of the last log entry acknowledged by this peer"
        ),
        validation_alias="lastAcknowledgedHash",
        serialization_alias="lastAcknowledgedHash",
    )
    updated_at: datetime = Field(
        default_factory=_now_utc,
        validation_alias="updatedAt",
        serialization_alias="updatedAt",
    )

    @model_validator(mode="after")
    def _set_id(self) -> "VultronReplicationState":
        """Compute ``id_`` deterministically from ``case_id`` and ``peer_id``."""
        slug = urllib.parse.quote(self.peer_id, safe="")
        self.id_ = f"{self.case_id}/replication/{slug}"
        return self
