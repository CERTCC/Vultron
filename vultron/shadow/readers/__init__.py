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

"""The case shadow's case readers, and which one a run reads through.

* :class:`~vultron.shadow.readers.vultron_ledger.VultronCaseReader` — reads
  a Vultron case-ledger JSONL file, untranslated.
* :func:`~vultron.shadow.readers.selection.select_case_reader` — the reader a
  run uses: the configured outside-system reader, or the Vultron case reader
  when none is configured.
"""

from vultron.shadow.readers.selection import select_case_reader
from vultron.shadow.readers.vultron_ledger import VultronCaseReader

__all__ = ["VultronCaseReader", "select_case_reader"]
