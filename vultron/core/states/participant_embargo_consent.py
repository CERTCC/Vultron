#!/usr/bin/env python
"""Participant Embargo Consent (PEC): one consent row per (participant, embargo).

A participant's consent is not one scalar answering "am I bound?"; it is a
separate answer to each embargo it was asked about (ADR-0120, CM-18).  Each
row — a :class:`~vultron.core.models.embargo_consent.EmbargoConsent` — holds
one of the four states below, and this module owns the transitions between
them.  Whether a participant is *bound* is a lookup of the row for the case's
active embargo; whether it has *lapsed* is derived from the rows and the
active embargo.  Neither is stored.

States
------
INVITED  – Asked about this embargo; no answer yet.
ACCEPTED – Accepted this embargo, explicitly or by containment (EP-05-001).
DECLINED – Explicitly refused this embargo, or withdrew from it (ADR-0093).
EXPIRED  – Invited, and the RSVP deadline passed with no answer (ADR-0118).
           Not a refusal.

A participant with no row for an embargo has not been asked about it.

Transitions (``None`` is "no row yet")
--------------------------------------
INVITE  : None | DECLINED | EXPIRED → INVITED
ACCEPT  : None | INVITED | EXPIRED → ACCEPTED
DECLINE : None | INVITED | ACCEPTED | EXPIRED → DECLINED
EXPIRE  : INVITED → EXPIRED  (RSVP deadline passed, CM-28-014)

``ACCEPTED`` refuses ``INVITE`` and ``DECLINED`` refuses ``ACCEPT``: a
participant that declined is re-invited first (``DECLINED → INVITED``), never
flipped silently.  ``ACCEPT`` and ``DECLINE`` are valid directly from no row for
self-determined embargoes and implicit-consent cases (ADR-0048, CM-14-005).
Whether repeating a trigger is idempotent is the caller's decision (CM-13-005):
:func:`consent_trigger_is_legal` says whether it moves.
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

    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class PEC_Trigger(StrEnum):
    """Triggers for a participant's consent row."""

    # auto() produces lowercase names when stringified.
    INVITE = auto()
    ACCEPT = auto()
    DECLINE = auto()
    EXPIRE = auto()


_S = EmbargoConsentState
_T = PEC_Trigger

#: ``trigger → {source → destination}``; a ``None`` source is "no row yet".
_TRANSITIONS: dict[
    PEC_Trigger, dict[EmbargoConsentState | None, EmbargoConsentState]
] = {
    _T.INVITE: {
        None: _S.INVITED,
        _S.DECLINED: _S.INVITED,
        _S.EXPIRED: _S.INVITED,
    },
    _T.ACCEPT: {
        None: _S.ACCEPTED,
        _S.INVITED: _S.ACCEPTED,
        _S.EXPIRED: _S.ACCEPTED,
    },
    _T.DECLINE: {
        None: _S.DECLINED,
        _S.INVITED: _S.DECLINED,
        _S.ACCEPTED: _S.DECLINED,
        _S.EXPIRED: _S.DECLINED,
    },
    _T.EXPIRE: {_S.INVITED: _S.EXPIRED},
}


def consent_trigger_is_legal(
    current: EmbargoConsentState | None, trigger: PEC_Trigger
) -> bool:
    """True when *trigger* moves a row at *current* (CM-18-003)."""
    return current in _TRANSITIONS[trigger]


def consent_after(
    current: EmbargoConsentState | None, trigger: PEC_Trigger
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
            f"PEC: consent {current if current else 'with no row'} does not"
            f" accept trigger '{trigger}'."
        ) from None
