---
name: readability-audit
description: >
  Score docs/ pages for readability with textstat and rank the pages and topic
  clusters with the most sentences and paragraphs over the style guide's
  limits. Use when choosing which docs to revise in a Simplified Technical
  English (STE) or plain-language pass, or when checking a rewrite's
  before/after scores.
---

# Skill: Readability Audit

Finds where a revision pass buys the most readability. The script does the
scoring; you do the clustering and the recommendation.

Limits and scope come from
[`../shared/docs-style-guide.md`](../shared/docs-style-guide.md): SG-14
(sentences over 28 words) and SG-16 (paragraphs over five sentences), and its
Scope table (ADRs and generated pages are out). The script holds both as
constants; change them there when the guide changes.

## Run

From the repo root. `uvx` supplies textstat for the run only; it is not a
project dependency.

```bash
A=".agents/skills/readability-audit/readability_audit.py"
uvx --with 'textstat>=0.7.13,<0.8' python -I "$A"                 # whole docs/ tree
uvx --with 'textstat>=0.7.13,<0.8' python -I "$A" docs/howto/     # one subtree
uvx --with 'textstat>=0.7.13,<0.8' python -I "$A" --match 'embargo|/em/'
uvx --with 'textstat>=0.7.13,<0.8' python -I "$A" --baseline origin/main docs/topics/
```

Options: `--top N` (ranking rows, default 30), `--csv FILE` (every page
score), `--paths-out FILE` (ranked paths, one per line). Exit 1 means no
in-scope page matched.

## Workflow

### 1. Score

Run the whole tree unless the user named a scope. Keep the report output.

### 2. Cluster

Group the ranked pages by **topic**, not by directory: one concept often
spreads over `topics/`, `reference/`, `howto/` and the spec fragments. For each
candidate cluster, rerun with `--match` to collect its pages and total its
over-limit sentences.

Done when every page in the top 30 sits in a named cluster or is marked
standalone.

### 3. Qualify

Label each cluster's pages before you recommend:

- `reference/vultron-spec/_*.md`: **normative** spec text. A rewrite can change
  a requirement's meaning, so it needs a closer review.
- `draft-*.md`: unpublished draft (mkdocs `draft_docs`). Rank it lower.
- The report's "word choice" table: long words in short sentences. Most are
  domain terms that STE allows. Treat these pages as a vocabulary check, not
  a sentence-splitting job.

### 4. Present

Report, in this order:

1. Corpus totals and the share held by the top 10, 20 and 40 pages.
2. **Where we do well**: the best sections and pages.
3. **Where to improve**: clusters ranked by over-limit sentences, each with its
   pages, counts and labels from step 3.
4. A recommendation: the first cluster to revise, and why.

Quote one real over-limit sentence from the top cluster, so the reader sees
the problem is real prose. Offer to write a cluster's paths to `wip_outputs/`
with `--paths-out`.

## Reading the scores

- **Rank on the over-limit counts**, which map to SG-14 and SG-16 and count
  edits. Use the grade formulas (Flesch-Kincaid, Flesch Reading Ease) to
  support a finding, never as a limit. Domain terms put a floor under them:
  pages that had an STE pass still score about grade 9.
- **Spelling a term out raises the grade**, but it helps the reader. A
  rewrite that replaces symbols with words, defines terms or adds notes can
  score worse and still be better. In `--baseline` output, read
  over-limit counts first and grade second.
- Pages under 200 words count in the totals but are not ranked. Their formula
  scores are unstable.
- The script strips code, Mermaid, math, tables, HTML, include directives and
  link targets before scoring. A page that is mostly a table can score near
  zero.
- Lines hard-wrapped mid-sentence (an SG-38 break) are rejoined before
  counting, so a wrapped page scores the same as an unwrapped one.
