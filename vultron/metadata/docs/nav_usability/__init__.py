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
"""The agent usability test that gates a navigation change (ADR-0136).

The method, rerun policy and recorded verdicts are in
``notes/nav-usability-test.md``. This package scripts the parts that must not
vary between runs, so the personas and tasks in
``notes/nav-usability/suite.yaml`` can be reused:

* **Stage 1, tree test.** :func:`nav_tree` turns a ``mkdocs.yml`` nav into a
  label tree with no page content; :func:`tree_prompt` briefs one
  persona on it; :func:`score_tree_answers` resolves each answered node to
  its page and scores it against the task's destinations.
* **Stage 2, walkthrough.** :class:`Walk` serves a built ``site/`` one page
  at a time as text plus numbered links, counting clicks against a budget.
  It has no search, by construction.
* **Tally.** :func:`tally` compares two navs' results and applies the pass
  rule: no worse on task success, and no task stalls at the home page.

Results are keyed on :func:`nav_hash`, so a baseline is reused until the
baseline nav itself changes.

CLI (``uv run nav-usability``):
    tree     print a config's nav hash and label tree
    prompt   print the Stage 1 briefing for one persona
    score    score a persona's Stage 1 answers into a results file
    walk-prompt  print the Stage 2 briefing for one persona
    walk     take one Stage 2 step in a session
    score-walks  score finished Stage 2 sessions into a results file
    tally    compare two results files and print the verdict
"""

from vultron.metadata.docs.nav_usability.cli import main
from vultron.metadata.docs.nav_usability.results import (
    Outcome,
    Results,
    TaskResult,
    Verdict,
    load_results,
    save_results,
    tally,
)
from vultron.metadata.docs.nav_usability.suite import (
    SUITE_PATH,
    Persona,
    Suite,
    Task,
    load_suite,
)
from vultron.metadata.docs.nav_usability.tree import (
    NavNode,
    nav_hash,
    nav_tree,
    render_tree,
    resolve_label_path,
    score_tree_answers,
    tree_prompt,
    walk_nodes,
)
from vultron.metadata.docs.nav_usability.walk import (
    DEFAULT_CLICK_BUDGET,
    PageView,
    Walk,
    WalkState,
    read_page,
    score_walk,
    site_page,
    walk_prompt,
)

__all__ = [
    "DEFAULT_CLICK_BUDGET",
    "SUITE_PATH",
    "NavNode",
    "Outcome",
    "PageView",
    "Persona",
    "Results",
    "Suite",
    "Task",
    "TaskResult",
    "Verdict",
    "Walk",
    "WalkState",
    "load_results",
    "load_suite",
    "main",
    "nav_hash",
    "nav_tree",
    "read_page",
    "render_tree",
    "resolve_label_path",
    "save_results",
    "score_tree_answers",
    "score_walk",
    "site_page",
    "tally",
    "tree_prompt",
    "walk_nodes",
    "walk_prompt",
]
