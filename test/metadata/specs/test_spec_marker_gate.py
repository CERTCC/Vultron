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

"""
Tests for the spec-marker validation gate in ``pytest_collection_modifyitems``
(issue #3331, SR-05-002).

``test/test_integration_timeout_tier.py`` covers the timeout half of the same
hook. This file covers the spec-marker half, and specifically its failure path:
the hook used to wrap the registry load in a bare ``except Exception: return``,
so a single malformed file in ``specs/`` disabled SR-05-002 marker validation for
the whole session with no warning and no change in exit code.

It lives under ``test/metadata/specs/`` rather than next to ``test/conftest.py``
because asserting the gate *fires* requires naming a spec ID that does not
resolve, and SR-04-008 hard-errors on a phantom spec-ID citation in any Python
file outside this directory — this is the one place exempted for synthetic
fixture IDs. Moving this file up a level turns ``spec-lint`` red.

Measurement at the time: on a healthy corpus the clause absorbed nothing across
the full unit suite, and on a corrupted one it absorbed a ``ScannerError`` while
a deliberately bogus marker ID went unreported.

The gate stays non-blocking on purpose — aborting the session would mean a
malformed spec file blocks the very tests that diagnose it — so "visible" here
means a warning, and that warning needs an ``always::`` filter to outrank the
``"error"`` rule in ``pyproject.toml``. ``TestWarningIsNotEscalated`` pins that,
because without it this fix would convert a silent skip into a hard abort.
"""

import contextlib
import warnings

import pytest
import yaml
from yaml.scanner import ScannerError

from test import conftest as root_conftest
from vultron.metadata.specs import (
    SpecRegistryUnavailableWarning,
    UnknownSpecIdWarning,
    warn_spec_registry_unavailable,
)


class SpecMarkedItem:
    """Minimal stand-in for a pytest ``Item`` carrying a ``spec`` marker."""

    def __init__(self, spec_id=None):
        self.spec_id = spec_id

    def get_closest_marker(self, name):
        if name == "spec" and self.spec_id is not None:
            return pytest.mark.spec(self.spec_id).mark
        return None

    def add_marker(self, marker):  # pragma: no cover - no marker is added
        raise AssertionError("the spec gate must not add markers")


def _raise_on_load(exc):
    """Return a ``load_registry`` replacement that raises *exc*."""

    def _fail(spec_dir):
        raise exc

    return _fail


