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
"""CSAF 2.1 documents at the wire edge (ADR-0184, CSAF-05).

- ``models/`` holds the Pydantic models generated from the pinned local copy
  of the CSAF 2.1 draft's schemas, whose root is
  ``CommonSecurityAdvisoryFramework``. Never edit them by hand: run
  ``uv run csaf-models`` (CSAF-05-003).

The copy itself and its pin record are third-party files in
``third_party/csaf/``, outside this package; :mod:`vultron.metadata.csaf.pin`
reads them, and nothing reads them at runtime (CSAF-05-001, CSAF-05-002).

A document the models accept is schema-valid, never valid CSAF: the schema
leaves most of the mandatory tests unchecked (CSAF-04-002).
"""
