---
title: "TB-14-003 offers raising the tier or a per-test marker, and omits the remedy the project actually prefers for one slow test"
type: learning
timestamp: "2026-11-05T22:05:00Z"
source: ISSUE-5943
signal: spec-ambiguity
---

TB-14-003 reads: "When a timeout tier fires on honest work rather than on a
hang, the tier SHOULD be raised, rather than each affected test given its own
`@pytest.mark.timeout` or recorded as flaky." Two remedies, with a preference
between them.

While splitting the CI test job (#5943),
`test/metadata/specs/test_docs_render.py::test_docs_callouts_link_existing_rows`
tripped the 30s unit tier twice in local parallel runs. It costs ~15s idle,
about five times the next slowest test in its file. Read literally, TB-14-003
says to raise the shared tier — which is the hang detector for roughly 29,000
other tests, so one outlier would double how long every hang holds a worker.

The remedy the project had already chosen for this exact test is neither of
TB-14-003's two: #5952 asks for the repeated render to be shared so the test
runs in under a third of its ceiling. Make the test fast. The requirement does
not mention that option, and the `pyproject.toml` comment that sized the tier
did not either until this PR.

Claim, from one instance: TB-14-003's fork is incomplete in a way that pushes
an agent toward the most expensive of the three options. A requirement that
enumerates remedies needs the preferred one in the list, or the enumeration
reads as exhaustive. The candidate wording makes speeding the test up the
first choice, keeps raising the tier for when the whole tier is mis-sized, and
admits a per-test marker only as an interim measure naming the issue that will
remove it — which is what #5943 did and what the tier's comment now says.

Open question for `learn`: whether TB-14-003 should be reworded, or split so
that "make the test fast" and "re-size a mis-sized tier" are separate
requirements with different triggers. The distinction that decides it is
whether one test is an outlier or the tier itself is wrong, and no requirement
currently names that test.
