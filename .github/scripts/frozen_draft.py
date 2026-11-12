#!/usr/bin/env python3
"""Build and check the frozen archive of a released Protocol Specification draft.

ADR-0188; DOCBW-08-013 to DOCBW-08-018 and DOCBW-08-021 in
``specs/docs-build-workflow.yaml``. The promote workflow
(``promote_release.yml``) runs main's copy of this script twice:

- ``build``, in the job that built the site at the promoted commit and holds
  no token that can write (DOCBW-08-019). It takes the rendered
  ``reference/vultron-spec/`` pages and every file they load, stamps each
  page with the frozen banner, points every link that leaves the
  specification at the live site (``site_url``), and writes
  ``vultron-spec-draft-N.tar.gz`` with its SHA-256 manifest
  ``vultron-spec-draft-N.sha256``.
- ``verify``, through :func:`verify_archive`, in the job that can write
  (``release.py promote``), before it pushes the release tag or creates the
  release (DOCBW-08-021). It unpacks the real archive into an empty folder,
  refusing any member that could write outside it, and fails when a relative
  reference of a page leaves the tree or when the tree is not exactly what
  the manifest lists.

The archive's root is the specification's root: the page built at
``reference/vultron-spec/index.html`` is ``index.html`` in the archive. A
file a page loads from elsewhere in the site (a stylesheet, a script, an
image) is copied below :data:`BUNDLE_DIR`, keeping its site path, so its own
relative references still resolve.

Standard library only: the scripts run as ``python3 -I`` from a sparse
checkout of ``.github/scripts``, so the reference rules of
``vultron/metadata/docs/links.py`` (the ``srcset`` candidate grammar, the
scheme test) are restated here rather than imported.

Material's ``__config`` keeps its ``base``, so a frozen page served at
``spec/draft-N/`` searches the live site's index, like its other links that
leave the specification; the search worker it names is bundled, so a later
change of the live worker does not break the page.

Usage:
  frozen_draft.py build --site DIR --out DIR --draft draft-N --release TAG
      --commit SHA --publish-tag TAG [--built YYYY-MM-DD]
  frozen_draft.py verify --archive FILE --manifest FILE --into DIR
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import io
import json
import posixpath
import re
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

#: Where the specification's pages are in the built site.
SPEC_DIR = "reference/vultron-spec"
#: The archive folder that holds the files the pages load from elsewhere in
#: the site, below their site paths.
BUNDLE_DIR = "_site"
#: The attributes whose references the archive keeps working (DOCBW-08-015).
REFERENCE_ATTRIBUTES = ("href", "src", "srcset")
#: The class of the banner every frozen page carries (DOCBW-08-017).
BANNER_CLASS = "vultron-frozen-banner"
#: The class of the footer paragraph that names the publish (DOCBW-06-031);
#: ``overrides/partials/copyright.html`` sets it.
FOOTER_CLASS = "build-footer"

# What a URL path keeps unescaped: RFC 3986's sub-delims, ":" and "@".
_PATH_SAFE = "/!$&'()*+,;=:@~"
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_DRAFT = re.compile(r"^draft-[1-9][0-9]*$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_MANIFEST_LINE = re.compile(r"^([0-9a-f]{64}) [ *](.+)$")
# One attribute of a start tag as written: name, and a value if it has one.
# It follows white space or the closing quote of the previous value.
_ATTRIBUTE = re.compile(
    r"""(?<=[\s"'])([^\s"'>/=]+)(\s*=\s*)("[^"]*"|'[^']*'|[^\s"'=<>`]+)"""
)
# A stylesheet's references: ``url(...)`` and ``@import "..."``.
_CSS_REFERENCE = re.compile(
    r"""url\(\s*(["']?)([^"')]+)\1\s*\)|@import\s+(["'])([^"']+)\3"""
)
# One ``srcset`` candidate, as HTML splits them: a URL may hold commas
# (``data:`` URIs), and descriptors follow it (links.py's rule).
_SRCSET_CANDIDATE = re.compile(r"[\s,]*(\S*[^\s,])(?:,+|[^,]*,?)")
_CONFIG = re.compile(
    r"""(<script id="__config" type="application/json">)(.*?)(</script>)""",
    re.DOTALL,
)
_CANONICAL = re.compile(
    r"""<link\b[^>]*\brel=["']?canonical["']?[^>]*>""", re.IGNORECASE
)
_HREF = re.compile(r"""\bhref=["']([^"']+)["']""", re.IGNORECASE)


class FrozenDraftError(ValueError):
    """An archive could not be built, or failed its checks.

    Every fault found is listed, not only the first (EH-07-001).
    """

    def __init__(self, faults: Sequence[str]) -> None:
        self.faults = list(faults)
        super().__init__("\n".join(self.faults))


def archive_name(version: str) -> str:
    """The archive's file name for draft *version*."""
    return f"vultron-spec-{version}.tar.gz"


def manifest_name(version: str) -> str:
    """The manifest's file name for draft *version*."""
    return f"vultron-spec-{version}.sha256"


# --- references ---------------------------------------------------------------


def is_relative(reference: str) -> bool:
    """Whether *reference* is a relative path reference.

    An empty reference, a fragment or query of the page itself, a
    scheme-relative or root-absolute path and any URL with a scheme
    (``https:``, ``mailto:``, ``data:``) are not.
    """
    path = split_reference(reference)[0]
    return bool(path) and not (
        path.startswith("/") or _SCHEME.match(path) is not None
    )


def split_reference(reference: str) -> tuple[str, str]:
    """``(path, rest)``: *reference* split before its query or fragment."""
    reference = reference.strip()
    cut = min(
        (i for i in (reference.find("?"), reference.find("#")) if i >= 0),
        default=len(reference),
    )
    return reference[:cut], reference[cut:]


def _srcset_spans(value: str) -> list[tuple[int, int]]:
    """Where each candidate URL of a ``srcset`` value starts and ends."""
    spans = []
    position = 0
    while (candidate := _SRCSET_CANDIDATE.match(value, position)) and (
        candidate.end() > position
    ):
        spans.append(candidate.span(1))
        position = candidate.end()
    return spans


def srcset_references(value: str) -> list[str]:
    """The URL of each candidate of a ``srcset`` value."""
    return [value[start:end] for start, end in _srcset_spans(value)]


def _rewrite_srcset(value: str, rewrite: Callable[[str], str]) -> str:
    pieces = []
    last = 0
    for start, end in _srcset_spans(value):
        pieces += [value[last:start], rewrite(value[start:end])]
        last = end
    return "".join([*pieces, value[last:]])


def resolve(reference: str, owner: str) -> str | None:
    """The tree path *reference*, written in the file *owner*, names.

    Both are POSIX paths relative to one root; the query and fragment are
    dropped and the path is unescaped. ``""`` is the root itself, and
    ``None`` a path that climbs above it.
    """
    path = split_reference(reference)[0]
    target = posixpath.normpath(
        posixpath.join(posixpath.dirname(owner), unquote(path))
    )
    if target == ".." or target.startswith("../"):
        return None
    return "" if target == "." else target


def file_of(root: Path, target: str) -> str | None:
    """The file *target* names below *root*: itself, or its folder's index."""
    path = root / target if target else root
    if path.is_dir() and (path / "index.html").is_file():
        return posixpath.join(target, "index.html") if target else "index.html"
    if target and path.is_file():
        return target
    return None


@dataclass
class _StartTag:
    offset: int
    text: str
    tag: str
    attributes: list[tuple[str, str | None]]


class _TagScanner(HTMLParser):
    """Collects every start tag of a page, with where it starts."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[_StartTag] = []
        self._lines = [0]
        for match in re.finditer("\n", text):
            self._lines.append(match.end())
        self.feed(text)
        self.close()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        line, column = self.getpos()
        raw = self.get_starttag_text() or ""
        self.tags.append(
            _StartTag(self._lines[line - 1] + column, raw, tag, attrs)
        )

    handle_startendtag = handle_starttag


def page_references(text: str) -> list[str]:
    """Every ``href``, ``src`` and ``srcset`` URL of the page *text*."""
    found: list[str] = []
    for tag in _TagScanner(text).tags:
        for name, value in tag.attributes:
            if value is None or name not in REFERENCE_ATTRIBUTES:
                continue
            if name == "srcset":
                found.extend(srcset_references(value))
            else:
                found.append(value)
    return found


def _rewrite_tag(raw: str, rewrite: Callable[[str], str]) -> str:
    """*raw* with each reference attribute's value passed through *rewrite*."""

    def one(match: re.Match[str]) -> str:
        name, equals, quoted = match.groups()
        if name.lower() not in REFERENCE_ATTRIBUTES:
            return match.group(0)
        value = html.unescape(
            quoted[1:-1] if quoted[:1] in "\"'" and quoted else quoted
        )
        if name.lower() == "srcset":
            new = _rewrite_srcset(value, rewrite)
        else:
            new = rewrite(value)
        if new == value:
            return match.group(0)
        return f'{name}{equals}"{html.escape(new, quote=True)}"'

    return _ATTRIBUTE.sub(one, raw)


# --- building -----------------------------------------------------------------


@dataclass(frozen=True)
class FrozenDraft:
    """What one frozen archive is a copy of: the banner's facts."""

    version: str
    release: str
    commit: str
    publish_tag: str
    built: date

    def problems(self) -> list[str]:
        faults = []
        if not _DRAFT.match(self.version):
            faults.append(f"{self.version!r} is not a draft-N version")
        if not _SHA.match(self.commit):
            faults.append(f"{self.commit!r} is not a full commit SHA")
        if not self.release or not self.publish_tag:
            faults.append("the release tag and the publish tag are required")
        return faults


def banner_html(draft: FrozenDraft) -> str:
    """The banner every frozen page carries (DOCBW-08-017)."""
    facts = html.escape(
        f"Frozen copy of the Vultron Protocol Specification {draft.version}, "
        f"as released in {draft.release}: commit {draft.commit}, built "
        f"{draft.built.isoformat()} (UTC)."
    )
    note = html.escape(
        "These pages never change. Their links that leave the specification "
        "go to the live site, which changes."
    )
    return (
        f'<div class="{BANNER_CLASS}" role="note" style="background:#fff3cd;'
        "color:#1a1a1a;border-bottom:2px solid #b38600;padding:0.6em 1em;"
        f'font-size:0.8rem;line-height:1.4"><p style="margin:0">'
        f"<strong>{facts}</strong> {note}</p></div>"
    )


@dataclass
class _Builder:
    site: Path
    draft: FrozenDraft
    site_url: str
    files: dict[str, bytes] = field(default_factory=dict)
    faults: list[str] = field(default_factory=list)
    _queue: list[str] = field(default_factory=list)

    # A site path is POSIX, relative to the site root, with no leading "./".

    def archive_path(self, site_path: str) -> str:
        if site_path == SPEC_DIR:
            return ""
        if site_path.startswith(SPEC_DIR + "/"):
            return site_path.removeprefix(SPEC_DIR + "/")
        return f"{BUNDLE_DIR}/{site_path}"

    def _in_spec(self, site_path: str) -> bool:
        return site_path == SPEC_DIR or site_path.startswith(SPEC_DIR + "/")

    def reference(self, reference: str, owner: str) -> str:
        """*reference*, written in the site file *owner*, for the archive.

        A reference inside the specification from a specification file is
        kept as written: the archive keeps the specification's layout. A
        page elsewhere becomes its live URL (DOCBW-08-016); any other file
        elsewhere is copied below :data:`BUNDLE_DIR` and referenced there.
        """
        if not is_relative(reference):
            return reference
        target = resolve(reference, owner)
        if target is None:
            self.faults.append(f"{owner}: {reference!r} leaves the site")
            return reference
        found = file_of(self.site, target)
        if found is None:
            self.faults.append(
                f"{owner}: {reference!r} names no file of the site"
            )
            return reference
        rest = split_reference(reference)[1]
        folder = found != target  # the reference names a folder's index page
        if found.endswith(".html") and not self._in_spec(target):
            slash = "/" if folder and target else ""
            return (
                self.site_url + quote(target, safe=_PATH_SAFE) + slash + rest
            )
        if not self._in_spec(target):
            self._queue.append(found)
        mapped = self.archive_path(found)
        if folder:
            mapped = posixpath.dirname(mapped)
        start = posixpath.dirname(self.archive_path(owner))
        if resolve(reference, self.archive_path(owner)) == mapped:
            return reference  # it already works in the archive's layout
        new = posixpath.relpath(mapped or ".", start or ".")
        if folder:
            new = "./" if new == "." else new + "/"
        return quote(new, safe=_PATH_SAFE) + rest

    def _redirect(self, site_path: str, tag: _StartTag) -> bool:
        """Whether *tag* is a redirect page's refresh; fault one that leaves.

        A redirect stub's target is in a ``content`` attribute and a script,
        which the archive does not rewrite, so a stub may only point inside
        the specification.
        """
        attributes = {name: value or "" for name, value in tag.attributes}
        if tag.tag != "meta" or attributes.get("http-equiv", "").lower() != (
            "refresh"
        ):
            return False
        url = attributes.get("content", "").partition("url=")[2].strip()
        target = resolve(url, site_path) if is_relative(url) else None
        if target is None or not self._in_spec(target):
            self.faults.append(
                f"{site_path}: redirects to {url!r}, outside the "
                "specification, which its frozen copy cannot follow"
            )
        return True

    def page(self, site_path: str, text: str) -> str:
        scanner = _TagScanner(text)
        pieces: list[str] = []
        last = 0
        body = False
        redirect = False
        for tag in scanner.tags:
            redirect = self._redirect(site_path, tag) or redirect
            pieces.append(text[last : tag.offset])
            pieces.append(
                _rewrite_tag(tag.text, lambda r: self.reference(r, site_path))
            )
            last = tag.offset + len(tag.text)
            if tag.tag == "body" and not body:
                pieces.append(banner_html(self.draft))
                body = True
        pieces.append(text[last:])
        text = _CONFIG.sub(
            lambda m: (
                m.group(1) + self._config(site_path, m.group(2)) + m.group(3)
            ),
            "".join(pieces),
        )
        pieces = [text]
        if not body:
            self.faults.append(f"{site_path}: the page has no <body>")
        if not redirect:  # a redirect stub has no footer
            self._check_footer(site_path, text)
        return "".join(pieces)

    def _check_footer(self, site_path: str, text: str) -> None:
        """Each page names the publish and the release (DOCBW-08-014)."""
        start = text.find(f'class="{FOOTER_CLASS}"')
        footer = text[start : text.find("</p>", start)] if start >= 0 else ""
        for tag in (self.draft.publish_tag, self.draft.release):
            if f">{html.escape(tag)}</a>" not in footer:
                self.faults.append(
                    f"{site_path}: the page footer does not name {tag}"
                )

    def _config(self, site_path: str, text: str) -> str:
        """Material's ``__config``, with its search worker bundled."""
        try:
            config = json.loads(text)
        except ValueError:
            self.faults.append(f"{site_path}: its __config is not JSON")
            return text
        worker = config.get("search")
        if not isinstance(worker, str):
            return text
        new = self.reference(worker, site_path)
        if new == worker:
            return text
        config["search"] = new
        return json.dumps(config).replace("</", "<\\/")

    def stylesheet(self, site_path: str, text: str) -> str:
        def one(match: re.Match[str]) -> str:
            url_quote, url, import_quote, imported = match.groups()
            reference = url if url is not None else imported
            new = self.reference(reference, site_path)
            if new == reference:
                return match.group(0)
            if url is not None:
                return f"url({url_quote}{new}{url_quote})"
            return f"@import {import_quote}{new}{import_quote}"

        return _CSS_REFERENCE.sub(one, text)

    def add(self, site_path: str) -> None:
        archive = self.archive_path(site_path)
        if archive in self.files:
            return
        source = self.site / site_path
        if source.is_symlink() or not source.is_file():
            self.faults.append(f"{site_path}: not a regular file")
            return
        data = source.read_bytes()
        self.files[archive] = data  # claimed before a reference returns here
        if not site_path.endswith((".html", ".css")):
            return
        text = _text(data)
        if text is None:
            self.faults.append(f"{site_path}: not UTF-8 text")
            return
        if site_path.endswith(".html"):
            text = self.page(site_path, text)
        else:
            text = self.stylesheet(site_path, text)
        self.files[archive] = text.encode("utf-8")

    def run(self) -> dict[str, bytes]:
        spec = self.site / SPEC_DIR
        for path in sorted(p for p in spec.rglob("*") if not p.is_dir()):
            site_path = path.relative_to(self.site).as_posix()
            if self.archive_path(site_path).split("/")[0] == BUNDLE_DIR:
                self.faults.append(
                    f"{site_path}: the specification has a {BUNDLE_DIR}/ "
                    "folder, which the archive keeps for the files its "
                    "pages load"
                )
                continue
            self.add(site_path)
        while self._queue:
            self.add(self._queue.pop(0))
        for name in self.files:
            if "\n" in name or "\\" in name:
                self.faults.append(
                    f"{name!r}: a name the manifest cannot hold"
                )
        return self.files


def _text(data: bytes) -> str | None:
    """*data* as UTF-8 text, or ``None`` when it is not."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def site_url_of(index: Path) -> str:
    """The live site's root URL, from the specification index's canonical link.

    The build writes ``<link rel="canonical">`` from ``site_url``, so the
    archive points at the site the release built, not at a URL given twice.
    """
    for link in _CANONICAL.findall(index.read_text(encoding="utf-8")):
        found = _HREF.search(link)
        if found and found.group(1).rstrip("/").endswith(SPEC_DIR):
            url = found.group(1).rstrip("/").removesuffix(SPEC_DIR)
            if url.startswith(("https://", "http://")):
                return url
    raise FrozenDraftError(
        [
            f"{index}: no canonical link ending in {SPEC_DIR}/, so the "
            "site_url the links outside the specification need is unknown"
        ]
    )


def frozen_files(site: Path, draft: FrozenDraft) -> dict[str, bytes]:
    """The archive's files, by archive path, built from the site at *site*.

    Raises:
        FrozenDraftError: Listing every fault: a reference that names no
            file of the site, a page without a body or without the footer
            that names the publish and the release.
    """
    faults = draft.problems()
    index = site / SPEC_DIR / "index.html"
    if not index.is_file():
        raise FrozenDraftError(
            [*faults, f"{index}: the site has no specification"]
        )
    site_url = site_url_of(index)
    builder = _Builder(site, draft, site_url)
    files = builder.run()
    faults += builder.faults
    if faults:
        raise FrozenDraftError(faults)
    return files


def manifest_text(files: dict[str, bytes]) -> str:
    """The manifest of *files*, in ``sha256sum`` format (DOCBW-08-018)."""
    return "".join(
        f"{hashlib.sha256(files[name]).hexdigest()}  {name}\n"
        for name in sorted(files)
    )


def archive_bytes(files: dict[str, bytes], when: datetime) -> bytes:
    """A ``.tar.gz`` of *files*, regular files only, in name order."""
    buffer = io.BytesIO()
    stamp = int(when.timestamp())
    with (
        gzip.GzipFile(fileobj=buffer, mode="wb", mtime=stamp) as zipped,
        tarfile.open(
            fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT
        ) as tar,
    ):
        for name in sorted(files):
            info = tarfile.TarInfo(name)
            info.size = len(files[name])
            info.mtime = stamp
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(files[name]))
    return buffer.getvalue()


def build_archive(
    site: Path, out: Path, draft: FrozenDraft
) -> tuple[Path, Path]:
    """Write the archive and its manifest into *out*; return their paths."""
    files = frozen_files(site, draft)
    when = datetime.combine(draft.built, datetime.min.time(), tzinfo=UTC)
    out.mkdir(parents=True, exist_ok=True)
    archive = out / archive_name(draft.version)
    manifest = out / manifest_name(draft.version)
    archive.write_bytes(archive_bytes(files, when))
    manifest.write_text(manifest_text(files), encoding="utf-8")
    # The promote job checks it again; failing here fails before its turn.
    verify_archive(archive, manifest)
    return archive, manifest


# --- checking -------------------------------------------------------------------


def _member_faults(members: Iterable[tarfile.TarInfo]) -> list[str]:
    """Every member that could write outside the folder it is unpacked into."""
    faults = []
    seen: set[str] = set()
    for member in members:
        name = member.name
        parts = name.split("/")
        if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            faults.append(f"{name!r}: an absolute path")
        elif ".." in parts:
            faults.append(f"{name!r}: a '..' component")
        elif not (member.isreg() or member.isdir()):
            faults.append(f"{name!r}: neither a regular file nor a folder")
        elif member.isreg() and name in seen:
            faults.append(f"{name!r}: listed twice")
        seen.add(name)
    return faults


def unpack(archive: Path, into: Path) -> None:
    """Unpack *archive* into the empty folder *into*.

    Every member is checked before any file is written.

    Raises:
        FrozenDraftError: When *into* is not empty or a member has an
            absolute path, a ``..`` component, or a type other than a
            regular file or a folder.
    """
    into.mkdir(parents=True, exist_ok=True)
    if any(into.iterdir()):
        raise FrozenDraftError([f"{into}: not an empty folder"])
    try:
        with tarfile.open(archive, mode="r:gz") as tar:
            members = tar.getmembers()
            faults = _member_faults(members)
            if faults:
                raise FrozenDraftError(
                    [f"{archive.name}: {fault}" for fault in faults]
                )
            tar.extractall(into, members=members, filter="data")
    except (tarfile.TarError, OSError, EOFError) as error:
        raise FrozenDraftError([f"{archive.name}: {error}"]) from error


def read_manifest(text: str, shown: str) -> tuple[dict[str, str], list[str]]:
    """``(digests by path, faults)`` of a ``sha256sum`` manifest."""
    digests: dict[str, str] = {}
    faults = []
    for number, line in enumerate(text.splitlines(), start=1):
        found = _MANIFEST_LINE.match(line)
        if found is None:
            faults.append(f"{shown}:{number}: not a sha256sum line")
            continue
        digest, name = found.groups()
        if name in digests:
            faults.append(f"{shown}:{number}: {name} is listed twice")
        digests[name] = digest
    if not digests and not faults:
        faults.append(f"{shown}: lists no file")
    return digests, faults


def tree_files(root: Path) -> dict[str, Path]:
    """Every file below *root*, by POSIX path relative to it."""
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if not path.is_dir()
    }


def manifest_faults(root: Path, digests: dict[str, str]) -> list[str]:
    """Where the tree at *root* is not exactly what *digests* lists."""
    files = tree_files(root)
    faults = [
        f"{name}: listed, but not in the archive"
        for name in sorted(set(digests) - set(files))
    ]
    faults += [
        f"{name}: in the archive, but not listed"
        for name in sorted(set(files) - set(digests))
    ]
    for name in sorted(set(files) & set(digests)):
        actual = hashlib.sha256(files[name].read_bytes()).hexdigest()
        if actual != digests[name]:
            faults.append(f"{name}: its SHA-256 is not the listed one")
    return faults


def stylesheet_references(text: str) -> list[str]:
    """Every ``url(...)`` and ``@import`` reference of the stylesheet *text*."""
    return [
        match.group(2) if match.group(2) is not None else match.group(4)
        for match in _CSS_REFERENCE.finditer(text)
    ]


def reference_faults(root: Path) -> list[str]:
    """Every relative reference of a page or stylesheet that misses the tree.

    A reference must resolve to a file inside *root*: a folder resolves to
    its ``index.html`` (DOCBW-08-015).
    """
    faults = []
    for name, path in tree_files(root).items():
        if not name.endswith((".html", ".css")):
            continue
        text = _text(path.read_bytes())
        if text is None:
            faults.append(f"{name}: not UTF-8 text")
            continue
        found = (
            page_references(text)
            if name.endswith(".html")
            else stylesheet_references(text)
        )
        for reference in found:
            if not is_relative(reference):
                continue
            target = resolve(reference, name)
            if target is None:
                faults.append(f"{name}: {reference!r} leaves the archive")
            elif file_of(root, target) is None:
                faults.append(
                    f"{name}: {reference!r} names no file of the archive"
                )
    return faults


def verify_archive(
    archive: Path, manifest: Path, into: Path | None = None
) -> None:
    """Unpack *archive* into the empty folder *into* and check it (DOCBW-08-021).

    With no *into*, a temporary folder is used and removed.

    Raises:
        FrozenDraftError: Listing every fault: an unsafe member, a file the
            manifest does not list or lists with another digest, a listed
            file that is missing, and a relative reference of a page or a
            stylesheet that names no file of the tree.
    """
    if into is None:
        with tempfile.TemporaryDirectory() as tmp:
            verify_archive(archive, manifest, Path(tmp) / "tree")
        return
    unpack(archive, into)
    text = _text(manifest.read_bytes())
    if text is None:
        raise FrozenDraftError([f"{manifest.name}: not UTF-8 text"])
    digests, faults = read_manifest(text, manifest.name)
    faults += manifest_faults(into, digests)
    faults += reference_faults(into)
    if faults:
        raise FrozenDraftError(faults)


# --- commands ---------------------------------------------------------------------


def _built(value: str) -> date:
    return date.fromisoformat(value) if value else datetime.now(UTC).date()


def cmd_build(args: argparse.Namespace) -> int:
    draft = FrozenDraft(
        args.draft,
        args.release,
        args.commit,
        args.publish_tag,
        _built(args.built),
    )
    archive, manifest = build_archive(Path(args.site), Path(args.out), draft)
    print(f"Built {archive} and {manifest}.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    verify_archive(Path(args.archive), Path(args.manifest), Path(args.into))
    print(f"{args.archive} matches {args.manifest}; every reference resolves.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or check a frozen Protocol Specification draft."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--site", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--draft", required=True)
    build.add_argument("--release", required=True)
    build.add_argument("--commit", required=True)
    build.add_argument("--publish-tag", required=True)
    build.add_argument("--built", default="")
    build.set_defaults(func=cmd_build)
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--into", required=True)
    verify.set_defaults(func=cmd_verify)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FrozenDraftError as error:
        for fault in error.faults:
            print(f"::error::{fault}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
