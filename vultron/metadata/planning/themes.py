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
"""The theme catalog: the ``theme:`` label set, read from one note.

Requirements: PAD-02-014 to PAD-02-021.

``notes/epic-themes.md`` holds the catalog as one fenced ``yaml`` block between
:data:`BEGIN_MARKER` and :data:`END_MARKER`. Every tool that needs the theme set
(the ``theme-labels`` sync, the structural theme check) loads it through
:func:`load_theme_catalog` so the block has one parser and one schema.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from vultron.metadata.base import NonEmptyStr, repo_root
from vultron.metadata.file_loading import (
    MetadataLoadError,
    display_path,
    loads_yaml,
    read_utf8,
    validate,
    yaml_node_positions,
)

CATALOG_PATH = Path("notes/epic-themes.md")
"""Repository-relative path of the note holding the catalog."""

BEGIN_MARKER = "<!-- theme-catalog:begin -->"
"""Comment line that opens the catalog block. Matched literally."""

END_MARKER = "<!-- theme-catalog:end -->"
"""Comment line that closes the catalog block. Matched literally."""

THEME_PREFIX = "theme:"
"""Prefix every theme label carries; other labels are not themes."""

GITHUB_DESCRIPTION_LIMIT = 100
"""GitHub refuses a label description longer than this."""

_FENCE_OPEN = re.compile(r"^```ya?ml\s*$")
_FENCE_CLOSE = re.compile(r"^```\s*$")

ThemeLabel = Annotated[
    str, StringConstraints(pattern=r"^theme:[a-z0-9]+(?:-[a-z0-9]+)*$")
]
"""A ``theme:`` label: the prefix, then lowercase words joined by hyphens."""

HexColor = Annotated[
    str, StringConstraints(pattern=r"^[0-9A-Fa-f]{6}$", to_upper=True)
]
"""A six-digit hex color without ``#``, held in upper case."""


class ThemeStatus(StrEnum):
    """Whether a theme takes new Issues."""

    ACTIVE = "active"
    RETIRING = "retiring"


class Theme(BaseModel):
    """One catalog entry: a theme label and what it covers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: ThemeLabel
    outcome: NonEmptyStr
    in_bounds: list[NonEmptyStr] = Field(min_length=1)
    out_of_bounds: list[NonEmptyStr] = Field(min_length=1)
    color: HexColor
    status: ThemeStatus = ThemeStatus.ACTIVE
    replaced_by: list[ThemeLabel] = Field(default_factory=list)

    @field_validator("outcome")
    @classmethod
    def outcome_is_one_line(cls, v: str) -> str:
        """Reject a multi-line outcome: it becomes a one-line description."""
        if "\n" in v:
            raise ValueError(
                "outcome must be one line; fold it with `>-`, not `|`"
            )
        return v

    @model_validator(mode="after")
    def retiring_names_replacements(self) -> Theme:
        """A retiring theme names its replacements; an active one does not."""
        retiring = self.status is ThemeStatus.RETIRING
        if retiring and not self.replaced_by:
            raise ValueError(
                f"{self.label}: a retiring theme must list `replaced_by`"
            )
        if not retiring and self.replaced_by:
            raise ValueError(
                f"{self.label}: only a retiring theme may list `replaced_by`"
            )
        if len(self.description) > GITHUB_DESCRIPTION_LIMIT:
            raise ValueError(
                f"{self.label}: the label description is "
                f"{len(self.description)} characters; GitHub allows "
                f"{GITHUB_DESCRIPTION_LIMIT}. Shorten the outcome."
            )
        return self

    @property
    def description(self) -> str:
        """The GitHub label description this entry syncs to."""
        if self.status is ThemeStatus.RETIRING:
            return "Retiring: use " + " or ".join(self.replaced_by)
        return self.outcome


class ThemeCatalog(BaseModel):
    """The whole theme set, as the catalog block declares it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    themes: list[Theme] = Field(min_length=1)

    @model_validator(mode="after")
    def labels_are_unique_and_replacements_exist(self) -> ThemeCatalog:
        """Reject a doubled label and a replacement that is not active."""
        faults: list[str] = []
        seen: set[str] = set()
        for theme in self.themes:
            if theme.label in seen:
                faults.append(f"{theme.label} is listed twice")
            seen.add(theme.label)
        active = {t.label for t in self.active()}
        for theme in self.themes:
            for target in theme.replaced_by:
                if target not in active:
                    faults.append(
                        f"{theme.label} is replaced by {target}, which is "
                        f"not an active theme in the catalog"
                    )
        if faults:
            raise ValueError("; ".join(faults))
        return self

    def active(self) -> tuple[Theme, ...]:
        """The themes that take new Issues."""
        return tuple(t for t in self.themes if t.status is ThemeStatus.ACTIVE)

    def labels(self) -> frozenset[str]:
        """Every label the catalog lists, retiring ones included."""
        return frozenset(t.label for t in self.themes)

    def get(self, label: str) -> Theme:
        """The entry for *label*.

        Raises:
            KeyError: If the catalog does not list *label*.
        """
        for theme in self.themes:
            if theme.label == label:
                return theme
        raise KeyError(label)


