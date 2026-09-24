"""Find a page's prose uses of glossary terms and the links it makes.

Support for :mod:`vultron.metadata.docs.level_order` (DF-11-002, SG-11). The
check needs two facts about each page: where a concept is first *used* in prose,
and where the page *links* to another page. Both are read from a masked copy of
the page in which everything that is not prose — frontmatter, fenced code,
inline code, ``<code>``/``<pre>`` elements, HTML comments and tags, ``{% %}``
directives, link targets, bare URLs, and reference-link definitions — is
blanked to spaces. Blanking rather than deleting keeps every line and column
where it was, so a finding reports the position in the file the author edits
(MS-17).

Two things still read as prose: an indented code block (four spaces is also
how mkdocs-material nests an admonition's prose, so indentation cannot tell
them apart) and a heading. A term in a heading is a use of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from vultron.metadata.markdown_tables import fenced_lines

#: ``X (Y)`` and ``X (or Y)``: a glossary term with its abbreviation or its
#: alternative name, each matched on its own.
_PAREN_TERM_RE = re.compile(r"^(?P<head>.+?)\s*\((?:or\s+)?(?P<alt>[^()]+)\)$")
_BLOCK_RES = (
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"\{%.*?%\}", re.DOTALL),
    re.compile(r"\{\{.*?\}\}", re.DOTALL),
    re.compile(r"<(code|pre|kbd|samp)\b[^>]*>.*?</\1\s*>", re.DOTALL),
    re.compile(r"(`+)[^\n]*?\1"),
)
_TARGET = r"<?(?P<target>[^)\s>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?"
_INLINE_LINK_RE = re.compile(
    rf"\[(?P<text>[^\[\]]*)\](?P<rest>\(\s*{_TARGET}\s*\))"
)
_REFERENCE_DEF_RE = re.compile(
    r"^[ \t]{0,3}\[(?P<label>[^\]\n]+)\]:[ \t]*<?(?P<target>[^\s>]+)>?.*$",
    re.MULTILINE,
)
#: ``[text][label]``, ``[text][]``, and the shortcut ``[text]``.
_REFERENCE_USE_RE = re.compile(
    r"\[(?P<text>[^\[\]]*)\](?P<rest>\[(?P<label>[^\[\]]*)\])?(?![(:])"
)
_ANCHOR_RE = re.compile(
    r"(?P<open><a\b[^<>]*>)(?P<text>.*?)(?P<close></a\s*>)",
    re.DOTALL | re.IGNORECASE,
)
_HREF_RE = re.compile(r"""\bhref\s*=\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)')""")
_TAG_RE = re.compile(r"</?[A-Za-z][^<>\n]*>")
_URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Position:
    """A 1-based ``line`` and ``column`` in a page's source."""

    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Link:
    """A link to a ``docs/`` page, located by its text.

    Attributes:
        target: The linked page's ``docs/``-relative path.
        position: Where the link starts (its ``[`` or ``<a``).
        start: Offset of the first character of the link text.
        end: Offset just past the link text.
    """

    target: str
    position: Position
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Use:
    """A prose use of a term: where it is and the text used.

    Whitespace runs in ``text``, such as a line break inside the term, are
    collapsed to one space.
    """

    position: Position
    offset: int
    text: str


@dataclass(frozen=True, slots=True)
class ScannedPage:
    """A page reduced to what the level check reads.

    Attributes:
        prose: The page text with every non-prose character blanked.
        links: Every link to a ``docs/`` page, in source order.
    """

    prose: str
    links: tuple[Link, ...]

    def first_link(self, target: str) -> Position | None:
        """Where the page first links to *target*, if it does."""
        return next(
            (link.position for link in self.links if link.target == target),
            None,
        )

    def link_around(self, offset: int) -> str | None:
        """The page linked by the link whose text holds *offset*, if any."""
        return next(
            (
                link.target
                for link in self.links
                if link.start <= offset < link.end
            ),
            None,
        )


def term_forms(term: str) -> tuple[str, ...]:
    """The spellings of a glossary *term* that count as a use of it.

    ``Coordinated Vulnerability Disclosure (CVD)`` is used by either half, and
    ``Semantic Type (or MessageSemantics)`` by either name. Spellings shorter
    than two characters, or holding a ``/``, are dropped: the ``V`` of
    ``V/v`` would match every state table, so no page could usefully claim
    to introduce it.
    """
    match = _PAREN_TERM_RE.match(term)
    forms = (match["head"], match["alt"]) if match else (term,)
    return tuple(
        form.strip()
        for form in forms
        if len(form.strip()) >= 2 and "/" not in form
    )


