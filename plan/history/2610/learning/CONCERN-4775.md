---
source: CONCERN-4775
timestamp: '2026-10-16T14:36:58.679621+00:00'
title: Received use cases compare the sender's raw actor id with ids stored canonically
type: learning
---

## Concern

A received activity's sender id (`request.actor_id`) reaches every received use case in the spelling the sender wrote. Nothing at the parse edge normalises it with `normalise_actor_id`. Many core lookups then compare it with stored ids by exact string match: `actor_participant_index.get(actor_id)` and `in` checks, and `case.attributed_to == actor_id`. Examples:

- `vultron/core/services/embargo_lifecycle/pec.py` (`find_actor_participant`, and the case-owner check near line 138)
- `vultron/core/behaviors/embargo/nodes/reject_proposed.py` (`attributed_to == rejecting_actor_id`)
- `vultron/core/behaviors/sender_entitlement.py` (`is_case_owner`)
- `vultron/core/use_cases/_helpers.py` (participant resolution by `participant_actor_id == actor_id`)

## Why it matters

Since #4772 (PR #4774), the case-proposal tree stores the proposer canonically: `attributed_to`, the CASE_OWNER participant key and the ledger snapshots hold the id without a trailing slash. Some actors spell their own id with a trailing slash in every message. After their case is created, their later messages (for example an embargo reject or a withdrawal) arrive in the slash spelling, and the exact comparisons above miss the canonical records. Before #4774, such a sender got its own spelling stored, so the exact comparisons matched.

Vultron-hosted actors are not affected. Their ids are `{base_url}/actors/{slug}` by construction (ADR-0073), and delivery strips the trailing slash (`http_delivery.py`). The gap applies to a peer that writes its id with a trailing slash. It also applies to an actor created through `POST /actors/` with a full-URI id that ends in `/`, because `canonical_actor_uri` returns such an id unchanged.

## Options

1. Normalise `actor_id` once at the inbound edge (the extractor, `vultron/wire/as2/extractor/_extract.py`), per ADR-0032. Then make the comparisons between the sender and ids in the payload tolerant (`same_actor_id`), because those ids keep the sender's spelling.
2. Keep raw sender ids, and change every sender-to-stored-id comparison to `same_actor_id` or `participant_id_for_actor` (`vultron/core/predicates/addressing.py`).

Option 1 gives one canonical spelling in every store. Option 2 leaves the stores with mixed spellings.

Related: CLP-10-021, OID-01-005, HP-09-001.

Where: vultron/wire/as2/extractor/_extract.py; vultron/core (exact actor-id comparisons)

**Resolved**: 2026-10-16 — implementation tracked in #4794, #4795.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4793>.

Spec: `specs/object-ids.yaml` (OID-01-006, OID-01-007).

Notes: `notes/case-proposal.md`.

Decisions: normalise the sender id at extraction and refuse an unnormalised one on the received event; file the received activity as received and normalise what is extracted from it; stores written in the slash spelling before the fix are unsupported; no ADR (applies ADR-0032 and ADR-0107).
