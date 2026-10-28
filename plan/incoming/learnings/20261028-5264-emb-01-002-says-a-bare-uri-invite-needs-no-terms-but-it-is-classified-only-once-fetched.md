---
title: EMB-01-002 says an Invite naming its terms by URI needs no terms for its ER, but under SE-01-006 it is classified only after the terms are fetched
type: learning
timestamp: 2026-10-28T15:30:00+00:00
source: ISSUE-5264
signal: spec-contradiction
---

**Trigger.** You read EMB-01-002 ("The ER names the Invite by id and needs no
terms, so an Invite that names its terms by URI only is answered too",
ADR-0123). Or you see a bare-URI `Invite(EmbargoEvent)` that is not answered
at once.

**Question for `learn`.** Under SE-01-006 a bare `object` matches no pattern's
object type. A receiver that does not hold the terms cannot tell an embargo
Invite from an actor Invite, so the activity is `UNKNOWN_UNRESOLVABLE_OBJECT`.
The inbox fetches the terms from the CASE_MANAGER (AKM-05-007) and replays the
Invite, and only then is the ER sent. If the fetch fails, no ER goes out
(AKM-05-015 dead-letters it). Should EMB-01-002 say the ER follows the fetch,
and that it is not sent when the terms cannot be fetched? Or should a bare
Invite with a case `context` be classified as an embargo Invite without its
terms, which needs a discriminator other than the object type?

**Evidence.** In PR #5318 (#5264), `test_a_bare_uri_invite_with_pxa_set_gets_an_er_once_its_terms_are_fetched`
in `test/core/use_cases/received/test_embargo_relay_replay.py` shows the
detour: the bare Invite names its terms to fetch, and the ER is sent only once
the receiver holds them. Before that PR the Invite was matched at once,
because a bare object was permissive.

**How to apply.** Until this is settled, expect a bare-URI embargo Invite to be
answered only after its terms are fetched. Do not loosen `object_` matching to
restore the immediate answer.
