# AGENTS.md — `vultron/core/behaviors/case/nodes/suggest_actor/`

Agent guidance for suggest-actor BT nodes in this package.

> For project-wide BT conventions see
> [`vultron/core/behaviors/AGENTS.md`](../../../AGENTS.md).

---

## The Case Owner's Answer Reads the Recorded Offer From the Blackboard

The Accept and Reject trees take only the answer's id. Their first precondition
guard, `RequireRecordedOfferAnswerNode`, looks up the recorded
`Offer(CaseParticipant)` and the recommendation behind it, and publishes a
`RecordedOfferAnswer` (recommender, invitee, roles) under
`recorded_offer_answer_{answer id segment}`. Every later node reads it through
`RecordedOfferAnswerInputMixin`.

- **Never resolve these ids in `execute()`.** A lookup there refuses before
  intake archives the answer and before the addressee door runs (CLP-10-005,
  CLP-10-018, HP-01-005; #4863).
- **A new answer-path node mixes in `RecordedOfferAnswerInputMixin`.** Taking
  the ids at construction needs them before the tree runs.
- **Roles come from the recorded Offer, never the Accept** (CM-16-019). An
  Offer that carries none seats no participant (CM-11-019).

**Blackboard key contrast**:

| Tree factory | Key written | Namespaced? |
|---|---|---|
| `create_recommend_actor_to_case_received_tree` | `suggested_roles_{id_segment}` | ✅ |
| `create_accept_actor_recommendation_received_tree` | `recorded_offer_answer_{id_segment}` | ✅ |
| `create_reject_actor_recommendation_received_tree` | `recorded_offer_answer_{id_segment}` | ✅ |
