"""Shared failure attribution for every loader under ``vultron.metadata``.

Every loader here walks a set of files, parses each one, and validates the
parsed data against a Pydantic model. Both steps can fail, and both must name
the file that failed — as ``path:line:col`` when the parser supplies a position
(MS-17-001). Neither may escape as a raw parser traceback (MS-17-002), and the
attribution comes from this module rather than a wrapper per loader
(MS-17-003).

Three traps this module absorbs so no caller has to:

1. A YAML error is not a ``ValueError``, so it escapes a caller guarding
   ``except (ValidationError, ValueError)``. Parse failures are re-raised as
   :class:`MetadataLoadError`, which is one (MS-17-004).
2. PyYAML names the source of its position mark after the stream it was handed
   — ``"<unicode string>"`` for text. The position is read off the exception's
   ``problem_mark`` and paired with the real path; PyYAML's own rendering of
   the mark never reaches the message.
3. A Pydantic error names the model and a positional path into the parsed
   structure, which locates nothing across a directory of files. Validation
   failures are attributed to the file just like parse failures.

Loaders that reject a corpus as a unit report **every** failing file, not the
first (SR-03-009): :class:`FailureCollector` gathers them and raises one
:class:`MetadataLoadErrors` carrying each failure as structured data.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

import frontmatter
import yaml
from frontmatter.default_handlers import YAMLHandler
from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)

#: Cause hints keyed on PyYAML's ``problem`` text. PyYAML reports *where* the
#: parse failed but never *why* an author got there; these name the edit that
#: most often produces each fault. A ``problem`` with no entry gets no hint — a
#: wrong hint is worse than none.
_UNQUOTED_COLON_HINT = (
    'a plain scalar containing ": " must be quoted, or written as a block '
    "scalar (`>-` or `|`)"
)
CAUSE_HINTS: dict[str, str] = {
    # libyaml (CSafeLoader, and python-frontmatter) and pure-Python PyYAML
    # word the same fault differently.
    "mapping values are not allowed in this context": _UNQUOTED_COLON_HINT,
    "mapping values are not allowed here": _UNQUOTED_COLON_HINT,
    "found character '\\t' that cannot start any token": (
        "YAML indentation must use spaces, not tabs"
    ),
}


class MetadataLoadError(ValueError):
    """One metadata file failed to parse or validate.

    A ``ValueError`` subclass on purpose (MS-17-004): the loaders document
    raising ``ValueError``, and a caller guarding
    ``except (ValidationError, ValueError)`` must catch this. It is tooling's,
    not the protocol's, so it does not derive from ``VultronError``.

    Attributes:
        path: The offending file as displayed (repository-relative when it is
            under the given root), or ``None`` for the no-path form used when
            validating a string that has no file behind it.
        line: 1-based line of the fault, when the parser supplied one.
        column: 1-based column of the fault, when the parser supplied one.
        detail: What went wrong, without the location.
    """

    def __init__(
        self,
        detail: str,
        *,
        path: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.path = path
        self.line = line
        self.column = column
        self.detail = detail
        super().__init__(self._render())

    @property
    def location(self) -> str | None:
        """``path:line:col``, ``path``, or ``None`` when there is no path."""
        if self.path is None:
            return None
        if self.line is None:
            return self.path
        if self.column is None:
            return f"{self.path}:{self.line}"
        return f"{self.path}:{self.line}:{self.column}"

    def _render(self) -> str:
        location = self.location
        return (
            self.detail if location is None else f"{location} — {self.detail}"
        )


class MetadataLoadErrors(ValueError):
    """Several metadata files failed; each is kept as structured data.

    SR-03-009 requires the individual failures to be recoverable without
    parsing the message, so a caller can count them, sort them, or render them
    in its own format.

    Attributes:
        failures: Every failure, in the order the files were visited.
    """

    def __init__(
        self,
        failures: Sequence[MetadataLoadError],
        *,
        summary: str | None = None,
        footer: str | None = None,
    ) -> None:
        self.failures = tuple(failures)
        heading = summary or f"{len(self.failures)} file(s) failed to load:"
        body = "\n".join(f"  {failure}" for failure in self.failures)
        message = f"{heading}\n{body}"
        if footer:
            message += f"\n\n{footer}"
        super().__init__(message)


class FailureCollector:
    """Gather :class:`MetadataLoadError` across files, then raise them once.

    Usage::

        collector = FailureCollector()
        for path in paths:
            with collector.attempt():
                data = load_yaml(path, root=root)
                results.append(validate(Model, data, path=path, root=root))
        collector.raise_if_any()

    A failed ``attempt()`` abandons the rest of that file's block and moves on
    to the next file.
    """

    def __init__(self) -> None:
        self.failures: list[MetadataLoadError] = []

    @contextmanager
    def attempt(self) -> Iterator[None]:
        """Record a :class:`MetadataLoadError` raised in the block."""
        try:
            yield
        except MetadataLoadError as exc:
            self.failures.append(exc)

    def raise_if_any(
        self, *, summary: str | None = None, footer: str | None = None
    ) -> None:
        """Raise :class:`MetadataLoadErrors` if any attempt failed."""
        if self.failures:
            raise MetadataLoadErrors(
                self.failures, summary=summary, footer=footer
            )


def display_path(path: Path, root: Path | None = None) -> str:
    """Return *path* relative to *root* when it lies under it (MS-17-001).

    A path outside *root* — a temporary directory in a test, say — is shown as
    given rather than failing, because a location the author can open beats a
    crash in the error path.
    """
    if root is not None:
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            pass
    return str(path)


def _yaml_error(
    exc: yaml.YAMLError, shown: str | None, lead: str
) -> MetadataLoadError:
    """Attribute a PyYAML error to *shown*, reading its position mark."""
    if not isinstance(exc, yaml.MarkedYAMLError):
        return MetadataLoadError(f"{lead}: {exc}", path=shown)
    mark = exc.problem_mark or exc.context_mark
    problem = exc.problem or "invalid YAML"
    detail = (
        f"{lead}: {exc.context}, {problem}"
        if exc.context
        else (f"{lead}: {problem}")
    )
    hint = CAUSE_HINTS.get(exc.problem or "")
    if hint:
        detail += f" (hint: {hint})"
    return MetadataLoadError(
        detail,
        path=shown,
        line=None if mark is None else mark.line + 1,
        column=None if mark is None else mark.column + 1,
    )


def load_yaml(
    path: Path,
    *,
    root: Path | None = None,
    loader: type[Any] = yaml.SafeLoader,
) -> object:
    """Parse the YAML file at *path*, attributing any fault to it.

    The file is handed to PyYAML as a stream rather than as text, so even the
    parser's own mark would carry the filename; the message still takes its
    position from the mark and its name from *path*.

    Raises:
        MetadataLoadError: On a YAML syntax fault or an undecodable file.
        FileNotFoundError: If *path* does not exist.
    """
    shown = display_path(path, root)
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.load(fh, Loader=loader)  # noqa: S506 — caller's loader
    except yaml.YAMLError as exc:
        raise _yaml_error(exc, shown, "YAML parse error") from exc
    except UnicodeDecodeError as exc:
        raise MetadataLoadError(f"not valid UTF-8: {exc}", path=shown) from exc


#: Lead-in for a frontmatter parse fault. Kept identical across loaders so the
#: fault reads the same whichever directory the author edited.
_FRONTMATTER_LEAD = "malformed YAML frontmatter"


class _NotAMapping(Exception):
    """A frontmatter block parsed to something other than a mapping."""


class _MappingYAMLHandler(YAMLHandler):
    """YAML handler that refuses a block parsing to a list or a scalar.

    ``python-frontmatter`` keeps the parsed block only when it is a ``dict``
    and otherwise returns empty metadata, so a malformed block would read as
    no block at all. An empty block (``None``) is still no metadata.
    """

    def load(self, fm: str, **kwargs: object) -> Any:
        data = super().load(fm, **kwargs)
        if data is not None and not isinstance(data, dict):
            raise _NotAMapping(type(data).__name__)
        return data


_MAPPING_YAML = _MappingYAMLHandler()


def _parse_frontmatter(text: str, shown: str | None) -> frontmatter.Post:
    # The handler is passed only when the text opens with a ``---`` fence;
    # passed unconditionally, it would split on a later horizontal rule.
    handler = _MAPPING_YAML if _MAPPING_YAML.detect(text) else None
    try:
        return frontmatter.loads(text, handler=handler)
    except yaml.YAMLError as exc:
        raise _yaml_error(exc, shown, _FRONTMATTER_LEAD) from exc
    except _NotAMapping as exc:
        raise MetadataLoadError(
            f"{_FRONTMATTER_LEAD}: the block is a YAML {exc}, not a mapping "
            f"of keys",
            path=shown,
            line=1,
        ) from exc


def load_frontmatter(
    path: Path, *, root: Path | None = None
) -> frontmatter.Post:
    """Parse the markdown file at *path* and its YAML frontmatter block.

    The line and column are file-relative: ``python-frontmatter`` parses the
    block in place, so a mark on the block's third line is the file's third
    line.

    Raises:
        MetadataLoadError: On malformed YAML frontmatter, a block that is not
            a mapping, or an undecodable file.
        FileNotFoundError: If *path* does not exist.
    """
    shown = display_path(path, root)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise MetadataLoadError(f"not valid UTF-8: {exc}", path=shown) from exc
    return _parse_frontmatter(text, shown)


def loads_frontmatter(text: str) -> frontmatter.Post:
    """Parse frontmatter from *text* that has no file behind it.

    The no-path form, for a caller validating content before it is written
    (``append-history`` stdin). The error carries the position but no path.

    Raises:
        MetadataLoadError: On malformed YAML frontmatter or a block that is
            not a mapping.
    """
    return _parse_frontmatter(text, None)


def describe_validation_error(exc: ValidationError) -> str:
    """Render a Pydantic error as ``field: message; field: message``.

    Drops the model's class name and Pydantic's documentation URL, neither of
    which helps an author fix a metadata file.
    """
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", ())) or "<root>"
        parts.append(f"{field}: {err.get('msg', 'invalid')}")
    return "; ".join(parts)


def validate(
    model: type[M],
    data: object,
    *,
    path: Path | None = None,
    root: Path | None = None,
    prefix: str | None = None,
    key_lines: Mapping[str, int] | None = None,
) -> M:
    """Validate *data* against *model*, attributing a failure to *path*.

    Args:
        model: The Pydantic model to validate against.
        data: The parsed file content.
        path: The file *data* came from; ``None`` for the no-path form.
        root: Root the displayed path is made relative to.
        prefix: Optional lead-in for the detail, e.g. ``"invalid history
            frontmatter"``, so a loader keeps its own vocabulary.
        key_lines: Optional 1-based line of each top-level key in the file.
            When given, the failure is located at the line of the first key
            that failed, so a schema fault reads ``path:line`` like a parse
            fault does.

    Raises:
        MetadataLoadError: If validation fails. The detail lists every field
            that failed, not only the first.
    """
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        detail = describe_validation_error(exc)
        if prefix:
            detail = f"{prefix}: {detail}"
        shown = None if path is None else display_path(path, root)
        line = None
        if key_lines:
            for err in exc.errors():
                loc = err.get("loc", ())
                if loc and str(loc[0]) in key_lines:
                    line = key_lines[str(loc[0])]
                    break
        raise MetadataLoadError(detail, path=shown, line=line) from exc
