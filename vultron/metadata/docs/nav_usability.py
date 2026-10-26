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
``notes/nav-usability-test.md``. This module scripts the parts that must not
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
    walk     take one Stage 2 step in a session
    tally    compare two results files and print the verdict
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from vultron.metadata.base import parse_mkdocs_config
from vultron.metadata.docs.landing_pages import page_title
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
    load_frontmatter,
    load_yaml,
    validate,
)
from vultron.primitives import NonEmptyString

SUITE_PATH = Path("notes/nav-usability/suite.yaml")
_INDEX_NAME = "index.md"
DEFAULT_CLICK_BUDGET = 8


# --------------------------------------------------------------------------
# The suite: personas and tasks, committed before a proposed nav is seen
# --------------------------------------------------------------------------


class Persona(BaseModel):
    """A briefed newcomer, with the things they explicitly do not know."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyString
    name: NonEmptyString
    brief: NonEmptyString
    does_not_know: list[NonEmptyString] = Field(min_length=1)
    start_page: NonEmptyString
    """The start page that opens this reader's thread: the destination of
    every ``thread`` task, on any nav that carries it."""


class Task(BaseModel):
    """A findability task, with every page that correctly answers it."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyString
    persona: NonEmptyString
    kind: Literal["lookup", "thread"]
    prompt: NonEmptyString
    destinations: list[NonEmptyString] = Field(default_factory=list)
    source: NonEmptyString


class Suite(BaseModel):
    """The personas and tasks; every task names a known persona."""

    model_config = ConfigDict(extra="forbid")

    personas: list[Persona] = Field(min_length=1)
    tasks: list[Task] = Field(min_length=1)

    def persona(self, persona_id: str) -> Persona:
        for persona in self.personas:
            if persona.id == persona_id:
                return persona
        raise KeyError(f"no persona {persona_id!r} in the suite")

    def tasks_for(self, persona_id: str) -> list[Task]:
        return [t for t in self.tasks if t.persona == persona_id]

    def destinations(self, task: Task) -> list[str]:
        """The pages that answer *task*: its own, or its persona's start."""
        if task.kind == "thread":
            return [self.persona(task.persona).start_page]
        return list(task.destinations)


def _suite_faults(suite: Suite) -> list[str]:
    """Every way *suite* breaks the test's rules, not just the first."""
    faults: list[str] = []
    persona_ids = [p.id for p in suite.personas]
    task_ids = [t.id for t in suite.tasks]
    for ids, what in ((persona_ids, "persona"), (task_ids, "task")):
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            faults.append(f"repeats {what} id(s) {', '.join(repeated)}")
    for task in suite.tasks:
        if task.persona not in persona_ids:
            faults.append(
                f"task {task.id} names unknown persona {task.persona!r}"
            )
        if task.kind == "lookup" and not task.destinations:
            faults.append(f"lookup task {task.id} names no destination")
        if task.kind == "thread" and task.destinations:
            faults.append(
                f"thread task {task.id} declares destinations; a thread "
                "task's destination is its persona's start_page"
            )
    for persona_id in persona_ids:
        if not any(t.kind == "thread" for t in suite.tasks_for(persona_id)):
            faults.append(
                f"persona {persona_id} has no 'follow your thread' task "
                "(ADR-0136 § Validation)"
            )
    return faults


def load_suite(path: Path) -> Suite:
    """Load and cross-check the suite at *path*.

    Raises:
        MetadataLoadError: If the file is not valid YAML or does not match
            :class:`Suite`.
        MetadataLoadErrors: One failure per rule the suite breaks: a task
            naming an unknown persona, a lookup task with no destination, a
            thread task declaring its own, a persona with no thread task, or
            a repeated id.
    """
    suite = validate(Suite, load_yaml(path), path=path)
    faults = _suite_faults(suite)
    if faults:
        raise MetadataLoadErrors(
            [MetadataLoadError(f, path=str(path)) for f in faults]
        )
    return suite


