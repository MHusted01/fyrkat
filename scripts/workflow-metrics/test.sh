#!/usr/bin/env bash
# Run the tests for the workflow metric scripts. Needs python3.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$here"
python3 -B test_audit.py
