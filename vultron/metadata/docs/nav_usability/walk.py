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
"""Stage 2, the walkthrough: a built site as page text and numbered links."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vultron.metadata.docs.landing_pages import is_url
from vultron.metadata.docs.nav_usability.results import Outcome, TaskResult
from vultron.metadata.docs.nav_usability.suite import Suite
from vultron.metadata.docs.nav_usability.tree import _INDEX_NAME
from vultron.metadata.file_loading import MetadataLoadError

DEFAULT_CLICK_BUDGET = 8


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
    if not href or href.startswith("#") or is_url(href):
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
    """Score a finished Stage 2 session for *task_id*.

    Raises:
        MetadataLoadError: If the suite has no task *task_id*, as when a
            session file is named for no task. It has no path: the caller
            knows which session file it read.
    """
    task = next((t for t in suite.tasks if t.id == task_id), None)
    if task is None:
        raise MetadataLoadError(
            f"names task {task_id!r}, which the suite does not have"
        )
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


_WALK_INSTRUCTIONS = """\
You are taking part in a usability test of a documentation website. Stay in
character as the reader described below. You browse the site ONLY through the
command shown for each task, which prints a page's text and its numbered
links. There is no search. Do not read, list or search any file, and do not
use any other command or tool: judge only from what the pages show, as this
reader would.

For each task, in order:

1. Start: {command} --start {site}
2. Follow links: {command} --go <link number>
   You have {budget} clicks. Going back is not possible; choose carefully.
3. When the page you are on finishes the task, record it:
   {command} --found
   If you cannot find it, or run out of clicks, give up:
   {command} --give-up

Each task has its own session file, named below; pass it to every command
for that task. When every task is recorded, reply with just "done".
"""


def walk_prompt(
    suite: Suite,
    persona_id: str,
    site: Path,
    sessions: Path,
    task_ids: list[str],
    budget: int = DEFAULT_CLICK_BUDGET,
) -> str:
    """The Stage 2 briefing for one persona on one built site.

    Raises:
        KeyError: If a task id is not one of the persona's tasks.
    """
    persona = suite.persona(persona_id)
    tasks = {t.id: t for t in suite.tasks_for(persona_id)}
    missing = [t for t in task_ids if t not in tasks]
    if missing:
        raise KeyError(f"{persona_id} has no task(s) {', '.join(missing)}")
    unknowns = "\n".join(f"- {u}" for u in persona.does_not_know)
    lines = []
    for task_id in task_ids:
        command = (
            "uv run nav-usability walk --session "
            f"{sessions / f'{task_id}.json'}"
        )
        lines.append(
            f"- {task_id}: {' '.join(tasks[task_id].prompt.split())}\n"
            f"  Command: {command}"
        )
    head = _WALK_INSTRUCTIONS.format(
        command="<the task's command>", site=site, budget=budget
    )
    return (
        f"{head}\n"
        f"## Who you are: {persona.name}\n\n{' '.join(persona.brief.split())}\n\n"
        f"What you do not know:\n{unknowns}\n\n"
        "## Your tasks\n\n" + "\n".join(lines) + "\n"
    )
