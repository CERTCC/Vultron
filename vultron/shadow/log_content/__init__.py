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

"""The case shadow's log records carry ids, never case content (VSD-01-003).

Logs are copied into issues, CI artifacts and agent sessions, so a log record
is a publication path (ADR-0189).  While :func:`withheld_case_content` is
active, every log record the process makes, by any logger and whatever
handler later writes it, is cleaned when it is made:

* A message argument that is an object, not a scalar, is replaced by its type
  name and id.  A whole case reading, entry or payload never reaches the
  text.
* An exception, logged with ``exc_info`` or passed as an argument, keeps its
  traceback (file, line, function and source line) and its type.  The message
  of a :class:`~vultron.errors.VultronError` is kept, because Vultron authors
  those messages to name ids and problems, not values.  Any other exception's
  message is withheld: a validation error, for one, quotes the input it
  refused.
* Inside :func:`case_log_context`, each string of the case reading's content
  (:func:`reading_content`) is replaced in each argument and traceback by
  :data:`WITHHELD`.  A string is found only where a record quotes it whole,
  or quotes one whole line of it: a word, a truncation or a changed case of
  a value is not found, nor is a value under four characters.  So code
  logs ids and counts, never a piece of a value.  An exception raised
  inside the context carries the context out with it, so a record made
  after the context has exited, such as
  Streamlit's log of an uncaught page exception, is cleaned too and carries
  the case's ids as attributes.  Streamlit writes that record with its own
  plain formatter, which prints no attribute.

The ids stay: inside :func:`case_log_context` each record carries
``case_id``, and ``case_reference`` when the case's ledger holds an outside
tracker reference (an ``issue-tracking`` ``CaseReference``, such as a VINCE
case URL).  The reference is known once the case is read
(:meth:`CaseLog.withhold`), so a record the reader makes during the read
names the case by ``case_id`` alone.  The shadow keeps no copy of a case
(SHD-01-003), so that reference is how a log read after the run finds the
case again.  The correlation ids
(``activity_id``, ``actor_id``) come from
:func:`~vultron.logging_correlation.correlation_context`, and
:class:`ShadowFormatter` prints all of them after the message.

The records are cleaned by a log record factory, not a handler filter,
because Streamlit writes its own records through handlers of its own, which
it replaces when it reads its configuration.  A factory sees each record when
it is made, before any handler.  :func:`shadow_logging` installs the factory
and the shadow's one root handler; ``vultron-shadow`` enters it around the
whole run.  A record the cleaning fails on is written as :data:`UNCLEANED`.
``Logger.makeRecord`` applies ``extra=`` after the factory, so an ``extra=``
value is not cleaned, and an ``extra=`` key the factory has set
(:data:`CASE_FIELDS`, a correlation id) raises ``KeyError``.  Neither may be
passed per call (``test/architecture/test_no_correlation_ids_in_log_extra.py``).

Modules:

* :mod:`.content` — what in a case reading is content, and its tracker
  references.
* :mod:`.context` — the case context and the scrub it applies.
* :mod:`.render` — how a record's arguments and exception are rendered.
* :mod:`.records` — the record factory and the shadow's handler.
"""

from vultron.shadow.log_content.content import (
    ISSUE_TRACKING_REL,
    reading_content,
    tracker_references,
)
from vultron.shadow.log_content.context import (
    WITHHELD,
    CaseLog,
    CaseLogContext,
    case_log_context,
)
from vultron.shadow.log_content.records import (
    CASE_FIELDS,
    UNCLEANED,
    ShadowFormatter,
    shadow_logging,
    withheld_case_content,
    withhold_case_content,
)
from vultron.shadow.log_content.render import WITHHELD_MESSAGE

__all__ = [
    "CASE_FIELDS",
    "ISSUE_TRACKING_REL",
    "UNCLEANED",
    "WITHHELD",
    "WITHHELD_MESSAGE",
    "CaseLog",
    "CaseLogContext",
    "ShadowFormatter",
    "case_log_context",
    "reading_content",
    "shadow_logging",
    "tracker_references",
    "withheld_case_content",
    "withhold_case_content",
]
