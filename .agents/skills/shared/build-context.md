# Build Context Hand-Forward

`build` and `bugfix` load task context with `orient-agent` and `deepen-context`.
Each later pr-ship phase (the pre-push reviewer, `pr-triage`, `pr-execute`) is a
fresh agent that would load it again. The build context file lists what was
loaded, so a later phase loads exactly that list instead of re-deriving it
(PAD-07-015 to PAD-07-019). The `build-context` console script writes and checks
it; its module docstring is the reference for the file's fields.

The file holds **facts found, never the author's reasoning**: the branch, the
head and base commits, the Spec manifest's loaded IDs, the domain hints, and the
notes and glossary sections read. A reviewer that loads it still reviews with a
fresh eye (PAD-07-001). The tool refuses any other field.

## Writing it (`build` Phase 3, `bugfix` Phase 2g)

Right after `deepen-context` returns, before the branch's first commit, save the
Spec manifest to `/tmp/spec-manifest-<N>.txt` and run:

```bash
PYTHONPATH= uv run build-context write --manifest /tmp/spec-manifest-<N>.txt \
  --hint "<hint>" [--hint "<hint>" ...] \
  [--note notes/<file>.md ...] [--glossary "<glossary section title>" ...]
```

Pass every focus hint, every `notes/` file and every glossary section that
`deepen-context` read. Exit 2 names a bad input (a note or section that does not
exist, a manifest with no loaded ID): fix the argument and re-run. Write it before
the first commit: `create-pr` cherry-picks the branch onto a newer base, which
keeps the recorded base commit an ancestor of the PR head but not a branch
commit, so a file written later reads as stale.

## Reading it (pr-ship phases)

```bash
PYTHONPATH= uv run build-context check
```

Run it on the PR branch (or, before the push, the task branch).

- **Exit 0, `mode=reuse`** — skip `orient-agent`; read
  `.agents/skills/shared/completeness-doctrine.md`, which triage severity rests
  on. Then load exactly what the file lists:
  - `spec-dump --ids <spec_ids> --deps --text`, `spec-dump --group <spec_groups>
    --text` and `spec-dump --topic <spec_topics> --text`, skipping an empty list;
  - each `note=` file;
  - each `glossary=` section of `docs/reference/glossary.md`, located with
    `PYTHONPATH= uv run glossary-index`.

  Then add what the file cannot know. Run `deepen-context` with only the hints
  for the changed-path domains that no `hint=` line covers. Load any spec ID in
  the PR body's (or draft body's) Spec manifest that the file does not list. The
  manifest can grow after the file is written.
- **Exit 3, `mode=fallback`**, or exit 2 — load context exactly as the phase
  does with no file: `orient-agent`, then `deepen-context`. Record the `reason=`
  line. `pr-triage` names it in its comment header (PAD-07-019). Exit 2 (detached
  checkout, not in a work tree) falls back the same way, with the error as the
  reason.

The file is an optimization, never a precondition. No phase fails, skips a
check, or narrows a check because the file is missing or unusable (PAD-07-018).
pr-ship often runs from another agent system or machine that has no copy of the
file, and that is the ordinary path.

`pr-verify` loads no task context. It uses the file only to delete it, at the
path `build-context path --branch <head_ref>` prints, in its cleanup.
