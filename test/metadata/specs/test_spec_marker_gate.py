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
means a warning, and that warning needs an ``always::`` filter that outranks the
``"error"`` rule in ``pyproject.toml``. **Outranking means being listed after
it**: pytest applies ini ``filterwarnings`` in list order through
``warnings.filterwarnings()``, which inserts at index 0, so a later entry wins.
Both spec-gate entries originally sat *before* ``"error"`` and were therefore
no-ops, which is why SR-05-002's "non-blocking" guarantee never actually held
(#2329 measured this first). ``TestWarningIsNotEscalated`` pins both halves —
the ordering and, in a real sub-session, the behaviour it produces.
"""

import contextlib
import warnings

import pytest

from test import conftest as root_conftest
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.specs import (
    SpecRegistryUnavailableWarning,
    UnknownSpecIdWarning,
    warn_spec_registry_unavailable,
)

pytest_plugins = ["pytester"]


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


def _redirect_spec_dir(monkeypatch, tmp_path, *, corpus_exists):
    """Point the hook's hard-coded ``specs/`` lookup into *tmp_path*.

    The hook derives ``spec_dir`` inline from ``Path(__file__)``, so there is no
    seam to override except ``Path`` itself. Patching it is what lets the two
    *silent* early returns be tested at all.
    """
    spec_dir = tmp_path / "repo" / "specs"
    if corpus_exists:
        spec_dir.mkdir(parents=True)
    monkeypatch.setattr(
        root_conftest,
        "Path",
        lambda _: tmp_path / "repo" / "test" / "conftest.py",
    )
    return spec_dir


@pytest.mark.spec("SR-05-006")
class TestNoCorpusStaysSilent:
    """The two *silent* early returns must stay silent.

    The docstring on the hook names three non-interchangeable early returns, and
    the point of #3331 is that they were conflated. Pinning the silent pair is
    what stops a future change from fixing the conflation in the other
    direction — warning on a corpus that is merely absent or empty, where
    nothing is wrong and there is nothing to validate against.
    """

    @pytest.mark.parametrize(
        "corpus_exists", [False, True], ids=["absent-dir", "empty-dir"]
    )
    def test_no_warning_and_no_validation(
        self, monkeypatch, tmp_path, corpus_exists
    ):
        _redirect_spec_dir(monkeypatch, tmp_path, corpus_exists=corpus_exists)

        with _escalated(UnknownSpecIdWarning, SpecRegistryUnavailableWarning):
            _run_gate([SpecMarkedItem("BOGUS-99-999")])


@pytest.mark.spec("SR-05-006")
class TestUnloadableCorpusIsVisible:
    """A corpus that exists but does not load MUST warn, not skip silently."""

    @pytest.mark.parametrize(
        "exc",
        [
            MetadataLoadError(
                "YAML parse error: mapping values are not allowed here",
                path="specs/broken.yaml",
                line=3,
                column=5,
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

    def test_real_yaml_syntax_fault_emits_the_warning(
        self, monkeypatch, tmp_path
    ):
        """End to end: the real loader on a corrupt corpus, no stand-in.

        A syntax fault used to escape ``load_registry`` as a bare
        ``ScannerError``, so the hook's tuple had to name ``yaml.YAMLError``.
        The loader now attributes it as a ``ValueError`` (MS-17-002), and this
        is what proves the narrower tuple still catches it.
        """
        spec_dir = _redirect_spec_dir(
            monkeypatch, tmp_path, corpus_exists=True
        )
        (spec_dir / "broken.yaml").write_text("id: X\ntitle: a: b\n")

        with pytest.warns(SpecRegistryUnavailableWarning) as record:
            _run_gate()

        assert "specs/broken.yaml:2:" in str(record[0].message)

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


@pytest.mark.spec("SR-05-006")
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

    def test_the_catch_is_not_blanket(self):
        """Bare ``Exception`` here is the defect; keep the tuple narrow.

        Deliberately not an exact-set assertion: which concrete types belong in
        the tuple is settled behaviourally by the parametrized test above, and
        the set has already shrunk once (#3324 made a YAML fault a
        ``ValueError``). Asserting the whole set would only be a
        change-detector on the constant.
        """
        caught = root_conftest._REGISTRY_LOAD_ERRORS

        assert Exception not in caught
        assert BaseException not in caught


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-05-002")
class TestHealthyCorpusStillValidates:
    """The fix must not cost the gate its normal behaviour.

    These read the real ``specs/`` corpus through the hook's own ``spec_dir``,
    so they carry ``spec_corpus`` — otherwise ``spec-check.yml`` would not run
    them on a specs-only PR, which is the gap that marker exists to close.
    """

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


@pytest.mark.spec("SR-05-007")
class TestWarningIsNotEscalated:
    """The ``always::`` filter is load-bearing, not decoration.

    ``pyproject.toml`` sets ``filterwarnings = [..., "error", ...]``. Without an
    entry that outranks it, this fix would turn a silently-skipped gate into a
    session that cannot run at all whenever a spec file is malformed.

    **Ordering is counter-intuitive and was originally recorded backwards.**
    pytest applies ini entries in list order through
    ``warnings.filterwarnings()``, which inserts each at index 0, so a **later**
    entry outranks an earlier one. An exemption listed *before* ``"error"`` is a
    no-op. Both spec-gate entries sat before it, which meant SR-05-002's
    "non-blocking" guarantee never held (see #2329, which measured this first).
    ``test_the_error_rule_does_not_escalate_the_warning`` pins the *behaviour*;
    the index test below pins the ordering that produces it. The index test
    alone is not enough — it passed while the behaviour was broken.
    """

    _ENTRY = "always::vultron.metadata.specs.SpecRegistryUnavailableWarning"

    @staticmethod
    def _filters(pytestconfig):
        return list(pytestconfig.getini("filterwarnings"))

    def test_unavailable_warning_has_an_always_entry(self, pytestconfig):
        assert self._ENTRY in self._filters(pytestconfig)

    def test_the_always_entry_outranks_the_error_rule(self, pytestconfig):
        """Later entries win, so the exemption must come *after* ``error``."""
        filters = self._filters(pytestconfig)

        assert filters.index(self._ENTRY) > filters.index("error")

    @pytest.mark.parametrize(
        "dotted_path",
        [
            "vultron.metadata.specs.SpecRegistryUnavailableWarning",
            "vultron.metadata.specs.UnknownSpecIdWarning",
        ],
        ids=["registry-unavailable", "unknown-spec-id"],
    )
    def test_the_error_rule_does_not_escalate_the_warning(
        self, pytester, pytestconfig, dotted_path
    ):
        """The behavioural half: a real sub-session under the real ini filters.

        Every other warning assertion in this file runs inside
        ``pytest.warns``/``catch_warnings``, which **replaces** the ini filters,
        so none of them can see an escalation — which is how the misordering
        shipped green. This one feeds the project's own ``filterwarnings`` list
        verbatim to a sub-session, so reordering the entries wrongly fails here.
        """
        entries = "\n".join(
            f"    {entry}" for entry in self._filters(pytestconfig)
        )
        pytester.makeini(f"[pytest]\nfilterwarnings =\n{entries}\n")
        module, _, name = dotted_path.rpartition(".")
        pytester.makepyfile(f"""
            import warnings

            from {module} import {name}


            def test_probe():
                warnings.warn("probe", {name})
            """)

        result = pytester.runpytest_subprocess("-p", "no:randomly")

        result.assert_outcomes(passed=1, warnings=1)

    def test_error_rule_is_still_in_force(self, pytestconfig):
        """Guard against 'fixing' this by dropping the strict rule entirely."""
        assert "error" in self._filters(pytestconfig)


@pytest.mark.spec("SR-05-006")
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
