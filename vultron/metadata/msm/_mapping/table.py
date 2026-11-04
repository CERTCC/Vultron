"""The occasion table model and its loader (``msm/occasions.yaml``)."""

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

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.models.events.base import MessageSemantics
from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import (
    display_path,
    loads_yaml,
    read_utf8,
    validate,
    yaml_node_positions,
)
from vultron.metadata.msm._mapping.status import MappingStatus
from vultron.primitives import NonEmptyString
from vultron.semantic_registry._occasion import (
    ANCHOR_PATTERN,
    MessagePage,
    ProtocolShorthand,
)

# ---------------------------------------------------------------------------
# The occasion table: the committed YAML projection (ADR-0128).
# ---------------------------------------------------------------------------

#: The committed, generated occasion table.  Internal: publishing it as an
#: interface belongs to protocol versioning (#2959).
OCCASION_TABLE_PATH: Path = Path(__file__).parent.with_name("occasions.yaml")


#: The occasion table's format version, written into the file from the start
#: so that a later reader can tell the shapes apart.  Version 2 replaced each
#: row's declared ``howto`` link with the derived ``seen_in`` pages (#4432);
#: version 3 added each row's derived ``send_to`` (#4438).
OCCASION_TABLE_FORMAT_VERSION: Final = 3


_ANCHOR = Annotated[str, Field(pattern=ANCHOR_PATTERN)]


_RECORD = ConfigDict(frozen=True, extra="forbid")


class PageLink(BaseModel):
    """A ``docs/`` page that embeds an occasion, with its page title.

    Attributes:
        path: The page, relative to ``docs/``.
        title: The page's H1, the text a link to it carries.
    """

    model_config = _RECORD

    path: NonEmptyString
    title: NonEmptyString


class OccasionRow(BaseModel):
    """One occasion as the table and its section render it; all derived.

    Attributes:
        anchor: The section anchor on the group's message page.
        heading: The section heading, which the details link text reuses
            (MSM-08-008).
        when: The sender's situation, completing "When…".
        send: The wire summary, rendered from the entry's ``ActivityPattern``.
        send_to: The "Send to" value, from the occasion's addressee
            (MSM-08-009).
        sent_by: The "Sent by" value (MSM-08-005).
        distinguished_by: What tells the occasion apart, as markdown.
        semantics: The ``SEMANTIC_REGISTRY`` entry the occasion belongs to.
        shorthand: The formal protocol message it carries, if any.
        status: The entry's mapping status (MSM-06-003).
        description: What the activity does.
        notes: Further prose for the section.
        seen_in: The published pages outside the message pages that embed
            the occasion, derived from their include directives, in path
            order.
        example: The ``vocab_examples`` function that builds its example.
    """

    model_config = _RECORD

    anchor: _ANCHOR
    heading: NonEmptyString
    when: NonEmptyString
    send: NonEmptyString
    send_to: NonEmptyString
    sent_by: NonEmptyString
    distinguished_by: NonEmptyString | None = None
    semantics: MessageSemantics
    shorthand: ProtocolShorthand | None = None
    status: MappingStatus
    description: NonEmptyString
    notes: NonEmptyString | None = None
    seen_in: tuple[PageLink, ...] = ()
    example: NonEmptyString


class OccasionGroup(BaseModel):
    """The occasions of one message page, in registry (dispatch) order.

    Attributes:
        page: The message page the occasions' sections live on.
        title: The group's title in the whole table.
        mechanics: ``True`` for protocol mechanics, which follow the case
            lifecycle groups.
        occasions: The group's rows.
    """

    model_config = _RECORD

    page: MessagePage
    title: NonEmptyString
    mechanics: bool
    occasions: tuple[OccasionRow, ...] = Field(min_length=1)


class OccasionTable(BaseModel):
    """The whole occasion table, as committed in :data:`OCCASION_TABLE_PATH`.

    Validation fails when a page has two groups, an anchor is not unique
    (MSM-08-004), or the lifecycle groups do not all precede the mechanics.
    """

    model_config = _RECORD

    format_version: Literal[3]
    groups: tuple[OccasionGroup, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _pages_and_anchors_are_unique(self) -> OccasionTable:
        problems: list[str] = []
        pages = Counter(group.page for group in self.groups)
        problems.extend(
            f"page {page.value!r} has {count} groups"
            for page, count in pages.items()
            if count > 1
        )
        anchors = Counter(
            row.anchor for group in self.groups for row in group.occasions
        )
        problems.extend(
            f"anchor {anchor!r} is used {count} times (MSM-08-004)"
            for anchor, count in anchors.items()
            if count > 1
        )
        kinds = [group.mechanics for group in self.groups]
        if kinds != sorted(kinds):
            problems.append(
                "a lifecycle group follows a protocol-mechanics group"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


def load_occasion_table(
    path: Path = OCCASION_TABLE_PATH, *, root: Path | None = None
) -> OccasionTable:
    """Load and validate the occasion table YAML at *path* (MS-17).

    Args:
        path: The YAML file; defaults to the committed table.
        root: Root the displayed path is made relative to; defaults to the
            repository root.

    Raises:
        MetadataLoadError: When the file does not parse or does not
            validate, naming ``path:line:col`` of the fault (a check across
            the whole table, such as a duplicate anchor, names the path).
        FileNotFoundError: When *path* does not exist.
    """
    shown_root = repo_root(Path(__file__).parent) if root is None else root
    shown = display_path(path, shown_root)
    text = read_utf8(path, shown)
    return validate(
        OccasionTable,
        loads_yaml(text, Path(shown)),
        path=path,
        root=shown_root,
        prefix="invalid occasion table",
        positions=yaml_node_positions(text),
    )
