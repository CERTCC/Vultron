#!/usr/bin/env python
"""file: zerodays
author: adh
created_at: 5/19/21 3:50 PM
"""
#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

from vultron.cvd_states.enums.utils import enum2title, unique_enum_list
from vultron.cvd_states.enums.zerodays import ZeroDayType
from vultron.cvd_states.patterns.base import compile_patterns
from vultron.cvd_states.validations import ensure_valid_state

_ZERODAYS = {
    "v..p..": (ZeroDayType.ZERO_DAY_VULNERABILITY_TYPE_1,),
    "v..P..": (ZeroDayType.ZERO_DAY_VULNERABILITY_TYPE_2,),
    ".f.P..": (ZeroDayType.ZERO_DAY_VULNERABILITY_TYPE_3,),
    "vfd.X.": (ZeroDayType.ZERO_DAY_EXPLOIT_TYPE_1,),
    ".fd.X.": (ZeroDayType.ZERO_DAY_EXPLOIT_TYPE_2,),
    "...pX.": (ZeroDayType.ZERO_DAY_EXPLOIT_TYPE_3,),
    "vfd..A": (ZeroDayType.ZERO_DAY_ATTACK_TYPE_1,),
    ".fd..A": (ZeroDayType.ZERO_DAY_ATTACK_TYPE_2,),
    "...p.A": (ZeroDayType.ZERO_DAY_ATTACK_TYPE_3,),
}

ZERODAYS = compile_patterns(_ZERODAYS)


@ensure_valid_state
def zeroday_type(state):
    """Determine the type(s) of Zero Day from the state

    Args:
        state

    Returns:

    """
    information = []
    for pat, info in ZERODAYS.items():
        if pat.match(state):
            information.extend(info)

    if len(information) == 0:
        # we didn't match anything, so it's not a zero day anything
        information.append(ZeroDayType.NOT_APPLICABLE)
    return unique_enum_list(information)


def type_from_history(history: str):
    """Determine the type(s) of Zero Day from the history

    Args:
        history

    Returns:

    """
    history = history.upper()

    v = history.find("V")
    f = history.find("F")
    d = history.find("D")
    p = history.find("P")
    x = history.find("X")
    a = history.find("A")

    ztypes = []
    # type 1 zero day vulnerabilities can not be discerned from a history
    # they are only relevant for individual case states
    if p < v:
        ztypes.append(ZeroDayType.ZERO_DAY_VULNERABILITY_TYPE_2)
    if p < f:
        ztypes.append(ZeroDayType.ZERO_DAY_VULNERABILITY_TYPE_3)
    if x < v:
        ztypes.append(ZeroDayType.ZERO_DAY_EXPLOIT_TYPE_1)
    if x < f:
        ztypes.append(ZeroDayType.ZERO_DAY_EXPLOIT_TYPE_2)
    if x < p:
        ztypes.append(ZeroDayType.ZERO_DAY_EXPLOIT_TYPE_3)
    if a < v:
        ztypes.append(ZeroDayType.ZERO_DAY_ATTACK_TYPE_1)
    if a < f:
        ztypes.append(ZeroDayType.ZERO_DAY_ATTACK_TYPE_2)
    if a < p:
        ztypes.append(ZeroDayType.ZERO_DAY_ATTACK_TYPE_3)

    return unique_enum_list(ztypes)


def main():
    info: object
    for pat, info in ZERODAYS.items():
        for i in info:
            print(f"* {pat.pattern} => {enum2title(i)}")

    for history in [
        "PVFDXA",
        "XPVAFD",
    ]:
        print(
            f"History: {history} => {[enum2title(x) for x in type_from_history(history)]}"
        )


if __name__ == "__main__":
    main()
