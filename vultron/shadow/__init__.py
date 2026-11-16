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

"""The case shadow: a standalone, read-only advisor over one case (ADR-0190).

The shadow uses the Vultron core as a library.  It hosts no actor and has no
inbox, outbox or activity delivery (SHD-01-001); it reads a case only through
a :class:`~vultron.core.ports.case_reader.CaseReader` (SHD-01-002).

The package sits outside the protocol path, beside :mod:`vultron.measure`
rather than under ``vultron/adapters/``.  It reads its cases and their
standing through the measure layer, and no module under ``vultron/core/``,
``vultron/wire/`` or ``vultron/adapters/`` may import that layer (CEH-01-001).

Layout:

* :mod:`vultron.shadow.readers` — the shadow's case readers and the choice of
  which one a run uses: the Vultron case reader over a case-ledger file, the
  default when no outside-system reader is configured.  An outside system's
  reader, such as the VINCE case reader, is a connector plugin under
  ``vultron/adapters/connectors/`` (ADR-0191 rule 6), handed in from there.
"""
