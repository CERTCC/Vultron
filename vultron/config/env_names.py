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

"""How a configuration setting's key path becomes its environment variable.

Every variable is ``VULTRON_`` followed by the key path in upper case, with
``__`` between a section and the key inside it (CFG-03-001, CFG-03-002).
:class:`~vultron.config.app.AppConfig` reads the environment by these two
constants, and every message or page that names a variable derives it with
:func:`env_var_name`, so the name printed is the name read.
"""

from __future__ import annotations

#: Prefix of every node environment variable (CFG-03-001).
ENV_PREFIX = "VULTRON_"

#: Separator between nested keys in an environment variable name (CFG-03-002).
ENV_NESTED_DELIMITER = "__"


def env_var_name(path: tuple[str, ...]) -> str:
    """Return the environment variable for the setting at *path* (CFG-03)."""
    return ENV_PREFIX + ENV_NESTED_DELIMITER.join(path).upper()
