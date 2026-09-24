"""Render ``docs/includes/stakeholder_types.md`` from the schema (DF-11-011).

The members come from :class:`~vultron.metadata.docs.page_schema.StakeholderType`
and their wording from
:data:`~vultron.metadata.docs.page_schema.AUDIENCE_DESCRIPTIONS`, so the
fragment every ``docs/`` page includes cannot drift from what the validator
accepts. ADR-0102 alone keeps a literal copy, on purpose: a decision record
must not silently acquire members it never decided (DF-10-002).
"""

from __future__ import annotations

from vultron.metadata.docs.page_schema import (
    ALL_STAKEHOLDERS,
    AUDIENCE_DESCRIPTIONS,
    StakeholderType,
)

#: Repository-relative path of the generated fragment.
FRAGMENT_PATH = "docs/includes/stakeholder_types.md"


def render_fragment() -> str:
    """Render the full contents of :data:`FRAGMENT_PATH`.

    Raises:
        ValueError: If a member, or ``ALL``, has no entry in
            ``AUDIENCE_DESCRIPTIONS`` — shipping a blank row would publish a
            type nobody has defined.
    """
    keys = [member.value for member in StakeholderType] + [ALL_STAKEHOLDERS]
    missing = [key for key in keys if key not in AUDIENCE_DESCRIPTIONS]
    if missing:
        raise ValueError(
            "AUDIENCE_DESCRIPTIONS in vultron/metadata/docs/page_schema.py has "
            f"no entry for {', '.join(missing)}; describe every stakeholder "
            "type before regenerating the fragment (DF-11-011)"
        )
    rows = [
        f"| `{key}` | {AUDIENCE_DESCRIPTIONS[key].who} | "
        f"{AUDIENCE_DESCRIPTIONS[key].wants} |"
        for key in keys
    ]
    return (
        "<!-- GENERATED from vultron/metadata/docs/page_schema.py by "
        "`uv run docs-site --write` — do not edit (DF-11-011) -->\n\n"
        "| Stakeholder type | Who it is | What they want |\n"
        "|---|---|---|\n" + "\n".join(rows) + "\n"
    )
