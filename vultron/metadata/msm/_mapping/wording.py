"""The "Sent by", "Send to" and "Distinguished by" wording of an occasion (MSM-08)."""

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

from __future__ import annotations

import re
from enum import Enum
from typing import Final

from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    SenderEntitlementKind,
    SenderExemption,
    SenderRule,
    in_declaration_order,
)
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.enums.roles import CVDRole
from vultron.semantic_registry._entry import (
    SemanticEntry,
)
from vultron.semantic_registry._occasion import (
    FieldValue,
    Occasion,
    SenderStanding,
    StateContext,
    wire_spelling,
)
from vultron.wire.as2.extractor._pattern import ActivityPattern

# ---------------------------------------------------------------------------
# "Sent by" and "Send to" (MSM-08-005, MSM-08-009, MSM-08-010).
# ---------------------------------------------------------------------------

#: The "Sent by" wording for a use case whose sender is not yet checked.
NOT_YET_CHECKED = "not yet checked"


#: The "Sent by" wording for a use case no sender check applies to (a
#: permanent exemption, ``no_sender_check``).
NO_SENDER_CHECK = "any actor (no sender check applies)"


#: The "Sent by" wording for an entry no received use case handles.  Such an
#: act is internal to the CASE_MANAGER (the role, whichever actor holds it),
#: so no receiver applies a sender rule to it, though the CASE_MANAGER may
#: still commit it to the case ledger as a ledgered activity (ADR-0140 item 5,
#: SE-05-002).
CASE_MANAGER_INTERNAL = "internal to the CASE_MANAGER"


def _words(type_name: str) -> str:
    """``"CaseProposal"`` → ``"case proposal"``."""
    return " ".join(re.findall(r"[A-Z][a-z0-9]*", type_name)).lower()


def _request_words(request: object, entry: SemanticEntry) -> str:
    """Word one request: its object type, and its verb when it is itself an
    activity (``Offer(VulnerabilityCase)`` → "vulnerability case offer").

    Raises:
        ValueError: When *request* names no object type.
    """
    verb = ""
    if isinstance(request, ActivityPattern):
        verb = f" {_words(str(request.activity_))}"
        request = request.object_
    if request is None or isinstance(request, ActivityPattern):
        raise ValueError(
            f"{entry.semantics.name}: the pattern names no object type to"
            " word an addressee from (MSM-08-005)"
        )
    return f"{_words(str(request))}{verb}"


def answered_request(entry: SemanticEntry) -> str:
    """Name the request or object *entry*'s activity answers or changes.

    The name is taken from the object type of the activity being answered
    (MSM-08-010).  ``Accept(CaseProposal)`` answers a case proposal and
    ``Remove(Note)`` changes a note.  When the answered activity is itself
    nested, as in ``Accept(Offer(VulnerabilityCase))``, the request is that
    inner activity, named by its object type and its verb: a vulnerability
    case offer.  An entry whose pattern does not nest the request it answers
    names each request it may answer in ``SemanticEntry.answers``, joined
    with "or": a bootstrap ``Create(VulnerabilityCase)`` answers a case
    proposal or a vulnerability report offer.

    Raises:
        ValueError: When the entry's pattern names no object type.
    """
    if entry.answers:
        return " or ".join(_request_words(r, entry) for r in entry.answers)
    pattern = entry.pattern
    return _request_words(None if pattern is None else pattern.object_, entry)


def _kind_wording(kind: SenderEntitlementKind, entry: SemanticEntry) -> str:
    """The "Sent by" words *kind* declares (MSM-08-010).

    A position held over an object names it from the entry's pattern
    (:func:`answered_request`): ``NAMED_ACTOR`` the request it answers,
    ``AUTHOR`` the object it changes.  A role's wording has no placeholder,
    so the pattern is read only when the wording needs it.
    """
    if "{object}" not in kind.sent_by:
        return kind.sent_by
    return kind.worded(answered_request(entry))


def rule_wording(
    rule: SenderRule, entry: SemanticEntry, addressee: AddresseeSide
) -> str:
    """Word the side of *rule* for *addressee*: its kinds joined with "or".

    Raises:
        ValueError: When the rule states no side for *addressee*, which
            ``SemanticEntry`` already refuses at construction (MSM-08-009).
    """
    side = rule.side(addressee)
    if not side:
        raise ValueError(
            f"{entry.semantics.name}: the sender rule states no side for an"
            f" activity sent to {addressee.send_to} (MSM-08-009)"
        )
    return " or ".join(
        _kind_wording(kind, entry) for kind in in_declaration_order(side)
    )


