"""Generate the message-occasion table and its documentation fragments.

The ``msm-occasions`` CLI (:func:`main`) regenerates or checks
``msm/occasions.yaml`` and every fragment under
``docs/reference/messages/_occasions/`` (MSM-06-006).

Submodules, by concern: ``table`` (deriving the occasion table from the
registry and the pages that embed each occasion), ``render`` (the fragment
renderers) and ``cli`` (the desired artifact set, drift detection, writing
and the CLI; its docstring is the CLI's help text).
"""

from vultron.metadata.msm.occasions.cli import (
    Drift,
    desired_contents,
    drift,
    main,
    write_artifacts,
)
from vultron.metadata.msm.occasions.render import (
    NO_WIRE_ANCHOR,
    SHORTHAND_FAMILIES,
    STATUS_ANCHOR,
    STATUS_PAGE,
    details_link,
    formal_link,
    render_embed,
    render_section,
    render_shorthands,
    render_slice,
    render_whole,
    seen_in_link,
    status_link,
)
from vultron.metadata.msm.occasions.table import (
    DETAILS_TAB,
    EMBED_DIR,
    EXAMPLE_TAB,
    FRAGMENT_DIR,
    FRAGMENT_MARKER,
    TABLE_GROUPS,
    WRITE_COMMAND,
    YAML_PATH,
    TableGroup,
    derive_table,
    dump_table,
    embedding_pages,
    emitted_type,
    format_pattern,
    page_title,
    wire_summary,
)

__all__ = [
    "DETAILS_TAB",
    "Drift",
    "EMBED_DIR",
    "EXAMPLE_TAB",
    "FRAGMENT_DIR",
    "FRAGMENT_MARKER",
    "NO_WIRE_ANCHOR",
    "SHORTHAND_FAMILIES",
    "STATUS_ANCHOR",
    "STATUS_PAGE",
    "TABLE_GROUPS",
    "TableGroup",
    "WRITE_COMMAND",
    "YAML_PATH",
    "derive_table",
    "desired_contents",
    "details_link",
    "drift",
    "dump_table",
    "embedding_pages",
    "emitted_type",
    "formal_link",
    "format_pattern",
    "main",
    "page_title",
    "render_embed",
    "render_section",
    "render_shorthands",
    "render_slice",
    "render_whole",
    "seen_in_link",
    "status_link",
    "wire_summary",
    "write_artifacts",
]
