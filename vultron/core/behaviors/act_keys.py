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

"""The one vocabulary of blackboard keys that carry a per-act value.

A per-act value varies with the act a tree runs for: a case, report, embargo
or actor id, or a carried object (BTND-01-008).  Every such key is named here,
once, with the type and the meaning of its value (BTND-03-022), so every tree
uses the same name for the same input and a reader finds what a key means
without reading the trees that seed it.

Two kinds of key are named:

- :class:`ActKey` — a per-act input a tree declares (BT-25-006).  The
  received-tree and trigger-tree runners seed it from the act's event or
  trigger request, or one lookup node in the tree publishes it (BT-25-007,
  BT-25-009, BT-25-011); see :mod:`vultron.core.behaviors.act_inputs`.
- :class:`RunKey` — a key ``BTBridge`` places on every run: the store, the
  executing actor, the received activity, the ports and the act's instant
  (BT-05-003, BT-17-012).  A tree never declares one; the bridge always
  supplies it.

Every key is a flat top-level key, read through a port remapped to
:attr:`ActKey.path` (``/case_id``), and ``BTBridge.execute_with_setup``
restores it when the run ends (BT-17-007).

**Adding a key.**  Define it below with :func:`_act_key`, which registers it
in :data:`ACT_KEYS`.  Name it for the value, not for the node that reads it,
and reuse an existing key when the value means the same thing.  A key whose
name matches a field or property of a received event or a trigger request is
seeded from that attribute by default
(:func:`vultron.core.behaviors.act_inputs.seeding_declaration`), so state in
the meaning what the attribute must mean for that default to hold.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType

from vultron.core.behaviors.bridge.act_instant import ACT_INSTANT_KEY
from vultron.core.behaviors.chosen_termination import ChosenTermination
from vultron.core.models.actor import CoreActor
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    ThreatSignalTermination,
)

__all__ = [
    "ACT_KEYS",
    "ANNOUNCE_ID",
    "CASE_ACTOR_ID",
    "CASE_ID",
    "CAUSE_ID",
    "EMBARGO",
    "EMBARGO_ID",
    "EMBARGO_PROPOSER_ID",
    "EXPECTED_SENDER_SEQUENCE",
    "FAULT_PUBLISHED",
    "INVITEE_ID",
    "INVITE_ID",
    "NOTE_ID",
    "OBJECT_ID",
    "OFFER_ID",
    "OWNER_PROFILE",
    "PARTICIPANT_ACTOR_ID",
    "PARTICIPANT_ID",
    "PAYLOAD_SNAPSHOT",
    "PROPOSAL_ID",
    "REFUSED_ACTIVITY_ID",
    "REFUSAL_REASON",
    "REFUSED_ENTRY",
    "REPORT_ID",
    "REQUESTING_ACTOR_ID",
    "RUN_KEYS",
    "SENDER_ID",
    "SENDER_PROPOSED_EMBARGO",
    "SENDER_PROPOSED_EMBARGO_DURATION",
    "TERMINATED_AT",
    "TERMINATION",
    "ActKey",
    "RunKey",
    "require_act_key",
    "vocabulary_key",
]


@dataclass(frozen=True)
class _BlackboardKey:
    """A named flat blackboard key with the type and meaning of its value.

    Attributes:
        name: The bare key, e.g. ``"case_id"``.
        value_type: What a value on the key must be an instance of; a union
            such as ``CoreActor | str`` is allowed.
        meaning: What the value is, in one or two sentences.
    """

    name: str
    value_type: type | object
    meaning: str

    @property
    def path(self) -> str:
        """The absolute key a node's port is remapped to, e.g. ``/case_id``."""
        return f"/{self.name}"

    def admits(self, value: object) -> bool:
        """Whether *value* is of this key's :attr:`value_type`."""
        return isinstance(value, self.value_type)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ActKey(_BlackboardKey):
    """A key that carries a per-act value a tree declares (BTND-01-008)."""


@dataclass(frozen=True)
class RunKey(_BlackboardKey):
    """A key ``BTBridge`` places on every run; never declared by a tree."""


_ACT_KEYS: dict[str, ActKey] = {}


def _act_key(name: str, value_type: type | object, meaning: str) -> ActKey:
    """Define the per-act key *name* and register it in :data:`ACT_KEYS`."""
    if name in _ACT_KEYS:
        raise ValueError(f"the act key {name!r} is already defined")
    key = ActKey(name=name, value_type=value_type, meaning=meaning)
    _ACT_KEYS[name] = key
    return key


# --- What the act is about ----------------------------------------------------

