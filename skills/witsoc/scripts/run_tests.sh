#!/usr/bin/env bash
# R8: the witsoc test runner. Runs every self-checking test file in isolation
# (WITSOC_CORE_ONLY: no Mathlib auto-enable, no network probes) and reports
# one line per failure plus a summary. Exit 1 on any failure.
set -u
cd "$(dirname "$0")"
export WITSOC_CORE_ONLY=1
unset WITSOC_SAMPLER_FLEET WITSOC_IDEATION_SAMPLER WITSOC_NOVELTY_CMD 2>/dev/null

fails=0
total=0
for t in test_*.py; do
  [ "$t" = "test_fixtures.py" ] && continue   # shared builders, not a test file
  total=$((total + 1))
  if ! out=$(timeout "${WITSOC_TEST_TIMEOUT:-480}" python3 "$t" 2>&1); then
    fails=$((fails + 1))
    echo "FAIL: $t"
    echo "$out" | tail -8
  fi
done
echo "=== $fails failed of $total test files ==="
exit $((fails > 0))
