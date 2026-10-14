---
source: NOTES-site-information-architecture--sub-section-index-decisions
timestamp: '2026-10-14T14:26:59.825855+00:00'
title: 'site-information-architecture: sub-section index decisions'
type: note
---

Archived from `notes/site-information-architecture.md` by #4498: the per-index decisions of #3617 are delivered. Each index now declares its shape in `contents:` frontmatter and `test/metadata/docs/test_site_sync.py::test_committed_generated_pages_are_the_decided_set` pins the decided sets; the rule for deciding a new index stays in the note's § "Landing pages are generated, never hand-maintained".

---

## Sub-section index decisions

One row per `index.md` the nav carries, decided in #3617 against the nav
shape that #3627 left. The decision is machine-readable on the page
(`contents:`); this table carries the reason.
`test_committed_generated_pages_are_the_decided_set` pins the three sets, so a
new group index is decided here before it lands.

| Index | Decision | Why |
|---|---|---|
| `tutorials/`, `topics/`, `howto/`, `reference/`, `research/` | generated | The five top-level landings from #3527, now declaring the shape they always had. |
| `topics/background/index.md` | generated | A plain enumeration in dependency order; the blurbs moved to each child's `description:`. |
| `topics/case_lifecycle/index.md` | generated | Was a grid of cards; the icons were decoration and the blurbs moved to `description:`. |
| `topics/process_models/index.md` | routing | Routes its four sub-groups through a diagram-per-model argument; a list would repeat what each H2 already does. |
| `topics/process_models/rm/index.md` | generated | A content page with an index filename (audit `extract` verdict, applied in part by #3680); its "In this section" list is generated so both sibling pages are always reached. |
| `topics/process_models/em/index.md` | generated | The "In this section" list is generated; the "Doing it on the wire" pointers into How-to stay hand-written. |
| `topics/process_models/cs/index.md` | generated | The table became the listing; the limits page sits in Research (#3627) and is linked from the framing. |
| `topics/process_models/model_interactions/index.md` | generated | Two bullets became the listing. |
| `topics/behavior_logic/index.md` | routing | Its "three views" table routes the notation page and the use-case group as part of an argument that also reaches the working record. |
| `topics/behavior_logic/use-cases/index.md` | generated | The trigger-name column folded into each child's `description:`. |
| `topics/scenarios/index.md` | rendered | Table rendered at build time from the scenario registry (DEMOCI-11-009); the leaves stay in the nav (DEMOCI-11-007). |
| `topics/future_work/index.md` | generated | Two cards became the listing. |
| `howto/activitypub/index.md` | routing | A content page on the AS2 grammar whose closing cards route its one child beside two reference pages. |
| `howto/activitypub/activities/index.md` | routing | The themed grouping (report and case, participants and roles, embargoes and faults) is editorial; the leaves are out of the nav (DF-11-006, #3627), so the sibling rule holds the page to all thirteen. |
| `reference/iso_crosswalks/index.md` | generated | The table became the listing; each crosswalk links the standard it maps, so the external links were redundant. |
| `reference/formal_protocol/index.md` | generated | Bullets became the listing; the set-notation in the blurbs became prose in `description:`. |
| `reference/messages/index.md` | generated | The shorthand codes each page covers folded into its `description:`. |
| `reference/specs/index.md` | routing | Routes every tier, two of which (`project.md`, `process.md`) are working record the nav omits (DF-11-003); a nav-derived listing would drop them. |
| `reference/vultron-spec/index.md` | routing | The Protocol Specification's landing page (#4059): its framing routes the six body pages, the seven annex pages, Open Questions and the hidden all-in-one `full.md`, which the nav omits (`notes/rfc-spec-authoring.md` § "Page Map"); a nav-derived listing would drop `full.md`. |
| `start/index.md` | routing | Opens *Start Here*; its four situation cards come from `includes/start_here_cards.md`, the same fragment the home page's "Where to start" uses, and `routing_faults` counts a whole-included fragment's links (DF-10-002). |
| `topics/measuring_cvd/index.md` | generated | The table became the listing; the reading-order sentence stays as framing. |
| `topics/other_uses/index.md` | generated | As above. |

Three `index.md` files the nav carries are not section indexes and declare
nothing: `topics/capability_model/index.md` is a content page whose directory
holds no other page; `reference/user_stories/index.md` routes the stories through
an included table, and the stories themselves are working record reached from
`traceability.md`; `docs/index.md` is the front door (#3524). A leaf
`index.md` becomes a section index the moment its directory gains a reader page
the nav omits — the generator then requires it to declare `routing` and link the
page.
