"""Write stub ADR files for the ADR schema, loader and index tests."""

from __future__ import annotations

from pathlib import Path


def write_adr_stub(
    adr_dir: Path,
    name: str,
    status: str = "accepted",
    title: str | None = None,
    **links: str | list[str],
) -> Path:
    """Write ``adr_dir/name`` with valid lifecycle fields and the given links.

    Each keyword is a frontmatter field such as ``supersedes``. A string value
    is written as a scalar and a list as a YAML block list, so both forms the
    schema accepts can be exercised. The H1 is *title*, defaulting to *name*.
    """
    lines = [
        "---",
        f"status: {status}",
        "created: 2020-01-01",
        "updated: 2020-01-01",
        "revision: 1",
    ]
    for field, value in links.items():
        if isinstance(value, list):
            lines.append(f"{field}:")
            lines.extend(f"  - {v}" for v in value)
        else:
            lines.append(f"{field}: {value}")
    lines += ["---", f"# {title or name}", ""]
    adr_dir.mkdir(parents=True, exist_ok=True)
    path = adr_dir / name
    path.write_text("\n".join(lines))
    return path
