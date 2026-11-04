"""Coerce a reviewed manifest, read back from JSON, into typed entries."""

from __future__ import annotations

from vultron.metadata.history.backfill_implementation.manifest import (
    BackfillManifest,
    ManifestEntry,
)


def _require_manifest_entry_int(
    data: dict[object, object], field: str, message: str
) -> int:
    value = data.get(field)
    if not isinstance(value, int):
        raise ValueError(message)  # noqa: TRY004  # ruff-baseline #3353
    return value


def _require_manifest_entry_str(
    data: dict[object, object], field: str, message: str
) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(message)  # noqa: TRY004  # ruff-baseline #3353
    return value


def _optional_manifest_entry_str(
    data: dict[object, object], field: str
) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"manifest entry {field} is malformed")  # noqa: TRY004  # ruff-baseline #3353
    return value


def _manifest_entry_str_list(
    data: dict[object, object], field: str
) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"manifest entry {field} is malformed")
    return value


def _coerce_manifest_entry(data: object) -> ManifestEntry:
    """Validate and coerce JSON-loaded manifest entry data."""
    if not isinstance(data, dict):
        raise ValueError("manifest entry is malformed")  # noqa: TRY004  # ruff-baseline #3353

    return ManifestEntry(
        heading_line=_require_manifest_entry_int(
            data,
            "heading_line",
            "manifest entry heading_line is missing",
        ),
        raw_heading=_require_manifest_entry_str(
            data,
            "raw_heading",
            "manifest entry raw_heading is missing",
        ),
        title=_require_manifest_entry_str(
            data,
            "title",
            "manifest entry title is missing",
        ),
        candidate_source=_optional_manifest_entry_str(
            data, "candidate_source"
        ),
        source=_require_manifest_entry_str(
            data,
            "source",
            "manifest entry source is missing",
        ),
        source_origin=_require_manifest_entry_str(
            data,
            "source_origin",
            "manifest entry source_origin is missing",
        ),
        canonical_date=_optional_manifest_entry_str(data, "canonical_date"),
        target_month=_require_manifest_entry_str(
            data,
            "target_month",
            "manifest entry target_month is missing",
        ),
        target_path=_require_manifest_entry_str(
            data,
            "target_path",
            "manifest entry target_path is missing",
        ),
        advisory_dates=_manifest_entry_str_list(data, "advisory_dates"),
        flags=_manifest_entry_str_list(data, "flags"),
        entry_markdown=_require_manifest_entry_str(
            data,
            "entry_markdown",
            "manifest entry entry_markdown is missing",
        ),
    )


def _coerce_manifest(data: object) -> BackfillManifest:
    """Validate and coerce JSON-loaded manifest data."""
    if not isinstance(data, dict):
        raise ValueError("manifest is malformed")  # noqa: TRY004  # ruff-baseline #3353

    kind = data.get("kind")
    generated_at = data.get("generated_at")
    legacy_file = data.get("legacy_file")
    entry_count = data.get("entry_count")
    status = data.get("status")
    blocking_entry_count = data.get("blocking_entry_count")
    raw_entries = data.get("entries")

    if not isinstance(kind, str):
        raise ValueError("manifest kind is missing")  # noqa: TRY004  # ruff-baseline #3353
    if not isinstance(generated_at, str):
        raise ValueError("manifest generated_at is missing")  # noqa: TRY004  # ruff-baseline #3353
    if not isinstance(legacy_file, str):
        raise ValueError("manifest legacy_file is missing")  # noqa: TRY004  # ruff-baseline #3353
    if not isinstance(entry_count, int):
        raise ValueError("manifest entry_count is missing")  # noqa: TRY004  # ruff-baseline #3353
    if not isinstance(status, str):
        raise ValueError("manifest status is missing")  # noqa: TRY004  # ruff-baseline #3353
    if not isinstance(blocking_entry_count, int):
        raise ValueError("manifest blocking_entry_count is missing")  # noqa: TRY004  # ruff-baseline #3353
    if not isinstance(raw_entries, list):
        raise ValueError("manifest entries are missing or malformed")  # noqa: TRY004  # ruff-baseline #3353

    entries = [_coerce_manifest_entry(raw_entry) for raw_entry in raw_entries]
    return BackfillManifest(
        kind=kind,
        generated_at=generated_at,
        legacy_file=legacy_file,
        entry_count=entry_count,
        status=status,
        blocking_entry_count=blocking_entry_count,
        entries=entries,
    )
