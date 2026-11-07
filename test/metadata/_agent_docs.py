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
"""Reading the agent-facing Markdown that guards over commands check.

Shared by the modules that ask what a written command does:
``test_gate_ceiling.py`` (the gate's ceiling, its heavy-check slot, and that
no gate runs the whole suite) and ``test_draft_pr_wiring.py`` (the draft life
cycle of a Pull Request).
"""

from __future__ import annotations


def code_lines(text: str) -> list[str]:
    """The lines of *text* an agent runs: frontmatter ``commands:`` and fences.

    Prose and inline code are left out on purpose. A guard that read them
    would invent a violation out of the sentence forbidding one — "never run
    ``gh pr ready`` here" reads as running it.
    """
    lines = text.splitlines()
    code: list[str] = []
    fenced = False
    in_frontmatter = bool(lines) and lines[0] == "---"
    in_commands = False
    for index, line in enumerate(lines):
        if in_frontmatter:
            if index and line == "---":
                in_frontmatter = False
            elif not line.startswith(" "):
                in_commands = line.startswith("commands:")
            elif in_commands:
                code.append(line)
        elif line.lstrip().startswith("```"):
            fenced = not fenced
        elif fenced:
            code.append(line)
    return code