CASE_ID = _act_key(
    "case_id",
    str,
    "The id of the case the act is about.",
)
REPORT_ID = _act_key(
    "report_id",
    str,
    "The id of the vulnerability report the act names.",
)
EMBARGO_ID = _act_key(
    "embargo_id",
    str,
    "The id of the embargo event the act names.",
)
OFFER_ID = _act_key(
    "offer_id",
    str,
    "The id of the Offer activity the act answers or names.",
)
INVITE_ID = _act_key(
    "invite_id",
    str,
    "The id of the Invite activity the act answers or names.",
)
PROPOSAL_ID = _act_key(
    "proposal_id",
    str,
    "The id of the proposal (a case proposal, an embargo proposal or a"
    " case-ownership-transfer proposal) the act answers or names.",
)
ANNOUNCE_ID = _act_key(
    "announce_id",
    str,
    "The id of the activity that carried a ledger entry the act answers or"
    " names, such as the Add(CaseLedgerEntry) a replica's processing fault"
    " refers to.",
)
PARTICIPANT_ID = _act_key(
    "participant_id",
    str,
    "The id of the CaseParticipant record the act names.",
)
NOTE_ID = _act_key(
    "note_id",
    str,
    "The id of the note the act adds or removes.",
)
CAUSE_ID = _act_key(
    "cause_id",
    str,
    "The id of what a CASE_MANAGER decision is about: the Invite whose"
    " deadline passed, or the case when the ledger names no Invite.  It"
    " seeds the id of the entry that records the decision, so a re-run"
    " commits the same entry (ID-04-004).",
)
OBJECT_ID = _act_key(
    "object_id",
    str,
    "The id of the object the act carries or names.  Every received event"
    " seeds it; a tree reads a narrower key above when one names the value.",
)

REFUSED_ACTIVITY_ID = _act_key(
    "refused_activity_id",
    str,
    "The id of the activity a refusal notice says the CASE_MANAGER refused:"
    " the one its ``inReplyTo`` names, else its ``object`` (CLP-05-001,"
    " CLP-06-006).",
)

REFUSAL_REASON = _act_key(
    "refusal_reason",
    str,
    "Why the CASE_MANAGER refused the activity a refusal notice names: the"
    " refusing guard's reason, carried as the notice's ``summary``"
    " (CLP-06-006).  Unset when the notice gives none.",
)

REFUSED_ENTRY = _act_key(
    "refused_entry",
    CaseLedgerEntry,
    "The ledger entry a replica's processing fault reports it refused: the"
    " entry the fault's Add(CaseLedgerEntry) carried (SYNC-03-007,"
    " SYNC-16-008).",
)

FAULT_PUBLISHED = _act_key(
    "fault_published",
    datetime,
    "The ``published`` time a replica's processing fault claims, on the"
    " sender's own clock (SYNC-16-008).  Unset when the fault claims none.",
)

EXPECTED_SENDER_SEQUENCE = _act_key(
    "expected_sender_sequence",
    int,
    "The sender sequence number a refusal notice says the CASE_MANAGER"
    " expects next from the executing actor: its"
    " ``expectedSenderSequence`` (SYNC-21-015).  Unset when the notice"
    " names none.",
)

PAYLOAD_SNAPSHOT = _act_key(
    "payload_snapshot",
    dict,
    "The activity a new ledger entry records, as its wire payload verbatim:"
    " the entry's ``payload_snapshot`` (CLP-07-011).  Unset when the commit"
    " has no payload to record.",
)

# --- Who takes part in the act ------------------------------------------------

SENDER_ID = _act_key(
    "sender_id",
    str,
    "The id of the actor who sent the received activity.  Never the"
    " executing actor, which is the ``actor_id`` run key.",
)
INVITEE_ID = _act_key(
    "invitee_id",
    str,
    "The id of the actor an invitation names as its invitee.",
)
PARTICIPANT_ACTOR_ID = _act_key(
    "participant_actor_id",
    str,
    "The id of the actor whose participant record the act names, such as"
    " the actor a Case Owner's removal or reinstatement names; the record is"
    " read from the case's ``actor_participant_index`` (CM-19-003).",
)
CASE_ACTOR_ID = _act_key(
    "case_actor_id",
    str,
    "The id of the CASE_MANAGER actor of the case the act is about, as the"
    " path stage, the manager-role guard, the replay stage and"
    " ``ResolveCaseManagerNode`` publish it.  The one key for that id:"
    " every tree reads the manager from it.",
)
EMBARGO_PROPOSER_ID = _act_key(
    "embargo_proposer_id",
    str,
    "The id of the actor who proposed the embargo the act answers"
    " (CM-24-002).",
)
REQUESTING_ACTOR_ID = _act_key(
    "requesting_actor_id",
    str,
    "The id of the actor whose request the CASE_MANAGER carries out in the"
    " act: the sender of the received request, credited as ``attributedTo``"
    " on what the CASE_MANAGER sends for it (CM-24-001, CM-24-020).  When no"
    " other actor asked, it is unset or names the executing actor itself,"
    " and either credits nobody.  A CASE_MANAGER trigger or cascade leaves"
    " it unset, so it is not ``sender_id``: a cascade inside a received tree"
    " credits no sender.",
)
OWNER_PROFILE = _act_key(
    "owner_profile",
    CoreActor | str,
    "The proposing CASE_OWNER's actor profile carried by a case proposal,"
    " or its id; the only source of the owner's actor default (CP-01-010).",
)

