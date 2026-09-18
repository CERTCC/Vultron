"""Spec registry for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.yaml SR-02, SR-03.
Pytest integration: specs/spec-registry.yaml SR-05.
Coverage reporter: specs/spec-registry.yaml SR-05-004, SR-05-005.
"""

import warnings
from pathlib import Path

from vultron.metadata.specs.coverage import (
    ProtocolCoverageReport,
    collect_marked_ids,
    compute_protocol_coverage,
)
from vultron.metadata.specs.registry import SpecRegistry, load_registry


class UnknownSpecIdWarning(UserWarning):
    """Warning emitted when a test references a spec ID not in the registry.

    Emitted (non-blocking) by ``pytest_collection_modifyitems`` when a
    ``@pytest.mark.spec`` marker references an ID that cannot be found in the
    loaded :class:`SpecRegistry` (SR-05-002).
    """


class SpecRegistryUnavailableWarning(UserWarning):
    """Warning emitted when the spec registry cannot be loaded for validation.

    The SR-05-002 marker check needs a loaded :class:`SpecRegistry`. When the
    corpus is present but unloadable, that check cannot run — and its absence
    must be *visible*, because a silently skipped gate reports the same clean
    pass as a corpus with no unknown IDs in it (#3331).

    Non-blocking by design, which requires a matching ``always::`` entry in
    ``filterwarnings`` **listed after** ``pyproject.toml``'s ``"error"`` entry
    (SR-05-007) — pytest inserts ini filters at index 0 in list order, so a later
    entry outranks an earlier one and an exemption placed *before* ``"error"`` is
    a no-op. A malformed spec file must not abort the session, or the tests that
    diagnose it could not be run.
    """


def warn_spec_registry_unavailable(spec_dir: Path, exc: Exception) -> None:
    """Emit :class:`SpecRegistryUnavailableWarning` naming the load failure.

    Args:
        spec_dir: The spec directory whose load failed.
        exc: The exception raised by :func:`load_registry`.
    """
    warnings.warn(
        f"Spec registry at {spec_dir} could not be loaded, so "
        f"@pytest.mark.spec IDs were not validated this session "
        f"(SR-05-002): {type(exc).__name__}: {exc}",
        SpecRegistryUnavailableWarning,
        stacklevel=2,
    )


def warn_unknown_spec_id(spec_id: str, registry: SpecRegistry) -> None:
    """Emit :class:`UnknownSpecIdWarning` if ``spec_id`` is not in registry.

    Args:
        spec_id: The spec ID string to validate.
        registry: The loaded :class:`SpecRegistry` to check against.
    """
    try:
        registry.get(spec_id)
    except KeyError:
        warnings.warn(
            f"Unknown spec ID referenced in test marker: {spec_id!r}",
            UnknownSpecIdWarning,
            stacklevel=2,
        )


__all__ = [
    "ProtocolCoverageReport",
    "SpecRegistry",
    "SpecRegistryUnavailableWarning",
    "UnknownSpecIdWarning",
    "collect_marked_ids",
    "compute_protocol_coverage",
    "load_registry",
    "warn_spec_registry_unavailable",
    "warn_unknown_spec_id",
]
