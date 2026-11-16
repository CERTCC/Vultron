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

"""Recognise log calls in an ``ast`` tree, for the logging ratchets.

One definition of "this call is a log call", shared by
``test_infrastructure_logs_not_at_info.py`` (SL-04-007) and
``test_no_correlation_ids_in_log_extra.py`` (SL-02-003), so widening what
counts as a logger widens both.

Coverage limits — deliberate, but worth knowing before trusting a green run:

- The receiver must be a name in :data:`LOGGER_NAMES` (``logger.info``,
  ``logging.info``), an attribute in :data:`LOGGER_ATTRIBUTES`
  (``self.logger.info``), or a call to a function in :data:`LOGGER_FACTORIES`
  (``logging.getLogger(__name__).info``, ``node_logger(node).info``).  A logger
  bound to any other name is not matched.
- :func:`message_text` reads only the message argument (the second one for
  ``.log(level, msg)``), so a message pre-built with ``%`` or ``.format()`` and
  passed as a variable is not matched.

Extend these rather than assume a ratchet already covers a new shape.
"""

import ast

#: Bare receiver names that hold a logger (``logging`` for the module-level
#: functions).
LOGGER_NAMES: frozenset[str] = frozenset(
    {"logger", "_LOGGER", "log", "logging"}
)

#: Attribute names that hold a logger (``self.logger``, ``self._logger``).
LOGGER_ATTRIBUTES: frozenset[str] = frozenset({"logger", "_logger"})

#: Functions whose call returns a logger.
LOGGER_FACTORIES: frozenset[str] = frozenset({"getLogger", "node_logger"})

#: Every ``logging.Logger`` method that writes a record.
LOG_METHODS: frozenset[str] = frozenset(
    {
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "exception",
        "critical",
        "log",
    }
)


def _is_logger_receiver(receiver: ast.expr) -> bool:
    if isinstance(receiver, ast.Name):
        return receiver.id in LOGGER_NAMES
    if isinstance(receiver, ast.Attribute):
        return receiver.attr in LOGGER_ATTRIBUTES
    if isinstance(receiver, ast.Call):
        func = receiver.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        return name in LOGGER_FACTORIES
    return False


def is_log_call(node: ast.Call, methods: frozenset[str] = LOG_METHODS) -> bool:
    """Return True when *node* calls one of *methods* on a recognised logger."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in methods:
        return False
    return _is_logger_receiver(func.value)


def is_logger_info_call(node: ast.Call) -> bool:
    """Return True when *node* is an INFO log call on a recognised logger."""
    return is_log_call(node, frozenset({"info"}))


def message_text(node: ast.Call) -> str:
    """Return the literal text of *node*'s message argument, or ``""``.

    The message is the first argument, or the second for ``.log(level, msg)``.

    Handles plain string literals, implicitly-concatenated literals (which
    ``ast`` folds into one ``Constant``), and f-strings, whose literal
    segments are concatenated so fragments spanning an interpolation are
    still detected.
    """
    position = (
        1
        if isinstance(node.func, ast.Attribute) and node.func.attr == "log"
        else 0
    )
    if len(node.args) <= position:
        return ""
    message = node.args[position]
    if isinstance(message, ast.Constant) and isinstance(message.value, str):
        return message.value
    if isinstance(message, ast.JoinedStr):
        return "".join(
            part.value
            for part in message.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return ""
