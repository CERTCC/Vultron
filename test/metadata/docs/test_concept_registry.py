"""Tests for ``introduces:`` declarations, the concept registry (DF-11-002).

Each finding names the offending key's ``path:line`` (MS-17-001).
"""

from __future__ import annotations

import pytest

from test.metadata.docs._level_tree import (
    failures,
    make_repo,
    leveled_page,
)

# ---------------------------------------------------------------------------
# ``introduces:`` declarations
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-002")
class TestIntroduces:
    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ("Case Ledger Entry", "non-empty list"),
            ("[]", "non-empty list"),
            ("[Case Ledger Entry, Case Ledger Entry]", "more than once"),
            ("[Ledger Thing]", "Ledger Thing is not a term"),
            ("[V/v]", "no spelling the scan can match"),
        ],
    )
    def test_malformed_value_names_the_key_line(
        self, tmp_path, value, message
    ):
        root = make_repo(
            tmp_path, {"topics/ledger.md": leveled_page(400, introduces=value)}
        )

        (failure,) = failures(root)

        assert failure.location == "docs/topics/ledger.md:4"
        assert message in failure.detail

    def test_every_fault_in_a_value_is_reported(self, tmp_path):
        value = "[Case Ledger Entry, Case Ledger Entry, Ledger Thing, V/v]"
        root = make_repo(
            tmp_path, {"topics/ledger.md": leveled_page(400, introduces=value)}
        )

        details = [f.detail for f in failures(root)]

        assert len(details) == 3
        assert any("more than once" in d for d in details)
        assert any("Ledger Thing is not a term" in d for d in details)
        assert any("V/v has no spelling" in d for d in details)

    def test_a_term_has_one_introducer(self, tmp_path):
        root = make_repo(
            tmp_path,
            {
                "topics/other.md": leveled_page(
                    500, introduces="[Case Ledger Entry]"
                )
            },
        )

        (failure,) = failures(root)

        assert "already introduced by docs/" in failure.detail

    def test_working_record_page_cannot_introduce(self, tmp_path):
        page = leveled_page(
            None, audience="[project-contributor]", introduces="[CASE_MANAGER]"
        )
        root = make_repo(tmp_path, {"adr/0001-x.md": page})

        (failure,) = failures(root)

        assert "DF-11-012" in failure.detail

    def test_fragment_cannot_introduce(self, tmp_path):
        root = make_repo(
            tmp_path,
            {
                "howto/_frag.md": "---\nintroduces: [CASE_MANAGER]\n---\nx\n",
                "howto/host.md": leveled_page(
                    300, '{% include-markdown "./_frag.md" %}\n'
                ),
            },
            nav=["howto/host.md", "topics/ledger.md"],
        )

        (failure,) = failures(root)

        assert "DF-11-010" in failure.detail
