"""Tests for vultron.metadata.adr.back_edges (#4410, ADR-0127).

The live-corpus test is the gate: every live decision record has a back-edge
from ``specs/`` or ``notes/``, or a record-only exemption, and no exemption is
stale. The pure-function tests below pin what counts as a back-edge.
"""

from __future__ import annotations

import inspect

import pytest

from vultron.metadata.adr import back_edges
from vultron.metadata.adr.back_edges import (
    RECORD_ONLY_EXEMPTIONS,
    LiveRecord,
    audit_back_edges,
    audit_corpus,
    live_records,
)
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.specs.schema import AdrStatus

#: Live records known to have no back-edge yet. A ratchet with terminal value
#: empty: ADR-0003 was left out of #4410 on purpose (its AC-5), and #4459 gives
#: it a home now that #4391 narrowed it to the legacy simulator.
#:
#: owner: #4459
KNOWN_HOMELESS_RECORDS: frozenset[str] = frozenset({"ADR-0003"})

_A = LiveRecord(adr_id="ADR-0100", file_name="0100-alpha.md")
_B = LiveRecord(adr_id="ADR-0101", file_name="0101-beta.md")


def _fm(status: AdrStatus) -> AdrFrontmatter:
    links = (
        {"superseded_by": "0100-alpha.md"}
        if status
        in (
            AdrStatus.SUPERSEDED,
            AdrStatus.DEPRECATED,
        )
        else {}
    )
    return AdrFrontmatter.model_validate(
        {
            "status": status.value,
            "created": "2020-01-01",
            "updated": "2020-01-01",
            "revision": 1,
            **links,
        }
    )


class TestAuditBackEdges:
    def test_record_with_nothing_pointing_back_is_homeless(self):
        report = audit_back_edges([_A], [], [], exemptions=())
        assert report.homeless == ("ADR-0100",)
        assert not report.clean

    def test_structured_adr_edge_is_a_back_edge(self):
        report = audit_back_edges([_A], ["ADR-0100"], [], exemptions=())
        assert report.clean

    def test_id_citation_in_prose_is_a_back_edge(self):
        report = audit_back_edges(
            [_A], [], ["Provenance: ADR-0100."], exemptions=()
        )
        assert report.clean

    def test_file_name_citation_is_a_back_edge(self):
        report = audit_back_edges(
            [_A], [], ["see docs/adr/0100-alpha.md"], exemptions=()
        )
        assert report.clean

    def test_id_must_be_a_whole_token(self):
        report = audit_back_edges([_A], [], ["ADR-01000 and XADR-0100"], ())
        assert report.homeless == ("ADR-0100",)

    def test_exempt_record_is_not_homeless(self):
        report = audit_back_edges([_A], [], [], exemptions=["ADR-0100"])
        assert report.clean

    def test_exemption_with_a_back_edge_is_stale(self):
        report = audit_back_edges(
            [_A], ["ADR-0100"], [], exemptions=["ADR-0100"]
        )
        assert report.stale_exemptions == ("ADR-0100",)
        assert not report.clean

    def test_exemption_naming_no_live_record_is_stale(self):
        report = audit_back_edges([_A], ["ADR-0100"], [], ["ADR-0999"])
        assert report.stale_exemptions == ("ADR-0999",)

    def test_results_are_sorted(self):
        report = audit_back_edges([_B, _A], [], [], exemptions=())
        assert report.homeless == ("ADR-0100", "ADR-0101")


class TestLiveRecords:
    @pytest.mark.parametrize(
        "status",
        [
            AdrStatus.PROPOSED,
            AdrStatus.ACCEPTED,
            AdrStatus.ACCEPTED_PROVISIONAL,
        ],
    )
    def test_open_statuses_are_live(self, status):
        records = live_records({"docs/adr/0100-alpha.md": _fm(status)})
        assert records == [_A]

    @pytest.mark.parametrize(
        "status",
        [AdrStatus.SUPERSEDED, AdrStatus.DEPRECATED, AdrStatus.REJECTED],
    )
    def test_retired_statuses_are_not_live(self, status):
        assert live_records({"docs/adr/0100-alpha.md": _fm(status)}) == []

    def test_a_record_name_without_a_number_raises(self):
        with pytest.raises(ValueError, match="no number"):
            live_records({"docs/adr/alpha.md": _fm(AdrStatus.ACCEPTED)})

    def test_archived_records_are_not_live(self):
        registry = {"docs/adr/archived/0100-alpha.md": _fm(AdrStatus.ACCEPTED)}
        assert live_records(registry) == []


class TestExemptionSet:
    def test_is_marked_as_a_pinned_exemption_set(self):
        """ARCH-18-003 / ARCH-18-005: permanent marker, described as pinned.

        The marker and the description must sit in the comment block directly
        above the constant, not merely somewhere in the module.
        """
        lines = inspect.getsource(back_edges).splitlines()
        at = next(
            i
            for i, line in enumerate(lines)
            if line.startswith("RECORD_ONLY_EXEMPTIONS")
        )
        block: list[str] = []
        for line in reversed(lines[:at]):
            if not line.startswith("#:"):
                break
            block.append(line)
        comment = " ".join(block)
        assert "permanent: MS-11-006" in comment
        assert "pinned exemption set" in comment
        assert "pinned exemption set" in (back_edges.__doc__ or "")

    def test_holds_only_the_meta_process_records(self):
        assert {"ADR-0000", "ADR-0001"} == RECORD_ONLY_EXEMPTIONS


@pytest.mark.spec_corpus
def test_every_live_record_has_a_back_edge_or_an_exemption(real_registry):
    """The live gate: computed from the corpus, never from a count (MS-16-002)."""
    report = audit_corpus(registry=real_registry)
    assert report.stale_exemptions == (), (
        "Remove these from RECORD_ONLY_EXEMPTIONS — they now have a back-edge "
        f"or are no longer live records: {report.stale_exemptions}"
    )
    assert set(report.homeless) == KNOWN_HOMELESS_RECORDS, (
        "Live decision records with no back-edge from specs/ or notes/: give "
        "each an adr: edge on the requirement that covers it, state its "
        "decision in a spec or note citing it, or (only for a one-time process "
        "choice, MS-11-006) add it to RECORD_ONLY_EXEMPTIONS. "
        "See notes/specs-vs-adrs.md. "
        f"Got {sorted(report.homeless)}, expected "
        f"{sorted(KNOWN_HOMELESS_RECORDS)}."
    )
