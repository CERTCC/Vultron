#!/usr/bin/env bash
# verify-ci-gate.sh — pr-verify Phase 3: the CI gate. Waits for the PR's checks
# with wait-for-ci.sh and maps the result onto pr-verify's verdicts.
#
# Usage: verify-ci-gate.sh <pr-number> [--integration]
#   --integration  pass it when execute.integration_tests_run is true: the
#                  integration-bearing check must then have passed, not been
#                  skipped or left out. That check is VERIFY_CI_INTEGRATION_CHECK
#                  (default "Tests (pytest)", the python-app.yml job that runs
#                  `pytest -m ""`).
#
# Rules:
#   wait-for-ci exit 1                         -> ci-failing
#   wait-for-ci exit 0, --integration, and the
#     integration check absent or not `pass`   -> ci-failing
#   wait-for-ci exit 0                         -> ci-green
#   wait-for-ci exit 2 (timeout or gh error)   -> ci-pending
#
# Output, one `key=value` per line:
#   verdict=<ci-green|ci-failing|ci-pending>
#   wait_exit=<0|1|2>
#   failing_check=<name>  one per check in the fail or cancel bucket
#   integration=<pass|missing|<bucket>>  (--integration only)
# Exit: 0 a verdict was printed; 2 usage error or jq missing.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check_name="${VERIFY_CI_INTEGRATION_CHECK:-Tests (pytest)}"

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
  bucket="$(printf '%s' "${json}" | jq -r --arg n "${check_name}" \
    '[.checks[]? | select(.name == $n) | .bucket] | first // "missing"' 2>/dev/null)"
  bucket="${bucket:-missing}"
  [ "${bucket}" = pass ] || verdict=ci-failing
fi

echo "verdict=${verdict}"
echo "wait_exit=${wait_exit}"
printf '%s' "${json}" | jq -r '.checks[]? | select(.bucket | IN("fail","cancel")) | "failing_check=\(.name)"' 2>/dev/null
[ -z "${bucket}" ] || echo "integration=${bucket}"
exit 0
