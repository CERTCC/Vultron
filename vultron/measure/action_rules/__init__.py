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
"""Action rules across CS, RM, EM and PEC, authored and generated, compared
(ADR-0216).

* :mod:`.model` — one vendor's position, the pattern language, and the
  authored rule with its roles, action and desiderata.
* :mod:`.authored` — the authored table: each ``CS_ACTION_RULES`` pair
  carried over, narrowed where another machine changes what it is.
* :mod:`.verdicts` — each move's band for one vendor, read from move advice:
  for a live case's vendors, and for every valid position of one vendor.
* :mod:`.generated` — those bands grouped into generated rules.
* :mod:`.compare` — the comparison, position by position, and its five
  results.
* :mod:`.report` — the comparison over every valid position of one vendor,
  rule by rule, for the generated docs page.
* :mod:`.pages` — the command that rebuilds the generated docs fragments
  (``uv run action-rules-docs``).

Everything here reads; nothing fires a trigger or writes (CEH-01-002),
except the command of :mod:`.pages`, which writes only the docs fragments.
"""

from vultron.measure.action_rules.authored import (
    NON_VENDOR,
    NOT_THE_OWNER,
    authored_rules,
)
from vultron.measure.action_rules.compare import (
    FLAGGED,
    FORCED_STEP,
    NO_STATE_CHANGE,
    NOT_MEASURED,
    DesideratumShift,
    PointComparison,
    ResultKind,
    RuleResult,
    compare_point,
    compare_points,
    resolve_action,
    rule_move,
)
from vultron.measure.action_rules.generated import (
    ConditionalBranch,
    ConditionalVerdict,
    GeneratedRule,
    PositionKey,
    conditional_verdicts,
    conditionals_from,
    generated_rules,
    group_positions,
    move_role,
    rules_from,
)
from vultron.measure.action_rules.model import (
    ACTION_MOVES,
    ANY_ROLE,
    NO_STATE_ACTIONS,
    SCORED_MACHINES,
    AuthoredRule,
    ConsentReading,
    Machine,
    MatchStatus,
    PatternMatch,
    Position,
    ProposalConsent,
    RuleNumbers,
    RulePattern,
    SourcePair,
    cs_action_pairs,
    desideratum_name,
    machine_of,
    move_advice_desiderata,
    move_names,
    rule_label,
    rule_number,
    trigger_of,
)
from vultron.measure.action_rules.verdicts import (
    VENDOR,
    MoveVerdict,
    VendorPoint,
    VendorScore,
    case_points,
    open_desiderata,
    point_at,
    point_prefix,
    vendor_points,
    vendor_score,
    vendor_verdicts,
)

__all__ = [
    "ACTION_MOVES",
    "ANY_ROLE",
    "AuthoredRule",
    "ConditionalBranch",
    "ConditionalVerdict",
    "ConsentReading",
    "DesideratumShift",
    "FLAGGED",
    "FORCED_STEP",
    "GeneratedRule",
    "Machine",
    "MatchStatus",
    "MoveVerdict",
    "NON_VENDOR",
    "NOT_MEASURED",
    "NOT_THE_OWNER",
    "NO_STATE_ACTIONS",
    "NO_STATE_CHANGE",
    "PatternMatch",
    "PointComparison",
    "Position",
    "PositionKey",
    "ProposalConsent",
    "ResultKind",
    "RuleNumbers",
    "RulePattern",
    "RuleResult",
    "SCORED_MACHINES",
    "SourcePair",
    "VENDOR",
    "VendorPoint",
    "VendorScore",
    "authored_rules",
    "case_points",
    "compare_point",
    "compare_points",
    "conditional_verdicts",
    "conditionals_from",
    "cs_action_pairs",
    "desideratum_name",
    "generated_rules",
    "group_positions",
    "machine_of",
    "trigger_of",
    "move_advice_desiderata",
    "move_names",
    "move_role",
    "open_desiderata",
    "point_at",
    "point_prefix",
    "resolve_action",
    "rule_label",
    "rule_move",
    "rule_number",
    "rules_from",
    "vendor_points",
    "vendor_score",
    "vendor_verdicts",
]
