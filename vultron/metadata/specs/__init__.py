"""Spec registry for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.md SR-02, SR-03.
Pytest integration: specs/spec-registry.md SR-05.
"""

import warnings

from vultron.metadata.specs.registry import SpecRegistry, load_registry


class UnknownSpecIdWarning(UserWarning):
    """Warning emitted when a test references a spec ID not in the registry.

    Emitted (non-blocking) by ``pytest_collection_modifyitems`` when a
    ``@pytest.mark.spec`` marker references an ID that cannot be found in the
    loaded :class:`SpecRegistry` (SR-05-002).
    """


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
    "SpecRegistry",
    "UnknownSpecIdWarning",
    "load_registry",
    "warn_unknown_spec_id",
]
