---
source: NOTES-do-work-behaviors--prior-art-and-references-embargo-policy
timestamp: '2026-10-12T19:35:49.998148+00:00'
title: Prior Art and References (Embargo Policy), incl. VulnerabilityDisclosurePolicy
  future work
type: note
---

**Archived:** 2026-10-12
**Reason:** untracked deferral — the wrapper object is deferred until a CVD policy schema standard exists and no issue tracks it; the prior-art list is reference for that future design
**Superseded by:** `specs/embargo-policy.yaml` EP-01

---

## Prior Art and References (Embargo Policy)

The following prior work is relevant to a standardized embargo policy record:

- **RFC 9116** (security.txt): <https://www.rfc-editor.org/rfc/rfc9116>
  — defines a machine-readable file for security disclosure contact info;
  a natural companion to an embargo policy declaration
- **disclose.io DIOSTS**: <https://github.com/disclose/diosts/>
  — disclosure terms schema (vendor disclosure policies)
- **disclose.io DIOTerms**: <https://github.com/disclose/dioterms/>
  — core disclosure terms vocabulary
- **SSVC** (Stakeholder-Specific Vulnerability Categorization): used for
  prioritization decisions (`specs/prototype-shortcuts.yaml` PROTO-05-001);
  relevant to engage/defer decisions that precede embargo negotiation

### Future Work: VulnerabilityDisclosurePolicy Wrapper Object

The current `EmbargoPolicy` model (`specs/embargo-policy.yaml` EP-01) captures
embargo-specific preferences. The longer-term goal is a broader
`VulnerabilityDisclosurePolicy` object that contains `embargo_policy` as a
sub-field — analogous to the relationship between `security.txt` (contact
and scope metadata) and DIOSTS (disclosure terms schema).

Key design considerations:

- DIOSTS format is a likely candidate for the policy representation, but
  embargo-specific fields (min/max duration, preferences) require a custom
  extension to the standard DIOSTS schema
- A `VulnerabilityDisclosurePolicy` wrapper should be a JSON-LD extension
  under a Vultron namespace (e.g., `vultron:disclosurePolicy`) so that
  external ActivityPub clients can safely ignore or process the custom field
- The wrapper would sit in an actor's ActivityPub profile alongside the
  existing `embargo_policy` field currently provided by `as_VultronActorMixin`

**Design Decision**: Defer `VulnerabilityDisclosurePolicy` until there is a
formal CVD policy schema standard to align with. Track as a follow-on to EP-01
when a formal spec is drafted.

**Open Question**: (blocked-by EP-01 stabilization) Whether to extend DIOSTS
directly or define a new Vultron-specific schema. DIOSTS is the preferred
basis if Vultron aims for interoperability with the broader security community.

**Cross-reference**: `specs/embargo-policy.yaml` EP-01; `vultron/wire/as2/vocab/
objects/vultron_actor.py` (`as_VultronActorMixin.embargo_policy`).
