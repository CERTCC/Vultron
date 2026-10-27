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
"""Stage 1, the tree test: a nav as labels only, the briefing, and scoring."""

from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import dataclass, field
from pathlib import Path

from vultron.metadata.base import parse_mkdocs_config
from vultron.metadata.docs.landing_pages import (
    is_url,
    page_title,
    split_nav_item,
)
from vultron.metadata.docs.nav_usability.results import Outcome, TaskResult
from vultron.metadata.docs.nav_usability.suite import Suite
from vultron.metadata.file_loading import (
    MetadataLoadError,
    load_frontmatter,
)

_INDEX_NAME = "index.md"


@dataclass
class NavNode:
    """One nav entry: a label, the page it opens (if any), its children."""

    label: str
    path: str | None
    children: list[NavNode] = field(default_factory=list)

    def pages(self) -> list[str]:
        """Every page at or under this node."""
        own = [self.path] if self.path else []
        return own + [p for child in self.children for p in child.pages()]


def nav_hash(config_text: str) -> str:
    """A short, stable hash of the ``nav`` section of a ``mkdocs.yml``."""
    nav = parse_mkdocs_config(config_text).get("nav", [])
    canonical = json.dumps(nav, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


class _TreeBuilder:
    def __init__(self, docs_dir: Path) -> None:
        self.docs_dir = docs_dir

    def title(self, rel: str) -> str:
        path = self.docs_dir / rel
        if not path.is_file():
            raise MetadataLoadError(
                "is in the nav but does not exist", path=f"docs/{rel}"
            )
        return page_title(load_frontmatter(path), rel)

    def node(self, label: str, path: str | None) -> NavNode:
        return NavNode(label=label, path=path)

    def items(self, items: list[object]) -> list[NavNode]:
        nodes: list[NavNode] = []
        for item in items:
            label, value = split_nav_item(item)
            if isinstance(value, list):
                nodes.append(self.group(label or "", value))
            elif isinstance(value, str):
                shown = label or (
                    value if is_url(value) else self.title(value)
                )
                nodes.append(self.node(shown, value))
        return nodes

    def group(self, label: str, value: list[object]) -> NavNode:
        """A labelled group; an ``index.md`` first member becomes its link,
        as the theme's section indexes render it."""
        opener: str | None = None
        rest = value
        if value:
            first_label, first = split_nav_item(value[0])
            if (
                first_label is None
                and isinstance(first, str)
                and posixpath.basename(first) == _INDEX_NAME
            ):
                opener, rest = first, value[1:]
        node = self.node(label, opener)
        node.children = self.items(rest)
        return node


def nav_tree(config_text: str, docs_dir: Path) -> list[NavNode]:
    """Return the nav of a ``mkdocs.yml`` as label nodes.

    Unlabelled entries take the page's title, as mkdocs shows them.

    Raises:
        MetadataLoadError: If an unlabelled entry names a missing page.
    """
    nav = parse_mkdocs_config(config_text).get("nav", [])
    return _TreeBuilder(docs_dir).items(nav if isinstance(nav, list) else [])


def walk_nodes(nodes: list[NavNode]) -> list[NavNode]:
    """Every node, depth first."""
    return [n for node in nodes for n in (node, *walk_nodes(node.children))]


def render_tree(nodes: list[NavNode], depth: int = 0) -> str:
    """The label tree an agent sees: labels only, no paths or numbers.

    Numbers invite an agent to answer with a line number of the file it
    read the tree from, so the answer names the labels instead.
    """
    lines: list[str] = []
    for node in nodes:
        lines.append(f"{'  ' * depth}- {node.label}")
        if node.children:
            lines.append(render_tree(node.children, depth + 1))
    return "\n".join(lines)


_TREE_INSTRUCTIONS = """\
You are taking part in a usability test of a documentation website's
navigation. Stay in character as the reader described below. You see ONLY the
site's navigation labels, as an indented tree; you cannot see any page. Do not
use anything you may already know about this project or its repository:
judge only from the labels, as this reader would.

For each task, pick the ONE entry you would click to finish the task, as the
reader would, and give its full path of labels from the top level down,
copied exactly. If no entry looks right, give up rather than guess wildly.

Answer with JSON only, no prose around it:
{"answers": [{"task": "<task id>", "path": ["<top label>", "...", "<entry>"]
or null to give up, "confidence": "high|medium|low",
"why": "<one short sentence>"}]}
"""


def tree_prompt(suite: Suite, persona_id: str, nodes: list[NavNode]) -> str:
    """The full Stage 1 briefing for one persona on one nav."""
    persona = suite.persona(persona_id)
    unknowns = "\n".join(f"- {u}" for u in persona.does_not_know)
    tasks = "\n".join(
        f"- {t.id}: {' '.join(t.prompt.split())}"
        for t in suite.tasks_for(persona_id)
    )
    return (
        f"{_TREE_INSTRUCTIONS}\n"
        f"## Who you are: {persona.name}\n\n{' '.join(persona.brief.split())}\n\n"
        f"What you do not know:\n{unknowns}\n\n"
        f"## The navigation\n\n{render_tree(nodes)}\n\n"
        f"## Your tasks\n\n{tasks}\n"
    )


def _fold(label: str) -> str:
    return " ".join(label.split()).casefold()


def _chains(nodes: list[NavNode], above: list[NavNode]) -> list[list[NavNode]]:
    """Every root-to-node chain, depth first."""
    chains: list[list[NavNode]] = []
    for node in nodes:
        chain = [*above, node]
        chains.append(chain)
        chains.extend(_chains(node.children, chain))
    return chains


def resolve_label_path(
    nodes: list[NavNode], labels: list[str]
) -> list[NavNode]:
    """The chain of nodes a label path names, top level first.

    The last label names the entry; the others locate it. Agents prefix the
    site name or skip a level, so the earlier labels need only appear among
    the entry's ancestors, in order: the entry whose ancestors match the most
    of them wins, and of equals the first in the tree, as a reader scanning
    it would find. Labels match case- and whitespace-insensitively.

    Raises:
        KeyError: If the path is empty or no entry has its last label.
    """
    if not labels:
        raise KeyError("an empty path names no entry")
    wanted = [_fold(label) for label in labels]
    best: list[NavNode] | None = None
    best_score = -1
    for chain in _chains(nodes, []):
        if _fold(chain[-1].label) != wanted[-1]:
            continue
        ancestors = iter(_fold(n.label) for n in chain[:-1])
        score = sum(1 for label in wanted[:-1] if label in ancestors)
        if score > best_score:
            best, best_score = chain, score
    if best is None:
        raise KeyError(f"no entry is labelled {labels[-1]!r}")
    return best


def _home_pages(nodes: list[NavNode]) -> set[str]:
    """The front desk: every top-level leaf that is a page, not a section,
    and the home page even when it opens a group of its own.

    The home page and any external parent-site link are both ``Home`` to a
    reader; an answer that ends there has not left the front door. The home
    page opens a group when the nav puts pages beside it (the lookup page,
    DF-11-021), and stopping on it is still stopping at the front door.
    """
    return {
        n.path
        for n in nodes
        if n.path is not None and (not n.children or n.path == _INDEX_NAME)
    }


def score_tree_answers(
    suite: Suite,
    persona_id: str,
    nodes: list[NavNode],
    answers: list[dict[str, object]],
    run: int = 1,
) -> list[TaskResult]:
    """Score one persona's Stage 1 answers on one nav.

    A task the persona was given but did not answer counts as giving up.

    Raises:
        MetadataLoadError: If an answer names a task the persona was not
            given, or a path the tree does not have.
    """
    by_task: dict[str, dict[str, object]] = {}
    for answer in answers:
        by_task[str(answer.get("task"))] = answer
    given = {t.id for t in suite.tasks_for(persona_id)}
    stray = sorted(set(by_task) - given)
    if stray:
        raise MetadataLoadError(
            f"answers name task(s) {', '.join(stray)} not given to "
            f"{persona_id}",
            path="answers",
        )
    home = _home_pages(nodes)
    results: list[TaskResult] = []
    for task in suite.tasks_for(persona_id):
        answer = by_task.get(task.id, {})
        labels = answer.get("path")
        why = answer.get("why")
        why_text = str(why) if why else None
        if labels is None:
            results.append(
                TaskResult(
                    task=task.id,
                    persona=persona_id,
                    run=run,
                    outcome=Outcome.GAVE_UP,
                    answer=None,
                    why=why_text,
                )
            )
            continue
        if not isinstance(labels, list) or not all(
            isinstance(label, str) for label in labels
        ):
            raise MetadataLoadError(
                f"task {task.id}: path must be a list of labels or null, "
                f"not {labels!r}",
                path="answers",
            )
        try:
            chain = resolve_label_path(nodes, labels)
        except KeyError as exc:
            raise MetadataLoadError(
                f"task {task.id}: {exc.args[0]}", path="answers"
            ) from exc
        chosen = chain[-1]
        destinations = suite.destinations(task)
        if chosen.path in destinations:
            outcome = Outcome.SUCCESS
        elif any(p in destinations for p in chosen.pages()):
            outcome = Outcome.NEAR
        else:
            outcome = Outcome.FAIL
        results.append(
            TaskResult(
                task=task.id,
                persona=persona_id,
                run=run,
                outcome=outcome,
                answer=chosen.path,
                label_path=[n.label for n in chain],
                stalled_at_home=outcome is not Outcome.SUCCESS
                and len(chain) == 1
                and chosen.path in home,
                why=why_text,
            )
        )
    return results
