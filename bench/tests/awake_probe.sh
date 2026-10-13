#!/usr/bin/env bash
# Probe for scripts/run_awake.ps1 (run by hand, never by pytest): prints where it ran, which uv
# it found and a line with both quote kinds, then exits 7 so the launcher's exit code is visible.
out="${AWAKE_PROBE_OUT:-/tmp/awake_probe.txt}"
{
  echo "pwd=$(pwd)"
  echo "uv=$(command -v uv)"
  echo "quotes: \"double\" and 'single'"
  sleep 3
  echo done
} >"$out" 2>&1
exit 7
