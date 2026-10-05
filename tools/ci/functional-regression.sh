#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mode="${1:-all}"

python3 tools/ci/functional-regression.py --validate

case "$mode" in
  all)
    python3 tools/ci/functional-regression.py all
    ;;
  full)
    python3 tools/ci/functional-regression.py all
    bash tools/ci/run-tests.sh integration
    ;;
  *)
    python3 tools/ci/functional-regression.py "$mode"
    ;;
esac
