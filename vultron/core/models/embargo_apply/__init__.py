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


"""The one apply function for embargo and consent entries (ADR-0124).

A ledger entry records one AS2 activity with its object, so the number of
entries follows the number of activity/object pairs, not the number of stored
objects an activity changes (ADR-0122, CLP-07-013).  Two kinds of entry change
the embargo part of the case file:

- **A register step.**  The act's own activity carries the whole step: the
  owner's ``Accept(EmbargoEvent)[target=VulnerabilityCase]`` is ``ACTIVATE``, with the
  ``SUPERSEDE`` of the embargo in force; ``Remove(EmbargoEvent)``
  is ``TERMINATE``, with the ``CANCEL`` of every open proposal;
  ``Reject(EmbargoEvent)[target=VulnerabilityCase]`` is ``REJECT``; the ``Invite`` that
  proposes an embargo is ``PROPOSE``; and a threat signal abandoning an open
  proposal with no embargo in force is ``CANCEL``.  :class:`RegisterStep`
  names the step; the register's definition says which entries it moves.
- **A consent row.**  A row belongs to a participant, another object, so each
  row the CASE_MANAGER brings into existence or changes is its own
  CASE_MANAGER activity, ``Create(EmbargoConsent)`` or
  ``Update(EmbargoConsent)``, carrying the row in full
  (:class:`ConsentRowChange`).

:func:`apply_embargo_change` applies one of them to an
:class:`EmbargoCaseFile` and returns the case file after it.  The CASE_MANAGER
and every replica call it, so both make the same checks (EMB-18-006).  It
copies: it writes what the entry carries, or performs the step the entry
names, after checking the starting state the entry implies; it mints no id,
reads no clock, reads no store, and runs no lifecycle logic (CM-23-044).  The
register step keeps ADR-0122's invariants and ADR-0130's EM transition check
after every entry, because it goes through
:func:`~vultron.core.models.embargo_register.apply_register_step`.  EM is never
written: it is derived from the register.  An entry whose starting state does
not match is refused with :class:`~vultron.errors.VultronEntryRefusedError`,
and the inputs are left as they were.
"""

from vultron.core.models.embargo_apply.apply import (
    EmbargoCaseFile,
    apply_embargo_change,
)
from vultron.core.models.embargo_apply.changes import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_apply.replay import (
    case_file_is_past,
    change_is_in_place,
    changed_objects,
)

__all__ = [
    "ConsentRowChange",
    "ConsentRowVerb",
    "EmbargoCaseFile",
    "EmbargoChange",
    "RegisterStep",
    "RegisterStepKind",
    "apply_embargo_change",
    "case_file_is_past",
    "change_is_in_place",
    "changed_objects",
]
