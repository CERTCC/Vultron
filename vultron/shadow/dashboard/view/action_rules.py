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


"""The authored action rules beside the move bands (SHD-06-001; ADR-0216).

:func:`rule_comparisons` compares the authored rules with each vendor's
position in a standing (SHD-06-001), each rule against the move's band for
the matched vendor, read from the case's own outcome shifts (SHD-06-002).
A standing at a picked point gives that point's positions, so the rules
follow the pick.  :func:`action_rule_rows` lays the results out as two
tables:

* the rules the bands check, and the unclaimed moves: each agreement, rule
  disagreement and misplaced rule, with its deciding part and the change in
  each desideratum the rule names; a rule disagreement and a misplaced rule
  are flagged (SHD-06-003);
* the rules with no number: each unscored rule, with why it has no band,
  and each undecided rule, shown as undecided (SHD-06-006).

Nothing here drops a move from the bands or changes a rule (SHD-05-013,
SHD-05-025).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from vultron.measure.action_rules import (
    FLAGGED,
    AuthoredRule,
    PointComparison,
    ResultKind,
    RuleNumbers,
    RuleResult,
    authored_rules,
    case_points,
    compare_points,
    rule_label,
)
from vultron.measure.standing import StandingRecord
from vultron.shadow.dashboard.view.bands import size_text
from vultron.shadow.dashboard.view.labels import Row, actor_label

#: Each result as the page marks it: a rule disagreement and a misplaced
#: rule are flagged (SHD-06-003).
RESULT_FLAGS: Mapping[ResultKind, str] = {
    ResultKind.AGREEMENT: "✅ agreement",
    ResultKind.RULE_DISAGREEMENT: "⚠️ rule disagreement",
    ResultKind.MISPLACED_RULE: "⚠️ misplaced rule",
    ResultKind.UNSCORED_RULE: "➖ unscored rule",
    ResultKind.UNCLAIMED_MOVE: "💡 unclaimed move",
}

#: How the page marks a rule undecided at a position (SHD-06-006).
UNDECIDED_FLAG = "❔ undecided"

#: Why an undecided rule has no number.
UNDECIDED_REASON = (
    "the reading holds no consent state, and the rule's pattern reads it"
)

#: The caption above the action rules.
ACTION_RULES_NOTE = (
    "Each authored action rule that matches a vendor's position at this"
    " point, compared with the move's band for that vendor.  A rule"
    " disagreement or a misplaced rule is flagged: neither the rule nor the"
    " band is ground truth, so the analyst judges which is wrong.  An"
    " unclaimed move is harm-free for the vendor, and no matching rule names"
    " it.  A rule never removes a move from the bands."
)

#: What the page says when no rule lacks a number.
NO_UNNUMBERED_RULE = "None: every matching rule is checked against a band."

#: What the page says when no rule is checked against a band.
NO_CHECKED_RULE = (
    "No matching rule names a move with a band here, and no harm-free move"
    " is unclaimed."
)


class RuleRows(BaseModel):
    """The action rules as the page lays them out.

    Fields:
        checked: One row for each agreement, rule disagreement, misplaced
            rule and unclaimed move, in vendor order, then comparison order.
        unnumbered: One row for each unscored rule, then each undecided
            rule, in vendor order.
        flagged: How many rows of *checked* are flagged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    checked: tuple[Row, ...] = ()
    unnumbered: tuple[Row, ...] = ()
    flagged: int = 0


def rule_comparisons(
    standing: StandingRecord, rules: Sequence[AuthoredRule] | None = None
) -> tuple[PointComparison, ...]:
    """The comparison of *rules*, by default the authored table, at each
    vendor's position in *standing*, against its own outcome shifts."""
    table = authored_rules() if rules is None else rules
    return compare_points(case_points(standing), table)


def _rule_name(rule: AuthoredRule | None, number: RuleNumbers) -> str:
    """A rule by its place in the numbered table, as the docs number it; a
    dash for an unclaimed move, which no rule names.

    Raises:
        ValueError: *rule* is not one of the table's rules.
    """
    return "—" if rule is None else rule_label(number(rule))


