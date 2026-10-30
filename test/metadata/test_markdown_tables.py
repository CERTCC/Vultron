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
"""Tests for :func:`vultron.metadata.markdown_tables.exec_blocks`."""

from vultron.metadata.markdown_tables import ExecBlock, exec_blocks


def test_exec_blocks_skip_plain_fences_and_record_the_opener_line() -> None:
    text = "\n".join(
        [
            "prose",
            "```python",
            "plain()",
            "```",
            '```python exec="true" idprefix=""',
            "run()",
            "```",
        ]
    )
    assert exec_blocks(text) == (ExecBlock(5, "run()"),)


def test_exec_blocks_dedent_a_nested_block() -> None:
    text = '!!! note\n\n    ````python exec="true"\n    a()\n      b()\n    ````\n'
    assert exec_blocks(text) == (ExecBlock(3, "a()\n  b()"),)


def test_exec_block_closes_only_on_a_bare_run_at_least_as_long() -> None:
    text = '````python exec="true"\n```\n```python\nx()\n````\n'
    assert exec_blocks(text) == (ExecBlock(1, "```\n```python\nx()"),)


def test_unclosed_exec_block_runs_to_the_end() -> None:
    assert exec_blocks('```python exec="true"\nx()\n') == (
        ExecBlock(1, "x()"),
    )
