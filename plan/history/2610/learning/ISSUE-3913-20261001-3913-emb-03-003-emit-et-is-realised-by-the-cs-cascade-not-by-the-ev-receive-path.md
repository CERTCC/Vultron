---
title: "EMB-03-003 says a Participant receiving EV on a public case MUST emit ET, but ADR-0113 maps it onto the CASE_MANAGER refusing the proposal with ER — the only marker test attests a refusal, and the termination is the CS cascade's"
type: learning
timestamp: "2026-10-01T02:10:00Z"
source: ISSUE-3913
signal: spec-gap
---

EMB-03-003: "A Participant in EM Active or Revise with CS in a public/exploit/
attack state receiving EV MUST emit ET to terminate the embargo immediately."
ADR-0113 step 2 cites it alongside EMB-01-002 for the CASE_MANAGER *refusing*
a proposal on a public, exploited or attacked case, and #3913 AC-1 asked for
an EMB-03-003 marker on the retained ER refusal. The marker test
(`test_a_revision_of_a_public_case_is_refused_with_er`) therefore asserts the
case stays `ACTIVE` and an ER `Reject` goes to the proposer — the opposite of
what the requirement's text says, and it is the only EMB-03-003 marker in the
suite.

Both readings are defensible and the corpus does not reconcile them. In the
CASE_MANAGER topology the embargo on a case that has gone public is torn down
by the CS public-event cascade (`PublicDisclosureBranchNode`) when the P/X/A
event is recorded, not by whichever EV happens to arrive afterwards; by the
time such an EV reaches the manager the embargo is normally already `EXITED`
and the EM guard refuses it. The ET the requirement names is thus emitted — but
by a different tree, on a different trigger. An EV arriving at `ACTIVE` with
P/X/A set (the scenario the marker test builds) is a race the cascade has not
yet resolved, and refusing the EV with ER rather than terminating the embargo
there keeps one mover for the EM write.

The gap: EMB-03-003 should either say that the termination is the CS cascade's
and the EV is refused (so the marker test matches the text), or keep its ET
wording and gain a separate marker on the cascade path, so that a test
asserting "stays ACTIVE, ER sent" is not the sole evidence for "emit ET".

**Promoted**: 2026-10-02 — Promoted — EMB-03-003 reworded (public awareness causes termination; a racing proposal is refused); markers owned by #4161.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4174>.