def _note(result: RuleResult) -> str:
    notes = []
    if result.blind_spot is not None:
        notes.append(f"cites blind spot #{result.blind_spot}")
    if result.proposal is not None:
        notes.append(f"for proposal {result.proposal}")
    if result.reason is not None:
        notes.append(result.reason)
    return "; ".join(notes)


def _checked_row(
    result: RuleResult,
    names: Mapping[str, str],
    number: RuleNumbers,
) -> Row:
    rule = result.rule
    deciding = (
        f"{result.deciding_part} {size_text(result.deciding_size)}"
        if result.deciding_part is not None
        and result.deciding_size is not None
        else ""
    )
    return {
        "Vendor": actor_label(result.vendor, names),
        "Result": RESULT_FLAGS[result.kind],
        "Rule": _rule_name(rule, number),
        "Roles": rule.roles_label if rule is not None else "",
        "Action": rule.action_label if rule is not None else "",
        "Move": result.move or "",
        "Who moves": (
            actor_label(result.participant, names)
            if result.participant is not None
            else ""
        ),
        "Deciding part": deciding,
        "Named desiderata": "; ".join(
            f"{c.desideratum} {size_text(c.change)}" for c in result.changes
        ),
        "Note": _note(result),
    }


def _unnumbered_row(
    vendor: str,
    flag: str,
    rule: AuthoredRule,
    why: str,
    names: Mapping[str, str],
    number: RuleNumbers,
) -> Row:
    return {
        "Vendor": actor_label(vendor, names),
        "Result": flag,
        "Rule": _rule_name(rule, number),
        "Roles": rule.roles_label,
        "Action": rule.action_label,
        "Why no number": why,
    }


def action_rule_rows(
    comparisons: Sequence[PointComparison],
    names: Mapping[str, str],
    rules: Sequence[AuthoredRule] | None = None,
) -> RuleRows:
    """The rows of *comparisons*: the results the bands check, then the
    rules with no number (SHD-06-003, SHD-06-006).

    *rules* numbers each rule by its place, as the docs do; by default the
    authored table.  They are the rules *comparisons* compared.
    """
    numbers = RuleNumbers(authored_rules() if rules is None else rules)
    checked: list[Row] = []
    unnumbered: list[Row] = []
    flagged = 0
    for comparison in comparisons:
        vendor = comparison.position.vendor
        for result in comparison.results:
            if result.kind is ResultKind.UNSCORED_RULE:
                assert result.rule is not None and result.reason is not None
                unnumbered.append(
                    _unnumbered_row(
                        vendor,
                        RESULT_FLAGS[result.kind],
                        result.rule,
                        result.reason,
                        names,
                        numbers,
                    )
                )
                continue
            flagged += result.kind in FLAGGED
            checked.append(_checked_row(result, names, numbers))
        unnumbered.extend(
            _unnumbered_row(
                vendor, UNDECIDED_FLAG, rule, UNDECIDED_REASON, names, numbers
            )
            for rule in comparison.undecided
        )
    return RuleRows(
        checked=tuple(checked),
        unnumbered=tuple(unnumbered),
        flagged=flagged,
    )


def flagged_note(rows: RuleRows) -> str | None:
    """The warning above the rules when any is flagged; ``None`` when none
    is."""
    if not rows.flagged:
        return None
    noun = "result" if rows.flagged == 1 else "results"
    return (
        f"{rows.flagged} flagged {noun}: a rule disagreement or a misplaced"
        " rule marks a wrong rule or a blind spot of the chance model."
    )


__all__ = [
    "ACTION_RULES_NOTE",
    "NO_CHECKED_RULE",
    "NO_UNNUMBERED_RULE",
    "RESULT_FLAGS",
    "UNDECIDED_FLAG",
    "UNDECIDED_REASON",
    "RuleRows",
    "action_rule_rows",
    "flagged_note",
    "rule_comparisons",
]
