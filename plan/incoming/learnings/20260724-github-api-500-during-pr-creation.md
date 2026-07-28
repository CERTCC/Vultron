---
title: "GitHub REST and GraphQL APIs returned HTTP 500 during PR creation (2026-07-24)"
type: learning
timestamp: "2026-07-24T19:52:00Z"
source: ISSUE-1686
signal: tooling-issue
---

Both `gh pr create` (GraphQL) and the REST `/repos/.../pulls` endpoint returned
HTTP 500 errors on 2026-07-24 around 19:20–19:52 UTC.  All other API calls
(branch lookup, compare, issue edit) succeeded normally.

Branch `task/1686-emit-accept-case-manager-role` is pushed and ready.  PR must
be opened manually at:
<https://github.com/CERTCC/Vultron/compare/main...task/1686-emit-accept-case-manager-role>
