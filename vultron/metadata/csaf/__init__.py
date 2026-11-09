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
"""Tooling for the pinned local copy of the CSAF 2.1 schemas (CSAF-05).

- :mod:`.pin` reads the pin record, ``third_party/csaf/pin.json``, which names
  the draft revision and maps each referenced schema to its file in the
  pinned local copy, ``third_party/csaf/schemas/`` (CSAF-05-001).
- :mod:`.regenerate` writes the models in ``vultron/wire/csaf/models/`` from
  the pinned local copy, or checks that they match it (``csaf-models``).
- :mod:`.corpus` runs those models over a local clone of the CSAF Technical
  Committee's test documents (``csaf-corpus``), outside the test suite
  (CSAF-05-004).
"""
