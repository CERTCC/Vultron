"""Render the trigger API reference from the FastAPI OpenAPI schema.

Called by docs/reference/trigger-api.md via a ``python exec="true"`` block.
All content is derived at build time from ``create_app().openapi()``,
so the rendered page tracks the routers automatically.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when this script runs under mkdocs
_repo = Path(__file__).resolve().parent.parent.parent
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

# ── Domain groups ─────────────────────────────────────────────────────────────
# Each entry defines the section title, the ordered list of behaviors in that
# section, and the how-to guide that covers the same workflows.

DOMAIN_GROUPS: list[dict] = [
    {
        "title": "Report Management",
        "behaviors": [
            "submit-report",
            "validate-report",
            "invalidate-report",
            "reject-report",
            "close-report",
        ],
        "howto_link": "../../howto/activitypub/activities/report_vulnerability.md",
        "howto_label": "How to Report a Vulnerability",
    },
    {
        "title": "Case Management",
        "behaviors": [
            "create-case",
            "engage-case",
            "defer-case",
            "add-report-to-case",
            "add-object-to-case",
        ],
        "howto_link": "../../howto/activitypub/activities/manage_case.md",
        "howto_label": "How to Manage a Case",
    },
    {
        "title": "Embargo Management",
        "behaviors": [
            "propose-embargo",
            "accept-embargo",
            "reject-embargo",
            "propose-embargo-revision",
            "terminate-embargo",
        ],
        "howto_link": "../../howto/activitypub/activities/establish_embargo.md",
        "howto_label": "How to Establish an Embargo",
    },
    {
        "title": "Actor Participation",
        "behaviors": [
            "suggest-actor-to-case",
            "invite-actor-to-case",
            "accept-actor-recommendation",
            "accept-case-invite",
            "reject-case-invite",
            "offer-case-participant-role",
            "offer-case-ownership-transfer",
            "accept-case-ownership-transfer",
        ],
        "howto_link": "../../howto/activitypub/activities/manage_participants.md",
        "howto_label": "How to Manage Case Participants",
    },
]


# ── Type rendering helpers ─────────────────────────────────────────────────────


def _type_str(fdef: dict) -> str:
    """Return a human-readable type string for a JSON Schema field definition."""
    if "$ref" in fdef:
        return fdef["$ref"].split("/")[-1]
    if "anyOf" in fdef:
        # Unwrap nullable union: keep the non-null branch(es)
        non_null = [v for v in fdef["anyOf"] if v.get("type") != "null"]
        if len(non_null) == 1:
            return _type_str(non_null[0])
        return " | ".join(_type_str(v) for v in non_null)
    if fdef.get("type") == "array":
        items = fdef.get("items", {})
        return f"list[{_type_str(items)}]"
    return fdef.get("type", fdef.get("format", "any"))


def _field_rows(
    schema_obj: dict, all_schemas: dict
) -> list[tuple[str, str, bool]]:
    """Return (name, type, required) tuples for the fields of *schema_obj*."""
    # Resolve a top-level $ref
    if "$ref" in schema_obj:
        ref_name = schema_obj["$ref"].split("/")[-1]
        schema_obj = all_schemas.get(ref_name, schema_obj)

    properties = schema_obj.get("properties", {})
    required_set = set(schema_obj.get("required", []))
    return [
        (name, _type_str(fdef), name in required_set)
        for name, fdef in properties.items()
    ]


# ── Per-endpoint rendering ─────────────────────────────────────────────────────


def _render_endpoint(path: str, op: dict, all_schemas: dict) -> list[str]:
    """Render one trigger endpoint as a Markdown subsection."""
    behavior = path.split("/trigger/")[-1]
    lines: list[str] = []

    lines.append(f"### `{behavior}`")
    lines.append("")
    lines.append(f"**POST** `{path}`")
    lines.append("")

    description = op.get("description", "").strip()
    if description:
        lines.append(description)
        lines.append("")

    # Request body table
    req_body = op.get("requestBody", {})
    if req_body:
        content = req_body.get("content", {}).get("application/json", {})
        req_schema_ref = content.get("schema", {})
        schema_name: str | None = None
        if "$ref" in req_schema_ref:
            schema_name = req_schema_ref["$ref"].split("/")[-1]
        resolved = (
            all_schemas.get(schema_name, {}) if schema_name else req_schema_ref
        )

        field_rows = _field_rows(resolved, all_schemas)
        if field_rows:
            label = "**Request body**"
            if schema_name:
                label += f" (`{schema_name}`)"
            lines.append(f"{label}:")
            lines.append("")
            lines.append("| Field | Type | Required |")
            lines.append("|---|---|---|")
            for fname, ftype, freq in field_rows:
                lines.append(
                    f"| `{fname}` | `{ftype}` | {'Yes' if freq else 'No'} |"
                )
            lines.append("")

    return lines


# ── Top-level renderer ─────────────────────────────────────────────────────────


def render() -> str:
    """Return the full Markdown for the trigger API reference page."""
    from vultron.adapters.driving.fastapi.app import (
        create_app,
    )  # noqa: PLC0415

    app = create_app()
    schema = app.openapi()
    all_schemas: dict = schema.get("components", {}).get("schemas", {})

    # Index trigger paths by behavior name
    trigger_paths: dict[str, tuple[str, dict]] = {}
    for path, methods in schema.get("paths", {}).items():
        if "/trigger/" not in path:
            continue
        behavior = path.split("/trigger/")[-1]
        trigger_paths[behavior] = (path, methods.get("post", {}))

    lines: list[str] = []
    for group in DOMAIN_GROUPS:
        lines.append(f"## {group['title']}")
        lines.append("")
        lines.append(
            f"For the workflow view, see"
            f" [{group['howto_label']}]({group['howto_link']})."
        )
        lines.append("")
        for behavior in group["behaviors"]:
            entry = trigger_paths.get(behavior)
            if not entry:
                continue
            path, op = entry
            lines.extend(_render_endpoint(path, op, all_schemas))

    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