def _entitlement_wording(
    use_case: type, entry: SemanticEntry, addressee: AddresseeSide
) -> str:
    """Word the sender entitlement *use_case* declares for *addressee*.

    Raises:
        ValueError: When the use case declares no sender entitlement.
    """
    declared: object = getattr(use_case, "sender_entitlement", None)
    match declared:
        case SenderExemption(permanent=True):
            return NO_SENDER_CHECK
        case SenderExemption():
            return NOT_YET_CHECKED
        case SenderRule():
            return rule_wording(declared, entry, addressee)
        case _:
            raise ValueError(
                f"{use_case.__name__} declares no sender_entitlement"
                " (HP-01-007)"
            )


def sent_by(entry: SemanticEntry, occasion: Occasion) -> str:
    """Derive the "Sent by" value of *occasion* on *entry* (MSM-08-005).

    The value is the wording of the side of the sender rule the entry's
    received use case declares that matches the occasion's addressee
    (:func:`rule_wording`), :data:`NOT_YET_CHECKED` for an exemption that
    names the issue owning its rule, :data:`NO_SENDER_CHECK` for a
    permanent one, or :data:`CASE_MANAGER_INTERNAL` for an entry no
    received use case handles.
    The occasion's usual sender roles, when it has any, follow in
    parentheses: "an active participant (usually: vendor)".

    Raises:
        ValueError: When the use case declares no sender entitlement.
    """
    use_case = entry.use_case_class
    wording = (
        CASE_MANAGER_INTERNAL
        if use_case is None
        else _entitlement_wording(use_case, entry, occasion.addressee)
    )
    if not occasion.usual_senders:
        return wording
    usual = ", ".join(_role_words(role) for role in occasion.usual_senders)
    return f"{wording} (usually: {usual})"


#: The two authority roles' names as the glossary spells them (ADR-0088):
#: a usual sender that holds one is named by it, never by a lowercase alias.
_AUTHORITY_ROLE_WORDS: Final[dict[CVDRole, str]] = {
    CVDRole.CASE_OWNER: "Case Owner",
    CVDRole.CASE_MANAGER: "CASE_MANAGER",
}


def _role_words(role: CVDRole) -> str:
    """Name *role* as a usual sender: ``"vendor"``, ``"Case Owner"``."""
    return _AUTHORITY_ROLE_WORDS.get(role, role.value.replace("_", " "))


def send_to(occasion: Occasion) -> str:
    """Derive the "Send to" value of *occasion*: its addressee's declared
    wording (MSM-08-009)."""
    return occasion.addressee.send_to


#: How a state context words a machine whose state is not the case's own
#: ("EM state"): the register status belongs to the embargo the activity
#: names, not to the case (MSM-08-003).
_STATE_CONTEXT_WORDS: Final[dict[type[Enum], str]] = {
    EmbargoRegisterStatus: "register status of the named embargo",
}


def _state_context_words(machine: type[Enum]) -> str:
    """Name what a state context on *machine* reads, e.g. "EM state"."""
    return _STATE_CONTEXT_WORDS.get(machine, f"{machine.__name__} state")


def distinguished_by(entry: SemanticEntry, occasion: Occasion) -> str | None:
    """Render what tells *occasion* on *entry* apart, as markdown, or ``None``.

    A field value reads "`pxaState` = `Pxa`", the field named by its wire
    spelling (:func:`wire_spelling`), as a dotted path when it is read within
    an embedded model ("`caseStatus.pxaState` = `Pxa`"); a state context reads
    "EM state `NONE` or `PROPOSED`", or "register status of the named embargo
    `ACTIVE`" on ``EmbargoRegisterStatus``; a sender standing reads "sender is
    the Case Owner" or "sender is not the Case Owner", worded by its kind
    (:func:`_kind_wording`, MSM-08-010).  Enum members are named, not valued,
    because a composite state such as ``CS_pxa.Pxa`` has no scalar value.
    """
    d = occasion.distinguisher
    if isinstance(d, FieldValue):
        spelling = wire_spelling(d.object_type, d.field, d.within)
        return f"`{spelling}` = `{d.value.name}`"
    if isinstance(d, StateContext):
        states = " or ".join(f"`{state.name}`" for state in d.states)
        return f"{_state_context_words(d.machine)} {states}"
    if isinstance(d, SenderStanding):
        verb = "is" if d.holds else "is not"
        return f"sender {verb} {_kind_wording(d.kind, entry)}"
    return None