# --------------------------------------------------------------------------
# Stage 1: the nav as a label tree
# --------------------------------------------------------------------------


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


def _is_url(value: str) -> bool:
    return "://" in value


def _split(item: object) -> tuple[str | None, object]:
    if isinstance(item, dict) and len(item) == 1:
        ((label, value),) = item.items()
        return str(label), value
    return None, item


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
            label, value = _split(item)
            if isinstance(value, list):
                nodes.append(self.group(label or "", value))
            elif isinstance(value, str):
                shown = label or (
                    value if _is_url(value) else self.title(value)
                )
                nodes.append(self.node(shown, value))
        return nodes

    def group(self, label: str, value: list[object]) -> NavNode:
        """A labelled group; an ``index.md`` first member becomes its link,
        as the theme's section indexes render it."""
        opener: str | None = None
        rest = value
        if value:
            first_label, first = _split(value[0])
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


class Outcome(StrEnum):
    """How one answer scored."""

    SUCCESS = "success"
    """The answer opens a destination page."""
    NEAR = "near"
    """The answer is a group holding a destination, not the page itself."""
    FAIL = "fail"
    GAVE_UP = "gave-up"


class TaskResult(BaseModel):
    """One scored answer, for one task, persona and nav."""

    model_config = ConfigDict(extra="forbid")

    task: str
    persona: str
    run: int = 1
    stage: Literal[1, 2] = 1
    outcome: Outcome
    answer: str | None = None
    """The page the answer opened (Stage 1) or ended on (Stage 2)."""
    label_path: list[str] = Field(default_factory=list)
    clicks: int | None = None
    stalled_at_home: bool = False
    why: str | None = None


class Results(BaseModel):
    """Every scored answer for one nav, keyed on its hash."""

    model_config = ConfigDict(extra="forbid")

    nav: str
    """A name for the nav, such as ``baseline`` or ``proposed``."""
    nav_hash: str
    source: str
    """Where the nav came from: a commit, or a branch at a commit."""
    model: str | None = None
    results: list[TaskResult] = Field(default_factory=list)


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
    """The front desk: every top-level leaf that is a page, not a section.

    The home page and any external parent-site link are both ``Home`` to a
    reader; an answer that ends there has not left the front door.
    """
    return {n.path for n in nodes if not n.children and n.path is not None}


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


# --------------------------------------------------------------------------
# Stage 2: a walkthrough of the built site, text and numbered links only
# --------------------------------------------------------------------------


