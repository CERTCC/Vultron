"""Tests for vultron.metadata.text_cache (#5880)."""

import uuid
import warnings
from collections.abc import Callable

import pytest

from vultron.metadata import text_cache
from vultron.metadata.specs import marked_tests
from vultron.metadata.specs.marked_tests import MarkedFile
from vultron.metadata.text_cache import CACHE_DIR_ENV, cached_read


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(CACHE_DIR_ENV, str(tmp_path / "cache"))
    return tmp_path / "cache"


def cached_strings(namespace, version, text, read):
    """:func:`cached_read` of a set of strings, one per line."""
    return cached_read(
        namespace,
        version,
        text,
        read,
        encode=lambda values: "\n".join(sorted(values)),
        decode=lambda entry: frozenset(filter(None, entry.split("\n"))),
    )


class _CountingReader:
    def __init__(self, values: frozenset[str] = frozenset({"A", "B"})):
        self.calls: list[str] = []
        self.values = values

    def __call__(self, text: str) -> frozenset[str]:
        self.calls.append(text)
        return self.values


def test_a_second_process_reads_an_unchanged_text_from_disk():
    """The entry outlives the first reader: the second never runs."""
    first, second = _CountingReader(), _CountingReader()
    assert cached_strings("ns", "v1", "text", first) == {"A", "B"}
    assert cached_strings("ns", "v1", "text", second) == {"A", "B"}
    assert (len(first.calls), len(second.calls)) == (1, 0)


def test_an_edited_text_is_read_again():
    reader = _CountingReader()
    cached_strings("ns", "v1", "text", reader)
    cached_strings("ns", "v1", "text, edited", reader)
    assert reader.calls == ["text", "text, edited"]


def test_a_new_reader_version_reads_every_text_again():
    reader = _CountingReader()
    cached_strings("ns", "v1", "text", reader)
    cached_strings("ns", "v2", "text", reader)
    assert len(reader.calls) == 2


def test_an_empty_result_is_cached_as_empty():
    reader = _CountingReader(frozenset())
    cached_strings("ns", "v1", "text", reader)
    assert cached_strings("ns", "v1", "text", reader) == frozenset()
    assert len(reader.calls) == 1


def test_a_fault_is_not_cached():
    def failing(text: str) -> frozenset[str]:
        raise SyntaxError("bad")

    with pytest.raises(SyntaxError):
        cached_strings("ns", "v1", "text", failing)
    assert cached_strings("ns", "v1", "text", _CountingReader()) == {"A", "B"}


def test_an_entry_that_does_not_decode_is_a_miss():
    def decode(entry: str) -> frozenset[str]:
        raise ValueError(entry)

    reader = _CountingReader()
    for _ in range(2):
        assert cached_read(
            "ns", "v1", "t", reader, encode=str, decode=decode
        ) == {"A", "B"}
    assert len(reader.calls) == 2


def test_an_unwritable_cache_costs_the_read_not_the_answer(
    _cache_dir, monkeypatch
):
    _cache_dir.parent.mkdir(parents=True, exist_ok=True)
    _cache_dir.write_text("a file, not a directory")
    reader = _CountingReader()
    assert cached_strings("ns", "v1", "text", reader) == {"A", "B"}
    assert cached_strings("ns", "v1", "text", reader) == {"A", "B"}
    assert len(reader.calls) == 2


def test_the_default_root_is_under_the_xdg_cache(monkeypatch, tmp_path):
    monkeypatch.delenv(CACHE_DIR_ENV)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert text_cache.cache_root() == tmp_path / "vultron"


def test_the_marker_reader_parses_an_unchanged_file_once_across_processes(
    monkeypatch,
):
    """A fresh worker reads a test file's markers from disk (#5880)."""
    parses: list[str] = []
    real_parse: Callable[[str], MarkedFile] = marked_tests._parse_file

    def counting_parse(source: str) -> MarkedFile:
        parses.append(source)
        return real_parse(source)

    monkeypatch.setattr(marked_tests, "_parse_file", counting_parse)
    source = (
        f"# {uuid.uuid4()}\nimport pytest\n"
        "class TestX:\n"
        "    @pytest.mark.spec('A', 'B')\n"
        "    @pytest.mark.xfail(reason='#1 held', strict=True)\n"
        "    def test_a(self): pass\n"
        "    @pytest.mark.spec('D')\n"
        "    @pytest.mark.xfail(strict=True)\n"
        "    def test_b(self): pass\n"
        "def _factory():\n    return pytest.mark.spec('C')\n"
        "TEXT = \"pytest.mark.spec('NOT-A-MARKER')\"\n"
    )
    first = marked_tests.read_marked_file("t.py", source)
    # A new process starts with empty in-memory caches.
    marked_tests.read_marked_file.cache_clear()
    marked_tests._file_at_no_path.cache_clear()
    again = marked_tests.read_marked_file("u.py", source)
    assert len(parses) == 1
    assert again.spec_ids == first.spec_ids == {"A", "B", "C", "D"}
    assert {(c.test, c.spec_ids, c.xfail_reasons) for c in again.cases} == {
        ("u.py::TestX::test_a", frozenset({"A", "B"}), ("#1 held",)),
        ("u.py::TestX::test_b", frozenset({"D"}), (None,)),
        ("u.py", frozenset({"C"}), ()),
    }
    assert marked_tests.marked_spec_ids(source) == {"A", "B", "C", "D"}
    assert len(parses) == 1


def test_a_cached_file_that_does_not_parse_names_the_path_each_time():
    source = "import pytest\n@pytest.mark.spec('A')\ndef broken(:\n"
    for path in ("a.py", "b.py"):
        with pytest.raises(SyntaxError) as raised:
            marked_tests.read_marked_file(path, source)
        assert raised.value.filename == path


def test_a_write_that_fails_after_the_temporary_file_leaves_no_file(
    _cache_dir, monkeypatch
):
    def refuse(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(text_cache.os, "replace", refuse)
    reader = _CountingReader()
    assert cached_strings("ns", "v1", "text", reader) == {"A", "B"}
    assert [p for p in _cache_dir.rglob("*") if p.is_file()] == []


def test_no_home_directory_costs_the_read_not_the_answer(monkeypatch):
    def no_home() -> object:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.delenv(CACHE_DIR_ENV)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(text_cache.Path, "home", no_home)
    assert cached_strings("ns", "v1", "text", _CountingReader()) == {"A", "B"}


def test_the_code_version_follows_the_reader_source(tmp_path):
    reader = tmp_path / "reader.py"
    reader.write_text("A = 1\n")
    before = text_cache.code_version(reader)
    assert text_cache.code_version(reader) == before
    reader.write_text("A = 2\n")
    assert text_cache.code_version(reader) != before


def test_a_parse_kept_on_disk_ignores_the_warnings_filter():
    """An invalid escape warns; the entry must not depend on that filter."""
    source = (
        f"# {uuid.uuid4()}\nimport pytest\n"
        "@pytest.mark.spec('A')\ndef test_a(): return '\\d'\n"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert marked_tests.read_marked_file("t.py", source).spec_ids == {"A"}
