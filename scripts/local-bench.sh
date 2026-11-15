#!/usr/bin/env bash
# GEX BENCH_SH contract for a dedicated local/disposable Linux build machine.
# No sync needed: all -s directories already exist on this machine.
set -euo pipefail
while [[ $# -gt 0 ]]; do
  case "$1" in
    -s)
      [[ $# -ge 2 && -d "$2" ]] || { echo 'local-bench: -s requires an existing directory' >&2; exit 2; }
      shift 2 ;;
    --) shift; [[ $# -gt 0 ]] || { echo 'local-bench: missing command' >&2; exit 2; }; exec "$@" ;;
    *) echo 'local-bench: expected -s DIR ... -- COMMAND' >&2; exit 2 ;;
  esac
done
echo 'local-bench: missing -- COMMAND' >&2
exit 2
