---
source: CONCERN-3443
timestamp: '2026-09-21T14:18:57.315232+00:00'
title: codebase-scan.txt tracked 16MB stale site mirror
type: learning
---

## Summary

`docs/reference/codebase/.codebase-scan.txt` is tracked, 16 MB, and `.gitignore`
line 154 already names `.codebase-scan.txt` — the ignore rule has no effect because
the file was committed before it was added.

Its contents include a dump of a built `site/search/search_index.json`, so it
carries a full stale mirror of the rendered documentation site, including pages
that no longer exist.

## Concrete cost

While taking an inbound-link census for #3003, a `git grep` over `docs notes specs`
reported 9 references to `docs/howto/activitypub/activities/transfer_ownership.md`
— a page that does not exist and has not for some time. All 9 were inside this
file. The same grep returned a 35 MB tool result that had to be discarded and
rerun with an exclusion.

This is the failure mode described in
`plan/incoming/learnings/20260918-3337-a-doc-rots-first-in-the-column-no-test-can-hold.md`:
an unratcheted artifact does not decay into silence, it decays into confident wrong
answers. Here it routes an agent to a nonexistent page with the same confidence as
a real reference.

## Root cause confirmed during planning

`scan.py` walks `cwd()` and does not list `site` in its `EXCLUDE_DIRS`, while
`json` is in its `SOURCE_EXTS`, so the built mkdocs search index is ingested.
`site/` is itself gitignored (`.gitignore:121`); the scan just ignores that.

## Resolution

Planned 2026-09-21 — implementation tracked in #3452 (blocked-by this Concern,
child of epic #607). The chosen approach (confirmed with the maintainer):
`git rm --cached` the blob so the existing ignore takes effect (Option 1);
additionally add `site` to `scan.py`'s `EXCLUDE_DIRS` so the regenerated
artifact stops mirroring the built site; and add a ratchet test that fails if
the file is tracked again (per the #3337 learning — ratchet the ratchetable in
the same PR). No spec/notes/ADR changes: the fix is self-documenting via code
and test, and the governing principle already lives in the #3337 learning.
