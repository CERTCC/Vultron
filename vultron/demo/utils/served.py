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
"""Read an object a server served as the received data it is.

A demo client reads what an actor's server holds or answers.  To the client
that is received data: a time a served object omits (a nested object a dump
left out as ``None``) is the server claiming none, read as ``None``, never
the client's clock (ADR-0103, ADR-0176).  So every served object is validated
under the inbound context, as the server's own parser reads a delivery.
"""

from typing import Any

from pydantic import BaseModel

from vultron.core.models._helpers import INBOUND_CONTEXT_KEY


def from_server[M: BaseModel](cls: type[M], data: Any) -> M:
    """Validate *data*, a body a server served, into *cls* as received."""
    return cls.model_validate(data, context={INBOUND_CONTEXT_KEY: True})


__all__ = ["from_server"]