class _PageReader(HTMLParser):
    """Collect a built page's title, main-content text and links.

    The theme's search box and any ``search`` link are dropped: the
    walkthrough has no site search (ADR-0136 § Validation).
    """

    _SKIP = {"script", "style", "noscript", "svg", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._skip = 0
        self._article = 0
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "article":
            self._article += 1
        elif tag == "a":
            self._href = dict(attrs).get("href")
            self._anchor = []
        elif self._article and tag in {
            "p",
            "li",
            "h1",
            "h2",
            "h3",
            "h4",
            "tr",
            "br",
        }:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag == "article":
            self._article = max(0, self._article - 1)
        elif tag == "a" and self._href is not None:
            label = " ".join("".join(self._anchor).split())
            if label:
                self.links.append((label, self._href))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._href is not None:
            self._anchor.append(data)
        if self._article:
            self.text.append(data)


@dataclass
class PageView:
    """What a walkthrough agent sees of one page."""

    path: str
    title: str
    text: str
    links: list[tuple[str, str]]


def _resolve_href(current: str, href: str) -> str | None:
    """The site-relative page a link opens, or ``None`` if it leaves the site.

    *current* is a site-relative page such as ``topics/index.html``.
    """
    if not href or href.startswith(("#", "mailto:", "javascript:")):
        return None
    if _is_url(href):
        return None
    target = href.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None
    joined = posixpath.normpath(
        posixpath.join(posixpath.dirname(current), target)
    )
    if joined.startswith(".."):
        return None
    if joined in {".", ""}:
        return _INDEX_NAME.replace(".md", ".html")
    if not posixpath.splitext(joined)[1]:
        joined = posixpath.join(joined, "index.html")
    return joined


def read_page(site: Path, rel: str, text_limit: int = 2500) -> PageView:
    """Read the built page *rel* (site-relative) as text and numbered links.

    Links to assets, external sites and the search page are dropped. Each
    target is listed once, at its first position, with every distinct label
    the page gives it: a tab and a card's "Start here" naming one page are
    one link with both names.

    Raises:
        FileNotFoundError: If the page is not in the built site.
    """
    path = site / rel
    if not path.is_file():
        raise FileNotFoundError(f"{rel} is not a page of the built site")
    reader = _PageReader()
    reader.feed(path.read_text("utf-8"))
    labels: dict[str, list[str]] = {}
    for label, href in reader.links:
        target = _resolve_href(rel, href)
        if (
            target is None
            or not target.endswith(".html")
            or target.startswith(("search", "assets/"))
            or target == rel
        ):
            continue
        seen = labels.setdefault(target, [])
        if label not in seen:
            seen.append(label)
    links = [(" / ".join(names), target) for target, names in labels.items()]
    raw = "".join(reader.text)
    paragraphs = [" ".join(line.split()) for line in raw.split("\n")]
    text = "\n".join(p for p in paragraphs if p)
    if len(text) > text_limit:
        text = text[:text_limit].rstrip() + " …"
    return PageView(
        path=rel, title=" ".join(reader.title.split()), text=text, links=links
    )


class WalkState(BaseModel):
    """A Stage 2 session: where the agent is, and the path it took."""

    model_config = ConfigDict(extra="forbid")

    site: str
    budget: int = DEFAULT_CLICK_BUDGET
    history: list[str] = Field(default_factory=list)
    links: list[tuple[str, str]] = Field(default_factory=list)
    finished: Literal["found", "gave-up", "out-of-clicks"] | None = None

    @property
    def clicks(self) -> int:
        return max(0, len(self.history) - 1)


class Walk:
    """One persona's walkthrough of one task, persisted between steps."""

    def __init__(self, session: Path) -> None:
        self.session = session

    def start(self, site: Path, budget: int = DEFAULT_CLICK_BUDGET) -> str:
        state = WalkState(site=str(site), budget=budget)
        return self._show(state, "index.html")

    def go(self, choice: int) -> str:
        state = self._load()
        if state.finished:
            return f"The walk is over ({state.finished})."
        if not 1 <= choice <= len(state.links):
            return f"There is no link {choice}; pick 1-{len(state.links)}."
        if state.clicks >= state.budget:
            state.finished = "out-of-clicks"
            self._save(state)
            return "You are out of clicks. The walk is over."
        return self._show(state, state.links[choice - 1][1])

    def finish(self, outcome: Literal["found", "gave-up"]) -> str:
        state = self._load()
        state.finished = state.finished or outcome
        self._save(state)
        return f"Recorded: {state.finished} at {state.history[-1]}."

    def state(self) -> WalkState:
        return self._load()

    def _show(self, state: WalkState, rel: str) -> str:
        view = read_page(Path(state.site), rel)
        state.history.append(rel)
        state.links = view.links
        self._save(state)
        links = "\n".join(
            f"[{i}] {label}" for i, (label, _) in enumerate(view.links, 1)
        )
        left = state.budget - state.clicks
        return (
            f"# {view.title}\n\n{view.text}\n\n## Links\n\n{links}\n\n"
            f"(clicks used: {state.clicks}/{state.budget}; {left} left)"
        )

    def _load(self) -> WalkState:
        return WalkState.model_validate_json(self.session.read_text("utf-8"))

    def _save(self, state: WalkState) -> None:
        self.session.write_text(state.model_dump_json(indent=2), "utf-8")


def site_page(docs_path: str) -> str:
    """The built-site page for a ``docs/``-relative source page."""
    stem, _ext = posixpath.splitext(docs_path)
    if posixpath.basename(stem) == "index":
        return f"{stem}.html"
    return f"{stem}/index.html"


def score_walk(
    suite: Suite, task_id: str, state: WalkState, run: int = 1
) -> TaskResult:
    """Score a finished Stage 2 session for *task_id*."""
    task = next(t for t in suite.tasks if t.id == task_id)
    wanted = {site_page(p) for p in suite.destinations(task)}
    final = state.history[-1] if state.history else None
    if state.finished == "found" and final in wanted:
        outcome = Outcome.SUCCESS
    elif state.finished == "found":
        outcome = Outcome.FAIL
    else:
        outcome = Outcome.GAVE_UP
    return TaskResult(
        task=task.id,
        persona=task.persona,
        run=run,
        stage=2,
        outcome=outcome,
        answer=final,
        label_path=list(state.history),
        clicks=state.clicks,
        stalled_at_home=outcome is not Outcome.SUCCESS and state.clicks == 0,
    )


# --------------------------------------------------------------------------
# Tally and verdict
# --------------------------------------------------------------------------


@dataclass
class Verdict:
    """The pass rule applied to two navs' results for one stage."""

    baseline_success: int
    proposed_success: int
    total: int
    stalls: list[str]
    worse: list[str]
    """Tasks the proposed nav lost that the baseline won."""
    better: list[str]

    @property
    def passed(self) -> bool:
        return (
            self.proposed_success >= self.baseline_success and not self.stalls
        )


def _success_rate(results: list[TaskResult]) -> dict[str, float]:
    by_task: dict[str, list[bool]] = {}
    for r in results:
        by_task.setdefault(r.task, []).append(r.outcome is Outcome.SUCCESS)
    return {task: sum(wins) / len(wins) for task, wins in by_task.items()}


def tally(
    baseline: Results, proposed: Results, stage: Literal[1, 2] = 1
) -> Verdict:
    """Apply the pass rule: no worse on task success, no stall at home.

    Repeated runs of a task are averaged, so a task counts as a success in
    proportion to the runs that found it.
    """
    base = _success_rate([r for r in baseline.results if r.stage == stage])
    prop = _success_rate([r for r in proposed.results if r.stage == stage])
    tasks = sorted(set(base) | set(prop))
    stalls = sorted(
        {
            r.task
            for r in proposed.results
            if r.stage == stage and r.stalled_at_home
        }
    )
    return Verdict(
        baseline_success=round(sum(base.get(t, 0.0) for t in tasks)),
        proposed_success=round(sum(prop.get(t, 0.0) for t in tasks)),
        total=len(tasks),
        stalls=stalls,
        worse=[t for t in tasks if prop.get(t, 0.0) < base.get(t, 0.0)],
        better=[t for t in tasks if prop.get(t, 0.0) > base.get(t, 0.0)],
    )


def load_results(path: Path) -> Results:
    return Results.model_validate(yaml.safe_load(path.read_text("utf-8")))


def save_results(path: Path, results: Results) -> None:
    data = results.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        "utf-8",
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _config_text(path: Path) -> str:
    return path.read_text("utf-8")


def _cmd_tree(args: argparse.Namespace) -> None:
    text = _config_text(args.config)
    print(f"nav hash: {nav_hash(text)}")
    print(render_tree(nav_tree(text, args.docs)))


def _cmd_prompt(args: argparse.Namespace) -> None:
    suite = load_suite(args.suite)
    nodes = nav_tree(_config_text(args.config), args.docs)
    print(tree_prompt(suite, args.persona, nodes))


def _cmd_score(args: argparse.Namespace) -> None:
    suite = load_suite(args.suite)
    text = _config_text(args.config)
    nodes = nav_tree(text, args.docs)
    if args.results.is_file():
        results = load_results(args.results)
        if results.nav_hash != nav_hash(text):
            raise SystemExit(
                f"{args.results} holds results for nav {results.nav_hash}, "
                f"not {nav_hash(text)}; start a new results file"
            )
    else:
        results = Results(
            nav=args.nav,
            nav_hash=nav_hash(text),
            source=args.source,
            model=args.model,
        )
    answers = json.loads(args.answers.read_text("utf-8"))["answers"]
    scored = score_tree_answers(suite, args.persona, nodes, answers, args.run)
    results.results = [
        r
        for r in results.results
        if not (
            r.stage == 1 and r.persona == args.persona and r.run == args.run
        )
    ] + scored
    save_results(args.results, results)
    for r in scored:
        print(f"{r.task} {r.outcome.value} {' > '.join(r.label_path)}")


def _cmd_walk(args: argparse.Namespace) -> None:
    walk = Walk(args.session)
    if args.start:
        print(walk.start(args.start, args.budget))
    elif args.go is not None:
        print(walk.go(args.go))
    elif args.found:
        print(walk.finish("found"))
    elif args.give_up:
        print(walk.finish("gave-up"))
    else:
        raise SystemExit("walk needs one of --start, --go, --found, --give-up")


def _cmd_tally(args: argparse.Namespace) -> None:
    verdict = tally(
        load_results(args.baseline), load_results(args.proposed), args.stage
    )
    print(
        f"stage {args.stage}: baseline {verdict.baseline_success}/{verdict.total}, "
        f"proposed {verdict.proposed_success}/{verdict.total}"
    )
    print(f"worse: {', '.join(verdict.worse) or 'none'}")
    print(f"better: {', '.join(verdict.better) or 'none'}")
    print(f"stalls at home: {', '.join(verdict.stalls) or 'none'}")
    print("PASS" if verdict.passed else "FAIL")
    if not verdict.passed:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nav-usability",
        description="The agent usability test that gates a nav change.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def nav_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", type=Path, default=Path("mkdocs.yml"))
        p.add_argument("--docs", type=Path, default=Path("docs"))

    tree = sub.add_parser("tree", help="print the nav hash and label tree")
    nav_args(tree)
    tree.set_defaults(func=_cmd_tree)

    prompt = sub.add_parser(
        "prompt", help="print a persona's Stage 1 briefing"
    )
    nav_args(prompt)
    prompt.add_argument("--suite", type=Path, default=SUITE_PATH)
    prompt.add_argument("--persona", required=True)
    prompt.set_defaults(func=_cmd_prompt)

    score = sub.add_parser("score", help="score Stage 1 answers")
    nav_args(score)
    score.add_argument("--suite", type=Path, default=SUITE_PATH)
    score.add_argument("--persona", required=True)
    score.add_argument("--answers", type=Path, required=True)
    score.add_argument("--results", type=Path, required=True)
    score.add_argument("--nav", required=True)
    score.add_argument("--source", required=True)
    score.add_argument("--model")
    score.add_argument("--run", type=int, default=1)
    score.set_defaults(func=_cmd_score)

    walk = sub.add_parser("walk", help="take one Stage 2 step")
    walk.add_argument("--session", type=Path, required=True)
    walk.add_argument("--start", type=Path, metavar="SITE")
    walk.add_argument("--budget", type=int, default=DEFAULT_CLICK_BUDGET)
    walk.add_argument("--go", type=int, metavar="LINK")
    walk.add_argument("--found", action="store_true")
    walk.add_argument("--give-up", action="store_true")
    walk.set_defaults(func=_cmd_walk)

    tally_p = sub.add_parser("tally", help="compare two navs' results")
    tally_p.add_argument("--baseline", type=Path, required=True)
    tally_p.add_argument("--proposed", type=Path, required=True)
    tally_p.add_argument("--stage", type=int, choices=(1, 2), default=1)
    tally_p.set_defaults(func=_cmd_tally)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (MetadataLoadError, MetadataLoadErrors) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover
    main()
