---
title: git push blocked by credential helper pointing at nonexistent /usr/local/bin/gh
type: learning
timestamp: 2026-08-11
source: ISSUE-2186
signal: tooling-issue
---

Pushing the fix branch for #2186/#2180 failed before the PR could be opened:

```text
/usr/local/bin/gh auth git-credential get: 1: /usr/local/bin/gh: not found
fatal: could not read Username for 'https://github.com'
```

Root cause: the git config sets
`credential.https://github.com.helper = !/usr/local/bin/gh auth git-credential`,
but in this environment `gh` lives at `/usr/bin/gh` — the configured path does
not exist. The obvious repair (`gh auth setup-git`) also failed:

```text
failed to set up git credential helper: failed to run git:
error: could not write config file /home/vscode/.gitconfig: Device or resource busy
```

so the global gitconfig cannot be rewritten (the file is bind-mounted /
locked). `GH_TOKEN` *is* present in the environment.

**Workaround that unblocked the push** — override the helper for a single
command using the correct `gh` path, without touching `~/.gitconfig`:

```bash
git -c credential.https://github.com.helper='!/usr/bin/gh auth git-credential' \
    push -u origin <branch>
```

(An inline token helper — `echo password=$GH_TOKEN` — or an
`https://x-access-token:$GH_TOKEN@github.com/...` URL are equivalent fallbacks.)

**How to apply:** when a `git push`/`gh` operation fails with
`/usr/local/bin/gh: not found`, do not try to `gh auth setup-git` (the
gitconfig is read-only here). Instead pass a one-shot `-c
credential.https://github.com.helper='!/usr/bin/gh auth git-credential'`
override on the push command. This is distinct from
`20260811-create-pr-cannot-target-integration-branch.md` (which is about the
create-pr skill hardcoding `--base main`); both had to be worked around in the
same session.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: git credential helper may point at nonexistent gh path.
Docs PR: TBD.
