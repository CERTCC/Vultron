#!/usr/bin/env bash
# verify-ci-gate.sh — pr-verify Phase 3: the CI gate. Waits for the PR's checks
# with wait-for-ci.sh and maps the result onto pr-verify's verdicts.
#
# Usage: verify-ci-gate.sh <pr-number> [--integration]
#   --integration  pass it when execute.integration_tests_run is true: the
#                  integration-bearing checks must then have passed, not been
#                  skipped or left out. They are every check whose name starts
#                  with VERIFY_CI_INTEGRATION_CHECK (default "Tests (pytest)",
#                  the python-app.yml job that runs `pytest -m ""`). That job
#                  is a matrix, so each part reports as its own check, named
#                  "Tests (pytest) <part>" — a prefix, not one exact name, or a
#                  split suite reads as absent and every PR is ci-failing.
#                  Every declared part must have reported, under its own name:
#                  a prefix match alone would read one green part out of four
#                  as a whole suite. VERIFY_CI_INTEGRATION_PARTS overrides how
#                  many to expect; by default it is the matrix legs the
#                  workflow declares.
#
# Rules:
#   wait-for-ci exit 1                         -> ci-failing
#   wait-for-ci exit 0, --integration, and no
#     integration check, fewer distinct part
#     names than declared, any of them not
#     `pass`, or no declared count at all      -> ci-failing
#   wait-for-ci exit 0                         -> ci-green
#   wait-for-ci exit 2 (timeout or gh error)   -> ci-pending
#
# Output, one `key=value` per line:
#   verdict=<ci-green|ci-failing|ci-pending>
#   wait_exit=<0|1|2>
#   failing_check=<name>  one per check in the fail or cancel bucket
#   integration=<pass|missing|incomplete|unknown-parts|<bucket>>
#     (--integration only)
#     `pass` only when every declared part reported and all passed;
#     `missing` when none matched the prefix; `incomplete` when fewer distinct
#     part names matched than the workflow declares; `unknown-parts` when no
#     part count could be derived at all; otherwise the first non-passing
#     bucket.
# Exit: 0 a verdict was printed; 2 usage error or jq missing.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_prefix="${VERIFY_CI_INTEGRATION_CHECK:-Tests (pytest)}"
# The matrix legs the workflow declares, one per `part:` key: the entry's
# first key, a later key, or flow style (`- {part: core, select: …}`). An
# over-count fails closed, as `incomplete`; an under-count would fail OPEN,
# reading one green part as a whole suite, so a count of zero is refused below
# rather than defaulted to one. `test/ci/test_python_app_test_parts.py` runs
# this same pattern against the workflow and pins the result to the matrix's
# length, so an edit that stops the pattern matching reds CI.
test_workflow="${VERIFY_CI_WORKFLOW:-${here}/../../../.github/workflows/python-app.yml}"
declared="$(grep -cE '(^|[[:space:]]|[{,])part:[[:space:]]' "${test_workflow}" 2>/dev/null)"
expected="${VERIFY_CI_INTEGRATION_PARTS:-${declared}}"

usage() { echo "usage: $0 <pr-number> [--integration]" >&2; exit 2; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage
pr="$1"
integration=false
if [ "$#" -eq 2 ]; then
  [ "$2" = "--integration" ] || usage
  integration=true
fi
command -v jq >/dev/null || { echo "verify-ci-gate: jq not found" >&2; exit 2; }

json="$(bash "${here}/wait-for-ci.sh" "${pr}")"; wait_exit=$?

case "${wait_exit}" in
  0) verdict=ci-green ;;
  1) verdict=ci-failing ;;
  *) verdict=ci-pending ;;
esac

bucket=""
if [ "${integration}" = true ] && [ "${wait_exit}" != 2 ]; then
  if ! [ "${expected}" -gt 0 ] 2>/dev/null; then
    # Nothing to compare against: the workflow moved, or its matrix no longer
    # writes `part:` the way the pattern above reads. Defaulting to 1 here
    # would admit one green part as the whole suite — the very failure the
    # count exists to refuse — so refuse, and name the override.
    bucket=unknown-parts
    echo "verify-ci-gate: no part count from ${test_workflow};" \
      "set VERIFY_CI_INTEGRATION_PARTS to override" >&2
  else
    # `.name // ""` and `.bucket // "unknown"`: a check with a null name would
    # make startswith() raise, and the raise would read as `missing` once
    # stderr is dropped — indistinguishable from "the test job never ran".
    # Distinct names, not array length: four reports of one part's name are
    # one part, not four, and would otherwise satisfy the count.
    bucket="$(printf '%s' "${json}" | jq -r \
      --arg n "${check_prefix}" --argjson want "${expected}" \
      '[.checks[]? | select((.name // "") | startswith($n))
        | {name: (.name // ""), bucket: (.bucket // "unknown")}]
       | if length == 0 then "missing"
         elif ([.[].name] | unique | length) < $want then "incomplete"
         elif all(.bucket == "pass") then "pass"
         else map(select(.bucket != "pass")) | first | .bucket end' \
      2>/dev/null)"
    bucket="${bucket:-missing}"
  fi
  [ "${bucket}" = pass ] || verdict=ci-failing
fi

echo "verdict=${verdict}"
echo "wait_exit=${wait_exit}"
printf '%s' "${json}" | jq -r '.checks[]? | select(.bucket | IN("fail","cancel")) | "failing_check=\(.name)"' 2>/dev/null
[ -z "${bucket}" ] || echo "integration=${bucket}"
exit 0
