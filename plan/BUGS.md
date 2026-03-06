# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---
## Markdown Linting Errors

Run DavidAnson/markdownlint-cli2-action@v22
markdownlint-cli2 v0.20.0 (markdownlint v0.40.0)
Finding: notes/bt-fuzzer-nodes.md notes/encryption.md notes/triggerable-behaviors.md prompts/LEARN_EXTRA_prompt.md specs/triggerable-behaviors.md AGENTS.md notes/README.md notes/activitystreams-semantics.md notes/bt-integration.md notes/case-state-model.md notes/codebase-structure.md notes/do-work-behaviors.md notes/domain-model-separation.md plan/BUGS.md plan/IDEAS.md plan/IMPLEMENTATION_NOTES.md plan/IMPLEMENTATION_PLAN.md plan/PRIORITIES.md prompts/PLAN_prompt.md specs/README.md specs/case-management.md specs/code-style.md specs/demo-cli.md specs/embargo-policy.md specs/encryption.md specs/meta-specifications.md specs/object-ids.md specs/project-documentation.md specs/tech-stack.md !plan/** !specs/** !wip_notes/** !AGENTS.md !node_modules/**
Linting: 12 file(s)
Summary: 45 error(s)
Error: notes/bt-integration.md:213:70 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: notes/encryption.md:4 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- ActivityPub supports public-..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:11 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- Prefer standard mechanisms (..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:20 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- Decryption should occur upst..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:34 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- Per-recipient messages (reco..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:50 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- Read public keys from the re..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:60 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- Store private keys securely ..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:72 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- Do we accept the extra netwo..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:80 MD032/blanks-around-lists Lists should be surrounded by blank lines [Context: "- ActivityPub actor publicKey:..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md032.md
Error: notes/encryption.md:80:32 MD034/no-bare-urls Bare URL used [Context: "https://docs.joinmastodon.org/..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md034.md
Error: notes/encryption.md:81:40 MD034/no-bare-urls Bare URL used [Context: "https://docs.joinmastodon.org/..."] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md034.md
Error: prompts/LEARN_EXTRA_prompt.md:29:85 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* o"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:30:115 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* o"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:36:1 MD029/ol-prefix Ordered list item prefix [Expected: 1; Actual: 9; Style: 1/1/1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:37:18 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* a"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:39:71 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:45:78 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:46:80 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:47:32 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* a"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:48:64 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:49:72 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* o"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:50:79 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:51:62 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* o"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:52:76 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:58:71 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:58:1 MD029/ol-prefix Ordered list item prefix [Expected: 1; Actual: 10; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:60:73 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:62:1 MD029/ol-prefix Ordered list item prefix [Expected: 2; Actual: 11; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:62:19 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* t"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:68:1 MD029/ol-prefix Ordered list item prefix [Expected: 3; Actual: 12; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:68:19 MD037/no-space-in-emphasis Spaces inside emphasis markers [Context: "* t"] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md037.md
Error: prompts/LEARN_EXTRA_prompt.md:70:68 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:72:75 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:74:73 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:75:71 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:76:71 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/LEARN_EXTRA_prompt.md:80:1 MD029/ol-prefix Ordered list item prefix [Expected: 4; Actual: 13; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:85:1 MD029/ol-prefix Ordered list item prefix [Expected: 1; Actual: 13; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:97:1 MD029/ol-prefix Ordered list item prefix [Expected: 2; Actual: 14; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:105:1 MD029/ol-prefix Ordered list item prefix [Expected: 3; Actual: 15; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:109:1 MD029/ol-prefix Ordered list item prefix [Expected: 4; Actual: 16; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:113:1 MD029/ol-prefix Ordered list item prefix [Expected: 1; Actual: 17; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/LEARN_EXTRA_prompt.md:118:1 MD029/ol-prefix Ordered list item prefix [Expected: 2; Actual: 18; Style: 1/2/3] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md029.md
Error: prompts/PLAN_prompt.md:32:51 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: prompts/PLAN_prompt.md:34:75 MD009/no-trailing-spaces Trailing spaces [Expected: 0 or 2; Actual: 1] https://github.com/DavidAnson/markdownlint/blob/v0.40.0/doc/md009.md
Error: Failed with exit code: 1