def extract_catalog_block(text: str, shown: str) -> tuple[str, int]:
    """Return the YAML inside the catalog fence and the lines before it.

    Args:
        text: The note's full text.
        shown: The path to name in a fault.

    Returns:
        The YAML text, and the number of file lines before its first line.

    Raises:
        MetadataLoadError: If a marker is missing or doubled, the markers are
            inverted, or anything other than one ``yaml`` fence sits between
            them.
    """
    lines = text.splitlines()
    for marker in (BEGIN_MARKER, END_MARKER):
        hits = [n for n, line in enumerate(lines) if line.strip() == marker]
        if len(hits) != 1:
            raise MetadataLoadError(
                f"expected exactly one `{marker}` line, found {len(hits)}",
                path=shown,
                line=hits[1] + 1 if len(hits) > 1 else None,
            )
    begin = next(
        n for n, line in enumerate(lines) if line.strip() == BEGIN_MARKER
    )
    end = next(n for n, line in enumerate(lines) if line.strip() == END_MARKER)
    if end < begin:
        raise MetadataLoadError(
            "the theme-catalog end marker precedes its begin marker",
            path=shown,
            line=end + 1,
        )
    inner = [
        (n, line) for n, line in enumerate(lines[begin + 1 : end], begin + 1)
    ]
    body = [(n, line) for n, line in inner if line.strip()]
    if (
        len(body) < 2
        or not _FENCE_OPEN.match(body[0][1])
        or not _FENCE_CLOSE.match(body[-1][1])
        or any(
            _FENCE_OPEN.match(line) or _FENCE_CLOSE.match(line)
            for _, line in body[1:-1]
        )
    ):
        raise MetadataLoadError(
            "the theme-catalog markers must enclose exactly one ```yaml "
            "fence and nothing else",
            path=shown,
            line=begin + 1,
        )
    first = body[0][0] + 1
    last = body[-1][0]
    return "\n".join(lines[first:last]) + "\n", first


def parse_theme_catalog(
    text: str, shown: str = str(CATALOG_PATH)
) -> ThemeCatalog:
    """Parse and validate the catalog block in a note's *text*.

    Raises:
        MetadataLoadError: If the block cannot be found, is not valid YAML,
            or does not match :class:`ThemeCatalog`. The fault names the
            note's line, not the block's.
    """
    block, offset = extract_catalog_block(text, shown)
    data = loads_yaml(block, Path(shown), line_offset=offset)
    positions = {
        loc: (line + offset, column)
        for loc, (line, column) in yaml_node_positions(block).items()
    }
    return validate(
        ThemeCatalog,
        data,
        path=Path(shown),
        prefix="invalid theme catalog",
        positions=positions,
    )


def load_theme_catalog(path: Path | None = None) -> ThemeCatalog:
    """Load the theme catalog from ``notes/epic-themes.md``.

    Args:
        path: The note to read; defaults to the repository's catalog note.

    Raises:
        MetadataLoadError: As :func:`parse_theme_catalog`, or if the note is
            not valid UTF-8.
        FileNotFoundError: If the note does not exist.
    """
    root = repo_root()
    note = path if path is not None else root / CATALOG_PATH
    shown = display_path(note, root)
    return parse_theme_catalog(read_utf8(note, shown), shown)
