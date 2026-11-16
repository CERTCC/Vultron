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

"""What a connector plugin exposes beyond its name and its ports (ARCH-05-005)."""

from typing import get_protocol_members

from vultron.adapters.connectors.base import (
    ConnectorPlugin,
    ports_implemented_by,
)


def surplus_members(plugin: object) -> set[str]:
    """*plugin*'s public members that are neither its name nor a member of
    a port it implements.

    A member of a port the plugin does not implement, such as a raising
    write stub, lands here (ARCH-05-005).
    """
    allowed = set(get_protocol_members(ConnectorPlugin))
    for port in ports_implemented_by(plugin):
        allowed |= get_protocol_members(port)
    public = {name for name in dir(plugin) if not name.startswith("_")}
    return public - allowed
