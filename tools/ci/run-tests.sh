#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

export PYTHONPATH="$REPO_ROOT:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
mode="${1:-deterministic}"

case "$mode" in
  deterministic)
    timeout 600s uv run --frozen --with-requirements webadmin/requirements.txt pytest -q -m "not integration" tests
    ;;
  integration)
    ok=0
    for attempt in 1 2 3; do
      echo "Integration attempt $attempt/3"
      if timeout 300s uv run --frozen --with-requirements webadmin/requirements.txt pytest -q -m integration tests; then
        ok=1
        break
      fi
      [ "$attempt" -eq 3 ] || sleep $((attempt * 10))
    done
    test "$ok" -eq 1
    ;;
  all)
    "$0" deterministic
    "$0" integration
    ;;
  *)
    echo "Usage: $0 {deterministic|integration|all}" >&2
    exit 2
    ;;
esac
