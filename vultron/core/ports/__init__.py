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

"""
Core ports package.

Contains port (interface) definitions for the core domain layer.
Ports are discriminated by direction following the Hexagonal Architecture
pattern (see ``notes/architecture-ports-and-adapters.md``
"Core Port Taxonomy: Inbound vs Outbound").

**Inbound (driving) ports** — external adapters call into core:

- ``ActivityDispatcher`` (``dispatcher.py``) — high-level dispatch contract
  called by HTTP inbox handler, CLI, and MCP driving adapters.
- ``UseCase`` (``use_case.py``) — per-operation contract called by the
  dispatcher implementation.

**Outbound (driven) ports** — core calls out to external systems:

- ``DataLayer`` (``datalayer.py``) — persistence interface; implemented by
  ``TinyDbDataLayer`` in ``vultron/adapters/driven/``.
- ``ActivityEmitter`` (``emitter.py``, to be added in OX-1.0) — outbound
  activity delivery.
"""
