#!/usr/bin/env python3
"""Migrate a specs/*.md requirement file to specs/*.yaml format.

Usage::

    python tools/migrate_spec_md_to_yaml.py specs/handler-protocol.md
    python tools/migrate_spec_md_to_yaml.py specs/  # all .md files

The script parses the markdown spec format and outputs a YAML file
conforming to the Pydantic schema in ``vultron/metadata/specs/schema.py``.

Human review of each generated file is expected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# Prefixes with dashes that must be flattened for SpecIdStr compliance.
PREFIX_RENAMES: dict[str, str] = {
    "CI-SEC": "CISEC",
    "DEMO-MA": "DEMOMA",
    "UC-ORG": "UCORG",
    "IMPL-TS": "IMPLTS",
}

SKIP_FILES = {"README.md", "meta-specifications.md", "datalayer.md"}

# Relationship verbs recognized in sub-bullets
REL_VERBS = {
    "depends-on": "depends_on",
    "depends_on": "depends_on",
    "refines": "refines",
    "implements": "implements",
    "supersedes": "supersedes",
    "extends": "extends",
    "derives-from": "derives_from",
    "derives_from": "derives_from",
    "is-derived-by": "derives_from",
    "constrains": "constrains",
    "conflicts": "conflicts",
    "verifies": "verifies",
    "part-of": "part_of",
    "part_of": "part_of",
}

# Spec ID: uppercase letters (with optional dash-letter groups), then -NN-NNN
_PREFIX_PAT = r"[A-Z]+(?:-[A-Z]+)*"
_FULL_ID_PAT = rf"{_PREFIX_PAT}-\d{{2}}-\d{{3}}"
_GROUP_OR_FULL_PAT = rf"{_PREFIX_PAT}-\d{{2}}(?:-\d{{3}})?"

# A spec bullet: - `ID` ...
SPEC_BULLET_RE = re.compile(rf"^-\s+`({_FULL_ID_PAT})`\s*(.*)")

# Relationship: ID verb ID (possibly with parenthetical note)
REL_RE = re.compile(
    rf"({_FULL_ID_PAT})"
    r"\s+"
    r"(depends-on|depends_on|refines|implements|supersedes|extends|"
    r"derives-from|derives_from|is-derived-by|constrains|conflicts|"
    r"verifies|part-of|part_of)"
    r"\s+"
    rf"({_GROUP_OR_FULL_PAT})"
    r"(?:\s*\(([^)]+)\))?"
)

_REL_VERB_SET = set(REL_VERBS.keys())


def rename_id(spec_id: str) -> str:
    """Apply prefix renames to a spec ID."""
    for old, new in PREFIX_RENAMES.items():
        if spec_id.startswith(old + "-"):
            return new + spec_id[len(old) :]
    return spec_id


def extract_prefix(spec_id: str) -> str:
    """Extract the letter prefix from a spec ID (after rename)."""
    m = re.match(r"^([A-Z]+)", spec_id)
    return m.group(1) if m else spec_id


def detect_priority(statement: str, explicit: str | None = None) -> str:
    """Detect the RFC 2119 priority from the statement or explicit tag."""
    if explicit:
        normed = explicit.strip().replace(" ", "_")
        if normed in {"MUST", "MUST_NOT", "SHOULD", "SHOULD_NOT", "MAY"}:
            return normed
    if "MUST NOT" in statement:
        return "MUST_NOT"
    if "SHOULD NOT" in statement:
        return "SHOULD_NOT"
    if "MUST" in statement:
        return "MUST"
    if "SHOULD" in statement:
        return "SHOULD"
    if "MAY" in statement:
        return "MAY"
    return "MUST"


def _is_continuation(line: str) -> bool:
    """Is this line a continuation of the previous bullet (indented text)?"""
    if not line or not line[0] == " ":
        return False
    stripped = line.lstrip()
    if not stripped:
        return False
    # Sub-bullet (starts with -)
    if stripped.startswith("- "):
        return True
    # Continuation text (indented non-bullet)
    return True


def _is_sub_bullet(line: str) -> bool:
    """Is this an indented sub-bullet under a spec?"""
    return bool(line) and line[0] == " " and line.lstrip().startswith("- ")


def _is_relationship_line(text: str) -> bool:
    """Does this text contain a relationship reference?"""
    return bool(REL_RE.search(text))


def _extract_relationships(text: str) -> list[dict]:
    """Extract all relationships from a line."""
    rels = []
    for m in REL_RE.finditer(text):
        verb = m.group(2)
        target = m.group(3)
        note = m.group(4)
        rel: dict = {
            "rel_type": REL_VERBS.get(verb, verb),
            "spec_id": rename_id(target),
        }
        if note:
            rel["note"] = note.strip()
        rels.append(rel)
    return rels


def parse_spec_md(path: Path) -> dict:
    """Parse a single specs/*.md file into a YAML-ready dict."""
    text = path.read_text()
    lines = text.split("\n")

    title = ""
    description_lines: list[str] = []
    groups: list[dict] = []
    current_group: dict | None = None
    current_spec: dict | None = None

    section = "pre"  # pre, overview, group, verification, related
    in_code_block = False

    def finalize_current_spec():
        nonlocal current_spec
        if current_spec and current_group is not None:
            _finalize_spec(current_spec, current_group)
            current_spec = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            i += 1
            continue
        if in_code_block:
            i += 1
            continue

        # Title
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            if title.endswith(" Specification"):
                title = title[: -len(" Specification")]
            i += 1
            continue

        # ## headings
        if line.startswith("## "):
            finalize_current_spec()
            heading = line[3:].strip()

            if heading == "Overview":
                section = "overview"
            elif heading.startswith("Verification") or heading == "Related":
                section = "skip"
            else:
                section = "group"
                current_group = {
                    "title": heading,
                    "specs": [],
                }
                groups.append(current_group)
            i += 1
            continue

        # ### headings
        if line.startswith("### "):
            finalize_current_spec()
            # Sub-verification sections stay in skip mode
            i += 1
            continue

        # Skip non-group sections
        if section in ("skip", "pre"):
            i += 1
            continue

        if section == "overview":
            stripped = line.strip()
            if stripped and stripped != "---":
                if not any(
                    stripped.startswith(p)
                    for p in (
                        "**Source**",
                        "**Note**",
                        "**Cross-references**",
                        "**Cross-reference**",
                    )
                ):
                    description_lines.append(stripped)
            i += 1
            continue

        # In group section
        stripped = line.strip()

        # Try to match a spec bullet (only at top-level, not indented)
        is_top_level = not line[0:1].isspace() if line else True
        m = SPEC_BULLET_RE.match(stripped) if is_top_level else None
        if m and current_group is not None:
            finalize_current_spec()

            raw_id = m.group(1)
            rest = m.group(2)

            # Check for PROD_ONLY
            is_prod_only = False
            if rest.startswith("`PROD_ONLY`"):
                is_prod_only = True
                rest = rest[len("`PROD_ONLY`") :].strip()

            # Check for explicit priority in parens: (MUST), (SHOULD), etc.
            explicit_priority = None
            prio_m = re.match(r"^\(([A-Z_ ]+)\)\s*(.*)", rest)
            if prio_m:
                explicit_priority = prio_m.group(1)
                rest = prio_m.group(2)

            # Also check for `PROD_ONLY` after priority
            if rest.startswith("`PROD_ONLY`"):
                is_prod_only = True
                rest = rest[len("`PROD_ONLY`") :].strip()

            # Collect the full statement text (may span multiple lines)
            stmt_parts = [rest]

            # Look ahead for continuation lines
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line or not next_line[0] == " ":
                    break
                next_stripped = next_line.lstrip()
                if not next_stripped:
                    break
                if next_stripped.startswith("- "):
                    break  # sub-bullet, handle separately
                # Continuation text
                stmt_parts.append(next_stripped)
                j += 1

            current_spec = {
                "raw_id": raw_id,
                "explicit_priority": explicit_priority,
                "statement_parts": stmt_parts,
                "rationale": None,
                "is_prod_only": is_prod_only,
                "relationships": [],
            }
            i = j
            continue

        # Sub-bullet under current spec
        if stripped.startswith("- ") and current_spec is not None:
            sub_text = stripped[2:].strip()

            # Collect full sub-bullet text (may wrap)
            sub_parts = [sub_text]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Must be more deeply indented than the sub-bullet
                if not next_line or len(next_line) < 4:
                    break
                if next_line[:4] != "    ":
                    break
                next_stripped = next_line.lstrip()
                if not next_stripped:
                    break
                if next_stripped.startswith("- "):
                    break
                sub_parts.append(next_stripped)
                j += 1

            full_sub = " ".join(sub_parts)

            # Check for relationship
            if _is_relationship_line(full_sub):
                rels = _extract_relationships(full_sub)
                current_spec["relationships"].extend(rels)
            elif full_sub.startswith("**Rationale**:"):
                rat_text = full_sub[len("**Rationale**:") :].strip()
                current_spec["rationale"] = rat_text
            # Skip implementation notes, enforcement, etc.
            # (they don't go into the YAML)

            i = j
            continue

        i += 1

    finalize_current_spec()

    # Build description
    description = " ".join(description_lines).strip()
    if not description:
        description = title

    # Determine file-level prefix
    file_prefix = ""
    for g in groups:
        for s in g.get("specs", []):
            file_prefix = extract_prefix(s["id"])
            break
        if file_prefix:
            break
    if not file_prefix:
        file_prefix = path.stem.upper().replace("-", "")[:8]

    # Assign group IDs based on first spec in each group
    seen_group_ids: set[str] = set()
    fallback_idx = 0
    for g in groups:
        if g["specs"]:
            first_id = g["specs"][0]["id"]
            # Extract group portion: PREFIX-NN
            parts = first_id.split("-")
            if len(parts) >= 2:
                gid = f"{file_prefix}-{parts[1]}"
            else:
                gid = f"{file_prefix}-{fallback_idx:02d}"
                fallback_idx += 1
        else:
            gid = f"{file_prefix}-{fallback_idx:02d}"
            fallback_idx += 1

        # Deduplicate
        while gid in seen_group_ids:
            num = int(gid.rsplit("-", 1)[1]) + 1
            gid = f"{file_prefix}-{num:02d}"
        seen_group_ids.add(gid)

        # Rebuild group dict with id first
        g_new = {"id": gid, "title": g["title"]}
        if g.get("description"):
            g_new["description"] = g["description"]
        g_new["specs"] = g["specs"]
        g.clear()
        g.update(g_new)

    # Remove empty groups
    groups = [g for g in groups if g.get("specs")]

    return {
        "id": file_prefix,
        "title": title,
        "description": description,
        "version": "1.0.0",
        "kind": "general",
        "scope": ["prototype", "production"],
        "groups": groups,
    }


def _finalize_spec(spec: dict, group: dict) -> None:
    """Convert a raw spec dict into the final YAML-ready format."""
    raw_id = spec["raw_id"]
    renamed_id = rename_id(raw_id)

    # Build full statement
    statement = " ".join(spec["statement_parts"]).strip()

    priority = detect_priority(statement, spec.get("explicit_priority"))

    result: dict = {
        "id": renamed_id,
        "priority": priority,
        "statement": statement,
    }

    if spec.get("rationale"):
        result["rationale"] = spec["rationale"]

    if spec.get("is_prod_only"):
        result["scope"] = ["production"]

    rels = spec.get("relationships", [])
    if rels:
        result["relationships"] = rels

    group["specs"].append(result)


class _SpecDumper(yaml.SafeDumper):
    """Custom YAML dumper with folded block scalars for long strings."""

    pass


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    if "\n" in data or len(data) > 80:
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style=">"
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_SpecDumper.add_representer(str, _str_representer)


def write_yaml(data: dict, out_path: Path) -> None:
    """Write the parsed spec data as YAML."""
    out_path.write_text(
        yaml.dump(
            data,
            Dumper=_SpecDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=88,
        )
    )


def migrate_file(md_path: Path) -> Path:
    """Migrate a single .md spec file to .yaml."""
    data = parse_spec_md(md_path)
    yaml_path = md_path.with_suffix(".yaml")
    write_yaml(data, yaml_path)
    return yaml_path


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <spec_file_or_dir>", file=sys.stderr)
        sys.exit(2)

    target = Path(sys.argv[1])

    if target.is_dir():
        md_files = sorted(target.glob("*.md"))
        for md_file in md_files:
            if md_file.name in SKIP_FILES:
                print(f"  SKIP {md_file.name}")
                continue
            yaml_path = migrate_file(md_file)
            print(f"  {md_file.name} -> {yaml_path.name}")
    elif target.is_file():
        if target.name in SKIP_FILES:
            print(f"  SKIP {target.name}")
            sys.exit(0)
        yaml_path = migrate_file(target)
        print(f"  {target.name} -> {yaml_path.name}")
    else:
        print(f"Not found: {target}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
