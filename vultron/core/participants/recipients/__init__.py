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

"""The shared recipient selection for messages about a case (CM-10-007).

Every send that addresses a case's participants picks its recipients here,
so the entitlement check cannot be forgotten at a send site.  Two audiences
exist, and they differ on purpose (ADR-0114 § "Inert and active"):

- :func:`case_content_recipients` — *case content*: ledger entries, case
  announcements, status broadcasts, embargo announcements.  Only **active**
  participants (:meth:`VulnerabilityCase.is_active_participant`, CM-10-004)
  whose closure is not recorded: a participant at RM ``CLOSED`` is sent no
  case content (CM-23-004).
- :func:`ledger_entry_recipients` — the recipients of one ledger entry's
  fan-out: :func:`case_content_recipients`, plus each closed participant the
  entry is *about* — the ``close_case`` entry and the status entries that
  record its own closure (CM-23-031, CM-23-004).
- :func:`inactive_joined_participants` — the joined participants that are
  not active, whose ledger streams are paused and backfilled on admission
  (CM-10-005, CM-10-006): the active embargo withholds them, or they were
  removed (CM-31-001).
- :func:`invitation_recipients` — an Invite addressed to a participant *so
  that* it can consent (the relayed embargo Invite, EP-09-002).  Every
  participant whose RM is not ``CLOSED`` and that is not removed, inert ones
  included (CM-10-007, CM-31-013).
- :func:`embargo_ending_notice_recipients` — the bound signatories the
  ledger fan-out no longer reaches, owed a direct notice when their embargo
  ends or shortens (CM-31-009, CM-31-030).  Not case content (CM-10-007).
- :func:`reporter_introduction_recipients` — the reporters the report
  receiver introduces the CASE_MANAGER to with its own
  ``Create(VulnerabilityCase)`` (CBT-01-001, ADR-0132).  The case-content
  selection narrowed to the ``REPORTER`` role.

Each reads the roster (``actor_participant_index``) and resolves each entry to
its participant record.  A roster entry whose record cannot be read is not
provably entitled, so it is left out and logged at WARNING: leaking case
content to an actor the case cannot vouch for is the failure CM-10-004
exists to prevent.

Roster order is kept, and an unresolvable entry is named, which is why this
walks the index itself rather than :func:`iter_case_participants` (that yields
records only, in no fixed order, and skips what it cannot read silently).
Record precedence matches it: the stored record first, an inline copy only as
the fallback.

The report tree's own ``Create(VulnerabilityCase)``
(``case_creation.CreateCaseActivity``) does not come here:
``case_creation._collect_create_case_addressees`` builds its addressees from the
actor, the report and the offer rather than the roster, and every one of them
is seated at case initialization.

The sender check reads the same records: :func:`may_act_on_case` is the one
predicate behind the ``ACTIVE_PARTICIPANT`` sender standing (CM-23-054), so a
sender may act on a case exactly when it would be sent its content;
:func:`why_may_not_act_on_case` names the ground a refusal by it cites.

This package is the one place in ``vultron/core/`` that lists roster actor
IDs for addressing; ``test/architecture/test_active_participant_recipient_selection.py``
holds every other module to that.
"""

from vultron.core.participants.recipients.beyond_fan_out import (
    awaits_embargo_ending_notice,
    embargo_ending_notice_recipients,
    inactive_joined_participants,
    inert_participants,
    invitation_recipients,
    ledger_stream_paused,
)
from vultron.core.participants.recipients.case_content import (
    case_content_participants,
    case_content_recipients,
    closed_participant_ledger_cutoff,
    entry_records_own_closure,
    is_case_content_recipient,
    ledger_entry_recipients,
    reporter_introduction_recipients,
)
from vultron.core.participants.recipients.roster import (
    closure_recorded,
    listed_participant_record,
)
from vultron.core.participants.recipients.sender_standing import (
    may_act_on_case,
    why_may_not_act_on_case,
)

__all__ = [
    "awaits_embargo_ending_notice",
    "case_content_participants",
    "case_content_recipients",
    "closed_participant_ledger_cutoff",
    "closure_recorded",
    "embargo_ending_notice_recipients",
    "entry_records_own_closure",
    "inactive_joined_participants",
    "inert_participants",
    "invitation_recipients",
    "is_case_content_recipient",
    "ledger_entry_recipients",
    "ledger_stream_paused",
    "listed_participant_record",
    "may_act_on_case",
    "reporter_introduction_recipients",
    "why_may_not_act_on_case",
]