@contextlib.contextmanager
def _escalated(*categories):
    """Turn *categories* into errors for the duration of the block.

    Used to assert a warning is **not** emitted. ``pytest.warns`` cannot express
    that, and simply not asserting would let the test pass vacuously.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        for category in categories:
            warnings.filterwarnings("error", category=category)
        yield


def _run_gate(items=()):
    """Invoke the hook under test with *items*."""
    root_conftest.pytest_collection_modifyitems(None, None, list(items))


class TestUnloadableCorpusIsVisible:
    """A corpus that exists but does not load MUST warn, not skip silently."""

    @pytest.mark.parametrize(
        "exc",
        [
            ScannerError(
                None, None, "mapping values are not allowed here", None
            ),
            ValueError("Duplicate spec ID: DUR-01-001"),
            OSError("unreadable"),
        ],
        ids=["yaml-syntax", "duplicate-id", "unreadable-file"],
    )
    def test_load_failure_emits_the_warning(self, monkeypatch, exc):
        monkeypatch.setattr(
            root_conftest, "load_registry", _raise_on_load(exc)
        )

        with pytest.warns(SpecRegistryUnavailableWarning):
            _run_gate()

    def test_warning_names_the_cause_and_the_requirement(self, monkeypatch):
        """A reader must be able to act on it without instrumenting anything."""
        monkeypatch.setattr(
            root_conftest,
            "load_registry",
            _raise_on_load(ValueError("Duplicate spec ID: DUR-01-001")),
        )

        with pytest.warns(SpecRegistryUnavailableWarning) as record:
            _run_gate()

        message = str(record[0].message)
        assert "Duplicate spec ID: DUR-01-001" in message
        assert "SR-05-002" in message

    def test_no_marker_warnings_when_the_registry_is_unavailable(
        self, monkeypatch
    ):
        """The gate really is off — the warning is the only signal there is.

        Pinning this keeps the warning honest. If a later change validated
        markers against a partially-loaded registry instead, the warning would
        be claiming something untrue.
        """
        monkeypatch.setattr(
            root_conftest, "load_registry", _raise_on_load(ValueError("boom"))
        )

        with pytest.warns(SpecRegistryUnavailableWarning):
            with _escalated(UnknownSpecIdWarning):
                _run_gate([SpecMarkedItem("BOGUS-99-999")])

    def test_timeout_half_of_the_hook_still_runs(self, monkeypatch):
        """The early return must not cost integration tests their timeout.

        ``apply_integration_timeout`` runs before the registry load, so a
        reordering that moved it after the ``return`` would silently drop the
        integration-tier ceiling on an unloadable corpus.
        """
        monkeypatch.setattr(
            root_conftest, "load_registry", _raise_on_load(ValueError("boom"))
        )
        calls = []
        monkeypatch.setattr(
            root_conftest,
            "apply_integration_timeout",
            lambda items: calls.append(items) or 0,
        )

        with pytest.warns(SpecRegistryUnavailableWarning):
            _run_gate()

        assert calls == [[]]


class TestUnexpectedFailureStillSurfaces:
    """A bug in the loader is not a bad spec file and MUST NOT degrade."""

    def test_unexpected_exception_type_propagates(self, monkeypatch):
        monkeypatch.setattr(
            root_conftest,
            "load_registry",
            _raise_on_load(AttributeError("loader bug")),
        )

        with pytest.raises(AttributeError, match="loader bug"):
            _run_gate()

    def test_caught_types_are_the_documented_load_failures(self):
        """Bare ``Exception`` here is the defect; keep the tuple narrow."""
        caught = root_conftest._REGISTRY_LOAD_ERRORS

        assert Exception not in caught
        assert BaseException not in caught
        assert set(caught) == {ValueError, OSError, yaml.YAMLError}


class TestHealthyCorpusStillValidates:
    """The fix must not cost the gate its normal behaviour."""

    def test_unknown_marker_id_is_reported_against_the_real_corpus(self):
        with pytest.warns(UnknownSpecIdWarning, match="BOGUS-99-999"):
            _run_gate([SpecMarkedItem("BOGUS-99-999")])

    def test_known_marker_id_is_accepted_against_the_real_corpus(self):
        with _escalated(UnknownSpecIdWarning, SpecRegistryUnavailableWarning):
            _run_gate([SpecMarkedItem("SR-05-002")])

    def test_real_corpus_emits_no_unavailable_warning(self):
        """Guards against the new warning firing on every healthy session."""
        with _escalated(SpecRegistryUnavailableWarning):
            _run_gate()


class TestWarningIsNotEscalated:
    """The ``always::`` filter is load-bearing, not decoration.

    ``pyproject.toml`` sets ``filterwarnings = [..., "error", ...]``. Without an
    entry that outranks it, this fix would turn a silently-skipped gate into a
    session that cannot run at all whenever a spec file is malformed.
    """

    _ENTRY = "always::vultron.metadata.specs.SpecRegistryUnavailableWarning"

    @staticmethod
    def _filters(pytestconfig):
        return list(pytestconfig.getini("filterwarnings"))

    def test_unavailable_warning_has_an_always_entry(self, pytestconfig):
        assert self._ENTRY in self._filters(pytestconfig)

    def test_the_always_entry_outranks_the_error_rule(self, pytestconfig):
        """pytest applies these in order, so ``error`` must not come first."""
        filters = self._filters(pytestconfig)

        assert filters.index(self._ENTRY) < filters.index("error")

    def test_error_rule_is_still_in_force(self, pytestconfig):
        """Guard against 'fixing' this by dropping the strict rule entirely."""
        assert "error" in self._filters(pytestconfig)


class TestWarnSpecRegistryUnavailable:
    """Unit-level contract for the warning helper."""

    def test_is_a_user_warning(self):
        assert issubclass(SpecRegistryUnavailableWarning, UserWarning)

    def test_is_distinct_from_the_unknown_id_warning(self):
        """Two different faults; a filter must be able to target one alone."""
        assert not issubclass(
            SpecRegistryUnavailableWarning, UnknownSpecIdWarning
        )
        assert not issubclass(
            UnknownSpecIdWarning, SpecRegistryUnavailableWarning
        )

    def test_emits_with_the_directory_and_the_cause(self, tmp_path):
        with pytest.warns(SpecRegistryUnavailableWarning) as record:
            warn_spec_registry_unavailable(tmp_path, ValueError("bad enum"))

        message = str(record[0].message)
        assert str(tmp_path) in message
        assert "ValueError" in message
        assert "bad enum" in message
