#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
This module contains functions to validate the various strings and patterns used by the CVD State Model
"""

import re
from typing import Callable

from vultron.case_states.errors import (
    HistoryValidationError,
    PatternValidationError,
    StateValidationError,
    TransitionValidationError,
)

TRANSITION_RULES = [
    # if a matches src, then b must match on dst
    ("v..P..", "V..P.."),
    ("...pX.", "...PX."),
]


def is_valid_pattern(pat: str) -> None:
    """
    Validate a pattern string.
    Patterns are expected to be regular expressions with the following constraints:

    - The pattern is exactly six characters long.
    - The pattern contains either upper or lower case v, f, d, p, x, a, in that order, or a dot.

    Examples:
        ```python
        is_valid_pattern("vfdpxa")
        is_valid_pattern("Vfd.X.")
        ```
        will succeed but
        ```python
        is_valid_pattern("xpdfva")
        is_valid_pattern("vfDPx")
        ```
        fail with a `PatternValidationError`.

    Args:
        pat: the pattern string to validate

    Returns:
        None

    Raises:
        PatternValidationError: if the pattern is invalid
    """
    if pat is None:
        raise (PatternValidationError(f"Invalid Pattern [{pat}]"))

    if not len(pat) == 6:
        raise PatternValidationError(f"Invalid Pattern [{pat}]")

    for p, c in zip(pat.lower(), "vfdpxa"):
        if p == c:
            continue
        # if you got here, the chars don't match
        if p == ".":
            continue
        # and the pattern is not a dot at this char
        # so you have a problem
        raise PatternValidationError(f"Invalid Pattern [{pat}]")


def ensure_valid_pattern(func: Callable) -> Callable:
    """Function decorator to ensure a valid pattern is passed to a function

    Example:
        ```python
        @ensure_valid_pattern
        def my_func(pattern, ...):
             ...
        ```
    Args:
        func: the function to decorate

    Returns:
        the decorated function
    """

    def wrapper(*args, **kwargs):
        # get the pattern from the first arg
        pat = args[0]
        try:
            is_valid_pattern(pat)
        except PatternValidationError as e:
            raise e
        return func(*args, **kwargs)

    return wrapper


def is_valid_state(state: str) -> None:
    """Validate a state string.
    Checks that the state is a valid state pattern.
    Also checks that the state is not impossible (e.g. `vF....`, `.fD...`)
    Finally, verifies that only allowed symbols (`vVfFdDpPxXaA.`) are used.


    Args:
        state: the state string to validate

    Returns:
        None

    Raises:
        StateValidationError: if the state is invalid
    """
    # every valid state has to be a valid pattern too
    try:
        is_valid_pattern(state)
    except PatternValidationError as e:
        raise StateValidationError(e)

    # disqualify impossible states
    if re.match("vF....", state):
        raise StateValidationError(f"Invalid state [{state}]")
    if re.match(".fD...", state):
        raise StateValidationError(f"Invalid state [{state}]")
    if not re.match("[vV.][fF.][dD.][pP.][xX.][aA.]", state):
        raise StateValidationError(f"Invalid state [{state}]")


def ensure_valid_state(func: Callable) -> Callable:
    """Function Decorator to ensure a valid state is passed to a function

    Example:
        ```python
        @ensure_valid_state
        def my_func(state, ...):
            ...
        ```

    Args:
        func: the function to decorate

    Returns:
        the decorated function
    """

    def wrapper(*args, **kwargs):
        # get the state from the first arg
        state = args[0]
        try:
            is_valid_state(state)
        except StateValidationError as e:
            raise e
        return func(*args, **kwargs)

    return wrapper


def ensure_valid_state_method_wrapper(func: Callable) -> Callable:
    """Method Decorator to ensure a valid state is passed to a method.
    Equivalent to ensure_valid_state, but for methods.

    Example:
        ```python
        class MyClass:
            @ensure_valid_state_method_wrapper
            def my_method(self, state, ...):
                ...
        ```

    Args:
        func: the method to decorate

    Returns:
        the decorated method
    """

    def wrapper(self, *args, **kwargs):
        # todo: this part would be cool to use, but it slows things down (doubled the time to run tests)
        # # get method default arguments and add them to the dict we are going to check
        # sig = inspect.signature(func)
        # bound = sig.bind(self, *args, **kwargs)
        # bound.apply_defaults()
        # bound_args = bound.arguments
        # bound_args.update(kwargs)

        # sometimes it's a kwarg called "state"
        # sometimes there are two states called "src" and "dst" or "start" and "end"
        states = []
        for k in ["state", "src", "dst", "start", "end"]:
            # if k in bound_args:
            #     states.append(bound_args[k])
            if k in kwargs:
                states.append(kwargs[k])

        # sometimes the state is the first arg,
        if len(states) == 0 and len(args) > 0:
            states.append(args[0])

        if not len(states) > 0:
            raise RuntimeError(
                "ensure_valid_state_method_wrapper: no state found in args or kwargs"
            )

        for state in states:
            try:
                is_valid_state(state)
            except StateValidationError as e:
                raise e

        return func(self, *args, **kwargs)

    return wrapper


def is_valid_transition(src: str, dst: str, allow_null: bool = False) -> None:
    """Validate a transition from src to dst

    Args:
        src: the source state
        dst: the destination state
        allow_null: if True, allow null transitions (src==dst), default=False

    Returns:
        None

    Raises:
        TransitionValidationError: if the transition is invalid
    """
    try:
        is_valid_state(src)
    except StateValidationError as e:
        raise TransitionValidationError(e)

    try:
        is_valid_state(dst)
    except StateValidationError as e:
        raise TransitionValidationError(e)

    # compute hamming distance
    diff = [(c1, c2) for c1, c2 in zip(src, dst) if c1 != c2]
    HD = len(diff)

    # short circuit to allow null transition
    if allow_null and HD == 0:
        return

    # otherwise reject unless hamming distance is 1
    if HD != 1:
        raise TransitionValidationError("Only HD=1 transitions allowed")

    # changes must be from lc to uc
    c1, c2 = diff[0]
    if c1.isupper():
        raise TransitionValidationError("Transitions from UC not permitted")

    if c2.islower():
        raise TransitionValidationError("Transitions to lc not permitted")

    if c1.lower() != c2.lower():
        raise TransitionValidationError(f"Invalid transition [{c1}->{c2}]")

    for a, b in TRANSITION_RULES:
        if re.match(a, src):
            # if the first pattern matches,
            # then the second must as well
            if not re.match(b, dst):
                raise TransitionValidationError(f"Transition not permitted [{a}->{b}]")


def is_valid_history(h: str) -> None:
    """
    Validate a history string.
    Checks that the history is exactly six characters long, is all uppercase, and contains one each of V, F, D, P, X, and A.
    Also checks that the causally-related events are in the correct order:

    - V $\\prec$ F $\\prec$ D
    - P $\\prec$ X or XP
    - V $\\prec$ P or PV

    Example:
        ```python
        is_valid_history("VFDPXA")
        ```
        succeeds, but
        ```python
        is_valid_history("VFDPX")
        ```
        fails with a `HistoryValidationError`.

    Args:
        h: the history string to validate

    Returns:
        None

    Raises:
        HistoryValidationError: if the history is invalid
    """
    # a history has exactly six elements
    if len(h) != 6:
        raise HistoryValidationError("History must have 6 events")

    # a history is all uppercase
    if not h.isupper():
        raise HistoryValidationError("History must be all uppercase")

    # a history must contain one each of v,f,d,p,x,a
    for c in "VFDPXA":
        if c not in h:
            raise HistoryValidationError(f"History must contain event {c}")

    # V<F
    if h.index("V") > h.index("F"):
        raise HistoryValidationError("V must precede F")
    # F<D
    if h.index("F") > h.index("D"):
        raise HistoryValidationError("F must precede D")
    # P...X or XP
    if (h.index("P") - h.index("X")) > 1:
        raise HistoryValidationError("P must precede X or immediately follow it")
    # V...P or PV
    if (h.index("V") - h.index("P")) > 1:
        raise HistoryValidationError("V must precede V or immediately follow it")


def ensure_valid_history(func: Callable) -> Callable:
    """Decorator to ensure a valid history is passed to a function

    Example:
        ```python
        @ensure_valid_history
        def my_func(history, ...):
            ...
        ```
    Args:
        func: the function to decorate

    Returns:
        the decorated function

    Raises:
        HistoryValidationError: if the history is invalid
    """

    def wrapper(*args, **kwargs):
        # get the history from the first arg
        history = args[0]
        try:
            is_valid_history(history)
        except HistoryValidationError as e:
            raise e
        return func(*args, **kwargs)

    return wrapper
