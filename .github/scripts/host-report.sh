#!/usr/bin/env bash
# Print host details to the log and the job summary, including whether /dev/kvm exists.
# That answers whether hosted runners could run guests with hardware acceleration.
set -euo pipefail

summary=${GITHUB_STEP_SUMMARY:-/dev/null}

{
  echo "## Host report"
  echo
  echo "- Kernel: \`$(uname -srm)\`"
  if [[ -e /dev/kvm ]]; then
    echo "- /dev/kvm: **present** (\`$(ls -l /dev/kvm)\`)"
  else
    echo "- /dev/kvm: **absent**"
  fi
  for tool in qemu-system-aarch64 qemu-system-x86_64 shellcheck actionlint jq; do
    if command -v "$tool" >/dev/null 2>&1; then
      echo "- $tool: \`$("$tool" --version 2>&1 | head -n 1)\`"
    else
      echo "- $tool: not installed"
    fi
  done
} | tee -a "$summary"
