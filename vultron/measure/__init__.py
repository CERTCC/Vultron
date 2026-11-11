"""The read-only measurement layer: CVD measures computed from a finished case's ledger.

Nothing in the protocol path imports this package (CEH-01-001), and nothing in
it writes to the DataLayer, a case ledger or any store (CEH-01-002); both
boundaries are architecture tests.  The package sits beside the demo layer, not
under it: the demo report tool imports its ledger reader from here, never the
reverse.

Layout (notes/case-event-history.md § "Reuse the One JSONL Walker"):

* :mod:`vultron.measure.ledger` — the tolerant case-ledger JSONL reader, its
  field-spelling helpers, the display-name resolver, and the complete-copy
  selection that every measure reads through (CEH-02).
* :mod:`vultron.measure.history` — the case event history derived from one
  case's ledger (CEH-03, CEH-04).
* :mod:`vultron.measure.baselines` — the exact chance baselines of the
  desiderata, from the indifference walk over the smallest model holding each
  (ADR-0182).  It reads only the state tables, never a ledger.

Later layers are sibling subpackages that read
through :mod:`vultron.measure.ledger`.
"""

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
