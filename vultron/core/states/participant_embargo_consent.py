#!/usr/bin/env python
"""Participant Embargo Consent (PEC): one consent row per (participant, embargo).

A participant's consent is not one scalar answering "am I bound?"; it is a
separate answer to each embargo in the case's embargo register (ADR-0122,
CM-18).  Each row — a :class:`~vultron.core.models.embargo_consent.EmbargoConsent`
— holds one of the five states below, and this module owns the transitions
between them.  Every row is written: a participant has one for every register
entry, starting at ``UNINVITED``, so no state is read from a missing row.
Whether a participant is *bound* is a lookup of the row for the register's
``ACTIVE`` entry; whether it has *lapsed* is derived from the rows and the
register.  Neither is a state, and neither is stored.

States
------
UNINVITED – Not asked about this embargo.  The start state.
INVITED   – Asked; no answer yet.  Carries the invitation's RSVP deadline.
AGREED    – Agreed to this embargo: explicitly, as its proposer, by seeding
            (CM-14-003, CM-14-005), or by carry-over (EP-05-001).
DECLINED  – Explicitly refused this embargo, or withdrew from it (ADR-0093).
TIMED_OUT – Invited, and the RSVP deadline passed with no answer (ADR-0118).
            Not a refusal.

Transitions
-----------
INVITE     : UNINVITED | DECLINED | TIMED_OUT → INVITED
AGREE      : UNINVITED | INVITED | TIMED_OUT → AGREED
DECLINE    : UNINVITED | INVITED | AGREED | TIMED_OUT → DECLINED
TIME_OUT   : INVITED → TIMED_OUT  (RSVP deadline passed, CM-28-014)
CARRY_OVER : every state except AGREED → AGREED  (EP-05-001)

``AGREED`` refuses ``INVITE`` and ``DECLINED`` refuses ``AGREE``: a
participant that declined is invited again first, never flipped silently.
``CARRY_OVER`` is the one way past that: the activation of a revision that ends
no later than the embargo it replaces binds every participant that agreed to
the replaced one, a ``DECLINED`` row for the revision included, because
agreeing to N days is agreeing to every shorter period.  Rows for an entry in a
final register status accept no trigger at all; that rule needs the register,
so :meth:`~vultron.core.models.case_participant.CaseParticipant.apply_pec_transition`
applies it.  Whether repeating a trigger is idempotent is the caller's decision
(CM-13-005): :func:`consent_trigger_is_legal` says whether it moves.
"""

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

from enum import StrEnum, auto

from vultron.errors import VultronInvalidStateTransitionError


class EmbargoConsentState(StrEnum):
    """State of one participant's consent to one embargo."""

    UNINVITED = "UNINVITED"
    INVITED = "INVITED"
    AGREED = "AGREED"
    DECLINED = "DECLINED"
    TIMED_OUT = "TIMED_OUT"


class PEC_Trigger(StrEnum):
    """Triggers for a participant's consent row."""

    # auto() produces lowercase names when stringified.
    INVITE = auto()
    AGREE = auto()
    DECLINE = auto()
    TIME_OUT = auto()
    CARRY_OVER = auto()


_S = EmbargoConsentState
_T = PEC_Trigger

#: ``trigger → {source → destination}`` (ADR-0122).
_TRANSITIONS: dict[
    PEC_Trigger, dict[EmbargoConsentState, EmbargoConsentState]
] = {
    _T.INVITE: {
        _S.UNINVITED: _S.INVITED,
        _S.DECLINED: _S.INVITED,
        _S.TIMED_OUT: _S.INVITED,
    },
    _T.AGREE: {
        _S.UNINVITED: _S.AGREED,
        _S.INVITED: _S.AGREED,
        _S.TIMED_OUT: _S.AGREED,
    },
    _T.DECLINE: {
        _S.UNINVITED: _S.DECLINED,
        _S.INVITED: _S.DECLINED,
        _S.AGREED: _S.DECLINED,
        _S.TIMED_OUT: _S.DECLINED,
    },
    _T.TIME_OUT: {_S.INVITED: _S.TIMED_OUT},
    _T.CARRY_OVER: {
        source: _S.AGREED for source in _S if source is not _S.AGREED
    },
}


def consent_trigger_is_legal(
    current: EmbargoConsentState, trigger: PEC_Trigger
) -> bool:
    """True when *trigger* moves a row at *current* (CM-18-003)."""
    return current in _TRANSITIONS[trigger]


def consent_move_is_legal(
    current: EmbargoConsentState, target: EmbargoConsentState
) -> bool:
    """True when some trigger moves a row from *current* to *target* (CM-18-003).

    A replica uses it to apply a row an entry carries only when it moves the
    held row forward, so a stale entry replayed over a seed that is already
    ahead leaves the row alone (the consent counterpart of the RM ratchet,
    RSH-05-007).
    """
    return any(moves.get(current) == target for moves in _TRANSITIONS.values())


def consent_after(
    current: EmbargoConsentState, trigger: PEC_Trigger
) -> EmbargoConsentState:
    """The state *trigger* leaves a row in, starting from *current*.

    Raises:
        VultronInvalidStateTransitionError: *trigger* is not legal from
            *current* (CM-18-003, CM-18-009).
    """
    try:
        return _TRANSITIONS[trigger][current]
    except KeyError:
        raise VultronInvalidStateTransitionError(
            f"PEC: consent {current} does not accept trigger '{trigger}'."
        ) from None