# --- Terms the act carries ----------------------------------------------------

SENDER_PROPOSED_EMBARGO = _act_key(
    "sender_proposed_embargo",
    EmbargoEvent,
    "The embargo terms a Reporter's case proposal carries (EP-04-003).",
)
SENDER_PROPOSED_EMBARGO_DURATION = _act_key(
    "sender_proposed_embargo_duration",
    timedelta,
    "The time left on the Reporter's proposed embargo, measured from the"
    " act's instant (EP-04-003, ADR-0176).",
)

EMBARGO = _act_key(
    "embargo",
    EmbargoEvent,
    "The EmbargoEvent the act carries in full: a received activity's inline"
    " copy (EMB-18-003), or the terms a trigger proposes.",
)
TERMINATED_AT = _act_key(
    "terminated_at",
    datetime,
    "The time a received termination claims: the ``published`` time of the"
    " ``Remove(EmbargoEvent)`` (ADR-0122).",
)

TERMINATION = _act_key(
    "termination",
    EmbargoTermination | ThreatSignalTermination | ChosenTermination,
    "How the act ends the embargo in force, its what and its why"
    " (ADR-0122, EMB-13-005): the termination a received"
    " ``Remove(EmbargoEvent)`` carries, the one a trigger requests, a"
    " threat-signal termination resolved from the case at the write, or the"
    " ``ChosenTermination`` a voluntary termination's reason call-out fills"
    " earlier in the same run, read when the node runs (EMB-14-001).",
)

#: Every per-act key, by name.
ACT_KEYS: Mapping[str, ActKey] = MappingProxyType(_ACT_KEYS)

#: The keys ``BTBridge`` places on every run, by name (BT-05-003, BT-17-012).
RUN_KEYS: Mapping[str, RunKey] = MappingProxyType(
    {
        key.name: key
        for key in (
            RunKey(
                "datalayer",
                object,
                "The executing actor's store (BT-05-002, ADR-0073).",
            ),
            RunKey(
                "actor_id",
                str,
                "The id of the actor the tree runs as (BT-05-003).",
            ),
            RunKey(
                "activity",
                object,
                "The received event a received tree runs for (BT-05-003).",
            ),
            RunKey(
                "trigger_activity_factory",
                object,
                "The port that builds outbound activities (ARCH-01-004).",
            ),
            RunKey(
                "wire_render_port",
                object,
                "The port that renders a core object to wire shape"
                " (ARCH-20-001).",
            ),
            RunKey(
                "sync_port",
                object,
                "The port that fans a ledger entry out (SYNC-02-003).",
            ),
            RunKey(
                "is_leader",
                object,
                "The leadership guard of the run (SYNC-09-003).",
            ),
            RunKey(
                ACT_INSTANT_KEY,
                object,
                "The act's instant (ADR-0176).",
            ),
        )
    }
)


def vocabulary_key(path_or_name: str) -> ActKey | RunKey | None:
    """The vocabulary key named by *path_or_name*, or ``None``.

    Accepts the bare name (``case_id``) or the absolute path (``/case_id``).
    """
    name = path_or_name.removeprefix("/")
    return ACT_KEYS.get(name) or RUN_KEYS.get(name)


def require_act_key(key: object, where: str) -> ActKey:
    """*key*, when it is the vocabulary's own :class:`ActKey` of its name.

    Args:
        key: The key a declaration or a seeder names.
        where: The tree or node, for the message.

    Raises:
        TypeError: *key* is not a key of the vocabulary (BTND-03-022).
    """
    if not isinstance(key, ActKey) or ACT_KEYS.get(key.name) is not key:
        raise TypeError(
            f"{where}: {key!r} is not a key of the act-key vocabulary"
            " (BTND-03-022)"
        )
    return key