def term_regex(form: str) -> re.Pattern[str]:
    """Match *form* as a whole word, allowing a plural ``s``/``es``.

    Words may be joined by whitespace or a hyphen, so ``Case Ledger Entry``
    finds "case-ledger entry". A spelling with a lowercase letter is matched
    case-insensitively; an all-capitals spelling such as ``CVD`` or
    ``CASE_MANAGER`` is an identifier and matched exactly, since folding its
    case would find "cvd" in a URL slug that escaped masking.
    """
    body = r"[\s-]+".join(re.escape(word) for word in form.split())
    flags = re.IGNORECASE if any(c.islower() for c in form) else 0
    return re.compile(rf"(?<![\w-]){body}(?:e?s)?(?![\w-])", flags)


def _blank(chars: list[str], start: int, end: int) -> None:
    for i in range(start, end):
        if chars[i] != "\n":
            chars[i] = " "


def _mask_structure(text: str) -> list[str]:
    """Blank frontmatter and fenced code, which are line-shaped."""
    chars = list(text)
    fenced = fenced_lines(text, nested=True)
    offset = 0
    in_frontmatter = text.startswith("---\n")
    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        end = offset + len(line)
        if in_frontmatter:
            _blank(chars, offset, end)
            if number > 1 and line.strip() == "---":
                in_frontmatter = False
        elif number in fenced:
            _blank(chars, offset, end)
        offset = end
    return chars


def _resolve(target: str, source_dir: PurePosixPath) -> str | None:
    """The ``docs/``-relative ``.md`` page a link *target* names, if any."""
    if target.startswith("#") or _SCHEME_RE.match(target):
        return None
    path = target.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return None
    if path.endswith("/"):
        path += "index.md"
    if not path.endswith(".md"):
        return None
    parts: list[str] = []
    for part in (source_dir / path).parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return "/".join(parts)


def _position(text: str, offset: int) -> Position:
    line_start = text.rfind("\n", 0, offset) + 1
    return Position(text.count("\n", 0, offset) + 1, offset - line_start + 1)


def scan_page(text: str, docs_path: str) -> ScannedPage:
    """Mask *text* to its prose and collect the pages it links to.

    Args:
        text: The page's source.
        docs_path: The page's ``docs/``-relative path, against which relative
            link targets resolve (include-markdown rewrites a fragment's links
            relative to the fragment, so a fragment passes its own path).
    """
    chars = _mask_structure(text)
    for pattern in _BLOCK_RES:
        for match in pattern.finditer("".join(chars)):
            _blank(chars, match.start(), match.end())

    source_dir = PurePosixPath(docs_path).parent
    links: list[Link] = []

    def record(target: str, match: re.Match[str]) -> None:
        page = _resolve(target, source_dir)
        if page is not None:
            position = _position(text, match.start())
            links.append(Link(page, position, *match.span("text")))

    masked = "".join(chars)
    definitions: dict[str, str] = {}
    for match in _REFERENCE_DEF_RE.finditer(masked):
        definitions.setdefault(match["label"].strip().lower(), match["target"])
        _blank(chars, match.start(), match.end())
    for match in _INLINE_LINK_RE.finditer(masked):
        record(match["target"], match)
        _blank(chars, match.start(), match.start() + 1)
        _blank(chars, *match.span("rest"))
        _blank(chars, match.end("text"), match.end("text") + 1)
    masked = "".join(chars)
    for match in _REFERENCE_USE_RE.finditer(masked):
        label = (match["label"] or match["text"]).strip().lower()
        if label in definitions:
            record(definitions[label], match)
            _blank(chars, match.start(), match.start() + 1)
            _blank(chars, match.end("text"), match.end())
    masked = "".join(chars)
    for match in _ANCHOR_RE.finditer(masked):
        href = _HREF_RE.search(match["open"])
        if href:
            record(href["dq"] or href["sq"] or "", match)
    for match in _TAG_RE.finditer(masked):
        _blank(chars, match.start(), match.end())
    for match in _URL_RE.finditer("".join(chars)):
        _blank(chars, match.start(), match.end())
    links.sort(key=lambda link: link.start)
    return ScannedPage(prose="".join(chars), links=tuple(links))


def first_use(page: ScannedPage, forms: tuple[str, ...]) -> Use | None:
    """Where *page* first uses any of *forms* in prose, and the text used."""
    best: re.Match[str] | None = None
    for form in forms:
        match = term_regex(form).search(page.prose)
        if match and (best is None or match.start() < best.start()):
            best = match
    if best is None:
        return None
    text = " ".join(best.group().split())
    return Use(_position(page.prose, best.start()), best.start(), text)


def read_page(docs_dir: Path, docs_path: str) -> ScannedPage:
    """Read and scan the page at *docs_path* under *docs_dir*."""
    text = (docs_dir / docs_path).read_text(encoding="utf-8", errors="replace")
    return scan_page(text, docs_path)
