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


"""Driven port for creating and storing trigger-related wire activities.

:class:`TriggerActivityPort` is the interface core trigger use cases and BT
nodes use to create, store, and queue outbound ActivityStreams activities.
Defining the port here keeps ``vultron/core/`` completely free of wire-layer
imports (ARCH-01-001).

Methods return ``(activity_id, activity_json)`` so callers can:

1. Queue the ``activity_id`` to the actor's outbox.
2. Include the ``activity_dict`` in the HTTP response.

Methods that create domain objects (notes, reports, cases) return
``(object_id, object_dict)`` using the same convention.

Methods only used for outbox queueing (no response body needed) return
``str`` (the activity ID alone).

Port direction: **outbound (driven)** — core constructs trigger requests and
the adapter handles wire-format construction, DataLayer persistence, and
returns the serialized result.

See also:
    - ``vultron/adapters/driven/trigger_activity_adapter/`` — adapter
    - ``specs/architecture.yaml`` ARCH-01-001, ARCH-01-004
    - ``vultron/wire/as2/factories/AGENTS.md``
"""

from typing import Protocol

from vultron.core.ports.received_activity_loader import ReceivedActivityLoader

from .cases import TriggerCasesPort
from .embargo import TriggerEmbargoPort
from .fault import TriggerFaultPort
from .invites import TriggerInvitesPort
from .ledger import TriggerLedgerRecordsPort
from .notes import TriggerNotesPort
from .ownership import TriggerOwnershipPort
from .participants import TriggerParticipantsPort
from .proposals import TriggerProposalsPort
from .reports import TriggerReportsPort
from .roles import TriggerRolesPort

__all__ = ["TriggerActivityPort"]


class TriggerActivityPort(
    ReceivedActivityLoader,
    TriggerNotesPort,
    TriggerReportsPort,
    TriggerCasesPort,
    TriggerProposalsPort,
    TriggerInvitesPort,
    TriggerParticipantsPort,
    TriggerRolesPort,
    TriggerLedgerRecordsPort,
    TriggerEmbargoPort,
    TriggerOwnershipPort,
    TriggerFaultPort,
    Protocol,
):
    """Driven port for trigger-related outbound wire activity construction.

    It is also the trigger side's :class:`ReceivedActivityLoader`: a trigger
    that answers a received activity loads it here, from the body the reply
    built through this port will embed (ADR-0149).

    Core trigger use cases and BT nodes call these methods with domain-level
    parameters (string IDs, primitive types) and receive activity IDs and
    serialized dictionaries in return.  The adapter handles all wire-format
    construction and DataLayer persistence.

    All methods that create an activity persist it to the DataLayer and return
    at minimum the activity's ID.  Methods whose results are included in HTTP
    responses also return a serialized ``dict``.
    """
