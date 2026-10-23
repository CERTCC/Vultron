"""Tests for UnknownSpecIdWarning and warn_unknown_spec_id (SR.3.3).

Covers: warning class importability, emission for unknown IDs, silence
for known IDs, and robustness with an empty registry.
"""

import warnings

import pytest

from vultron.metadata.specs import (
    UnknownSpecIdWarning,
    load_registry,
    warn_unknown_spec_id,
)


def test_unknown_spec_id_warning_is_user_warning():
    assert issubclass(UnknownSpecIdWarning, UserWarning)


def test_warn_unknown_spec_id_emits_for_unknown(loaded_registry):
    with pytest.warns(UnknownSpecIdWarning, match="XX-99-999"):
        warn_unknown_spec_id("XX-99-999", loaded_registry)


def test_warn_unknown_spec_id_silent_for_known(loaded_registry):
    # A known ID must not emit UnknownSpecIdWarning
    with warnings.catch_warnings():
        warnings.simplefilter("error", UnknownSpecIdWarning)
        warn_unknown_spec_id("TST-01-001", loaded_registry)


def test_warn_unknown_spec_id_empty_registry(tmp_path):
    # Empty registry — any ID is unknown, so a warning is emitted
    registry = load_registry(tmp_path)
    assert registry.files == []
    with pytest.warns(UnknownSpecIdWarning):
        warn_unknown_spec_id("XX-99-999", registry)
