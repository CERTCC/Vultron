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

"""Markdown and YAML renderings of the settings for the reference page."""

from __future__ import annotations

from typing import Any

import yaml

from vultron.metadata.docs.config_reference.settings import (
    ConfigSetting,
    iter_settings,
)

#: Heading for the settings that sit at the top level of ``AppConfig``.
TOP_LEVEL_SECTION = "Top-level settings"


def _section_name(setting: ConfigSetting) -> str:
    return setting.path[0] if len(setting.path) > 1 else TOP_LEVEL_SECTION


def render_settings_tables(settings: list[ConfigSetting] | None = None) -> str:
    """Return one Markdown table per ``config.yaml`` section.

    Top-level settings come first, then each section in ``AppConfig`` order,
    headed by its key. A model with no top-level settings gets no top-level
    table.
    """
    settings = iter_settings() if settings is None else settings
    sections: dict[str, list[ConfigSetting]] = {TOP_LEVEL_SECTION: []}
    for setting in settings:
        sections.setdefault(_section_name(setting), []).append(setting)

    lines: list[str] = []
    for name, members in sections.items():
        if not members:
            continue
        heading = name if name == TOP_LEVEL_SECTION else f"`{name}:` section"
        lines += [f"### {heading}", ""]
        lines += [
            "| YAML key | Environment variable | Type | Default | Description |",
            "|---|---|---|---|---|",
        ]
        for s in members:
            lines.append(
                f"| `{s.yaml_key}` | `{s.env_var}` | {s.type_label}"
                f" | {s.default} | {s.description} |"
            )
        lines.append("")
    return "\n".join(lines)


def default_config_yaml(settings: list[ConfigSetting] | None = None) -> str:
    """Return a ``config.yaml`` that sets every setting to its default."""
    settings = iter_settings() if settings is None else settings
    document: dict[str, Any] = {}
    for setting in settings:
        node = document
        for key in setting.path[:-1]:
            node = node.setdefault(key, {})
        node[setting.path[-1]] = setting.default_value
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def render_default_config_block(
    settings: list[ConfigSetting] | None = None,
) -> str:
    """Return :func:`default_config_yaml` as a fenced ``yaml`` code block."""
    return f"```yaml\n{default_config_yaml(settings)}```\n"
