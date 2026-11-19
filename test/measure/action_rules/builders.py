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

"""Authored-rule builders the action-rule tests share."""

from __future__ import annotations

from typing import Any

import pytest

from vultron.core.scoring.potential_actions import Actions
from vultron.measure.action_rules import ANY_ROLE, AuthoredRule, RulePattern

#: One worker runs every action-rule test.  The first test on a worker pays
#: the cold walks (the scope desiderata, then each one-vendor point) inside
#: its own timeout, about 13 s at idle; grouped, one worker pays it once
#: rather than each worker that draws one of these tests (TB-14-011).
ACTION_RULES_GROUP = pytest.mark.xdist_group("measure-action-rules")


def rule_fields(**fields: Any) -> dict[str, Any]:
    """A valid authored rule's fields, with *fields* replacing them: any
    role, monitoring for attacks, for SA, naming ``D≺P``, carried from no
    source pair."""
    base: dict[str, Any] = {
        "pattern": RulePattern(),
        "roles": ANY_ROLE,
        "action": Actions.MONITOR_FOR_ATTACKS,
        "reason": "SA",
        "desiderata": ("D≺P",),
        "source": None,
    }
    base.update(fields)
    return base


def make_rule(**fields: Any) -> AuthoredRule:
    """The authored rule of :func:`rule_fields`."""
    return AuthoredRule(**rule_fields(**fields))
