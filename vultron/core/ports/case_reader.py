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

"""Driven port: read one case from an outside system (ADR-0191, CRD-01).

A case reader answers a request for one case with a
:class:`~vultron.core.models.case_reading.CaseReading`: the case as a core
case ledger, plus its citations, inferences, untranslated facts and the
facts its source can never observe (ADR-0197).  An outside-system reader,
such as the VINCE case reader, translates that system's case; a Vultron
case reader returns a CASE_MANAGER's ledger as it is.

The port is read-only: it declares no method that writes to the outside
system (CRD-01-002), so a reader cannot write whatever its adapter does.  A
read-write port for the later gateway is a separate interface.

This is a connector direction: a connector plugin implements it to serve
the case shadow (ARCH-05-004).  The core declares it here and never imports
a connector (ARCH-05-001).
"""

from typing import Protocol, runtime_checkable

from vultron.core.models.case_reading import CaseReading, UnobservableFact


@runtime_checkable
class CaseReader(Protocol):
    """Port: return one outside-system case as a case reading.

    Attributes:
        unobservable: What the reader's source never exposes, for any case.
            The reader declares it once and copies it into every reading it
            returns (CRD-02-004).
    """

    unobservable: tuple[UnobservableFact, ...]

    def read_case(self, case_id: str) -> CaseReading:
        """Read the case the outside system names *case_id*.

        A fact the reader cannot translate is returned in the reading's
        untranslated facts, never dropped and never a reason to refuse the
        case (CRD-01-005).  Each translated entry names as its actor the
        participant who acted in the outside system (CRD-01-006), and takes
        its times from the source, never from a clock read (CRD-02-006).

        Raises:
            VultronError: The case could not be read at all, for example
                because the source is unreachable or holds no such case.
        """
        ...  # pragma: no cover


__all__ = ["CaseReader"]
