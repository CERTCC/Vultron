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

"""The embargo register: one entry for every embargo proposed on a case.

``VulnerabilityCase.embargo_register`` is append-only (ADR-0122): an entry is
added by ``PROPOSE`` and changes status by the other triggers of
:mod:`vultron.core.states.embargo_register`, and is never removed.  Every
change is a **step** — the whole change one protocol event causes — and
:func:`apply_register_step` checks the step's triggers together against the
register invariants, so ``TERMINATE`` and the ``CANCEL`` of every open
proposal, or ``ACTIVATE`` and the ``SUPERSEDE`` it implies, are one change.
Each step names one EM trigger (:func:`register_step_em_trigger`), and the EM
derived before and after it must be one of that trigger's moves in
:data:`vultron.core.states.em.EM_TRANSITIONS` (ADR-0130).

The ``*_changes`` builders name the step each protocol event causes, so the
callers say *what happened* and the register decides which entries move.

Grouped by concern (CS-18-005):

- ``entry`` — the register entry and one change to it
- ``step`` — checking and applying one register step (ADR-0130)
- ``builders`` — the step each protocol event causes
"""

from vultron.core.models.embargo_register.builders import (
    activation_changes,
    carry_embargo_inline,
    proposal_changes,
    rejection_changes,
    termination_changes,
)
from vultron.core.models.embargo_register.entry import (
    EmbargoRegisterEntry,
    RegisterChange,
    repeated_ids,
    replaces_violations,
)
from vultron.core.models.embargo_register.step import (
    apply_register_step,
    em_move_violations,
    register_step_em_trigger,
    register_step_is_legal,
)

__all__ = [
    "EmbargoRegisterEntry",
    "carry_embargo_inline",
    "RegisterChange",
    "activation_changes",
    "apply_register_step",
    "em_move_violations",
    "proposal_changes",
    "register_step_em_trigger",
    "rejection_changes",
    "repeated_ids",
    "termination_changes",
]
