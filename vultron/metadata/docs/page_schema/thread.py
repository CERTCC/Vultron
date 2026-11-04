"""The ``thread:`` declaration of a ``docs/start/`` page (DF-11-013–016)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
)

from vultron.primitives import NonEmptyString

#: The ``docs/``-relative directory holding the start pages. Every page in it
#: but its ``index.md`` opens one reading-path thread (DF-11-013).
START_DIR = "start"


#: Frontmatter key carrying a start page's thread (DF-11-013).
THREAD_KEY = "thread"


def is_start_page(docs_path: str) -> bool:
    """Whether a ``docs/``-relative POSIX path is a start page.

    A start page is a page directly in :data:`START_DIR` other than its
    ``index.md``, which routes to the start pages rather than opening a thread.
    """
    head, _, name = docs_path.rpartition("/")
    return head == START_DIR and name.endswith(".md") and name != "index.md"


def _check_member_page(value: str) -> str:
    """Accept only a ``docs/``-relative ``.md`` path, with an optional fragment.

    A thread is a path through pages, so an external URL, an absolute path, a
    path climbing out of ``docs/``, or a non-Markdown file is not a member
    (DF-11-013). A link that is not a page belongs in a stage's ``framing``.
    """
    path, hash_, fragment = value.partition("#")
    if urlsplit(value).scheme or value.startswith("/"):
        raise ValueError(
            "must be a docs/-relative page path, not a URL or an absolute "
            "path; put a link that is not a page in the stage's framing"
        )
    if not path.endswith(".md") or ".." in path.split("/"):
        raise ValueError(
            "must name a .md page under docs/, written relative to docs/ "
            "without '..' segments"
        )
    if hash_ and not fragment:
        raise ValueError("has an empty #fragment")
    return value


def _check_single_line(value: str) -> str:
    """Refuse a line break: a heading or a link's text is one line."""
    if "\n" in value or "\r" in value:
        raise ValueError("must be a single line")
    return value


#: A stage title or member label: rendered as a heading or a link's text, so
#: non-blank and on one line.
SingleLine = Annotated[NonEmptyString, AfterValidator(_check_single_line)]


class StageKind(StrEnum):
    """Whether a thread stage's pages are read in order (DF-11-013)."""

    #: Read in any order; rendered as a bulleted list.
    SET = "set"
    #: Read in order; rendered as a numbered list.
    CHAIN = "chain"


class ThreadMember(BaseModel):
    """One page on a reading-path thread.

    Attributes:
        page: ``docs/``-relative page path, optionally with a ``#fragment``.
        blurb: What the reader gets from the page, written for this thread; it
            need not match the page's ``description:``.
        label: The link text, when it should differ from the page's title (a
            link to one section of a page names the section).
    """

    model_config = ConfigDict(extra="forbid")

    page: Annotated[str, AfterValidator(_check_member_page)]
    blurb: NonEmptyString
    label: SingleLine | None = None

    @property
    def path(self) -> str:
        """The member's page, without its fragment."""
        return self.page.partition("#")[0]


class ThreadStage(BaseModel):
    """One stage of a thread: an unordered set or an ordered chain of pages.

    Attributes:
        title: The reader's goal at this stage, never a page type.
        kind: :attr:`StageKind.SET` or :attr:`StageKind.CHAIN`.
        stopping_point: The reader who only needed this far is done.
        framing: Prose shown under the stage's heading, before its pages; a
            link that is not a page lives here.
        members: The stage's pages, in reading order for a chain.
    """

    model_config = ConfigDict(extra="forbid")

    title: SingleLine
    kind: StageKind
    stopping_point: StrictBool = False
    framing: NonEmptyString | None = None
    members: Annotated[list[ThreadMember], Field(min_length=1)]


class ThreadDeclaration(BaseModel):
    """A start page's reading-path thread: its ordered stages (DF-11-013).

    Only the ``thread`` key is validated; the page's other frontmatter belongs
    to :class:`PageFrontmatter`.
    """

    thread: Annotated[list[ThreadStage], Field(min_length=1)]
