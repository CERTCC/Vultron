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

"""Renderer for the generated tables on ``docs/reference/configuration.md``.

The node configuration reference lists every setting a Vultron node reads from
``config.yaml`` and the ``VULTRON_*`` environment variables. Its tables and its
example file are generated at build time from
:class:`vultron.config.app.AppConfig` by a markdown-exec Python block, so a new,
renamed or re-defaulted field reaches the page without a docs edit (#4171).

Each leaf field of ``AppConfig`` becomes one :class:`ConfigSetting`: its YAML
key path, the environment variable that overrides it, a type label, its
default, its bounds and a description. The description is the field's
entry under its model's ``Attributes:`` docstring section when it has one,
else its ``Field(description=...)``; the docstring entry comes first because it
is the fuller of the two where both exist. A field with neither raises
:class:`ConfigReferenceError`, which fails the strict docs build rather than
publishing a blank row.

A description is split into sentences, and a sentence that only states the
default (``Defaults to 30.``, ``Default: 7 days.``), the overriding variable
(``Override via ``VULTRON_X``.``) or a code pointer (``See ``X``.``) is dropped,
because the table prints the first two from the model; keeping them would give
one row two sources for the same fact. A sentence that starts that way but
says anything more raises :class:`ConfigReferenceError` rather than lose the
extra fact, as does an ``Override via`` sentence naming another variable.
Python literals in code spans become the page's vocabulary (``None`` reads
``unset``, ``True`` reads ``true``), and issue numbers in prose are dropped,
since they are project-record pointers, not facts about the setting. A cleaned
description that is empty or still carries reStructuredText markup or an
emptied parenthesis raises too, so the strict docs build fails instead of
publishing a mangled row.

Usage (in a markdown-exec Python block)::

    from vultron.metadata.docs.config_reference import render_settings_tables
    print(render_settings_tables())
"""

from vultron.config.env_names import (
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    env_var_name,
)
from vultron.metadata.docs.config_reference.errors import ConfigReferenceError
from vultron.metadata.docs.config_reference.render import (
    TOP_LEVEL_SECTION,
    default_config_yaml,
    render_default_config_block,
    render_settings_tables,
)
from vultron.metadata.docs.config_reference.settings import (
    ConfigSetting,
    iter_settings,
)

__all__ = [
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "TOP_LEVEL_SECTION",
    "ConfigReferenceError",
    "ConfigSetting",
    "default_config_yaml",
    "env_var_name",
    "iter_settings",
    "render_default_config_block",
    "render_settings_tables",
]
