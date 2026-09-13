#!/usr/bin/env bash
# Build a minimal no-space Icarus Verilog runtime at /tmp/ivl.
#
# Why: the bundled oss-cad-suite lives under ".../work at school/..." (a path
# with a space).  Its bin/iverilog and bin/vvp are *shell wrappers* whose
# driver shells out to ivlpp/ivl with an unquoted path, so they fail with
#   sh: /Users/maghu/Desktop/work: No such file or directory
# This script copies the minimal compiled binaries + runtime libs to the
# no-space path /tmp/ivl and points the run scripts at it.
#
# Usage:  bash rtl/sim/setup_iverilog_nospace.sh
# Then:   IVERILOG=/tmp/ivl/libexec/iverilog VVP=/tmp/ivl/libexec/vvp \
#           bash rtl/sim/run_e2_five_lane_pool.sh all
set -euo pipefail

OSS="$(cd "$(dirname "$0")/../../.." && pwd)/../.tools/oss-cad-suite"
OSS="$(cd "$(dirname "$0")" && pwd)"  # placeholder, recomputed below
# locate the oss-cad-suite relative to the repo (../../.tools/oss-cad-suite)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"   # compress-vliw/
OSS="$(dirname "$REPO_DIR")/.tools/oss-cad-suite"

if [ ! -d "$OSS/libexec" ]; then
    echo "ERROR: oss-cad-suite not found at $OSS" >&2
    exit 1
fi

rm -rf /tmp/ivl
mkdir -p /tmp/ivl/libexec /tmp/ivl/lib
cp "$OSS/libexec/iverilog" "$OSS/libexec/ivlpp" "$OSS/libexec/ivl" \
   "$OSS/libexec/vvp" "$OSS/libexec/realpath" /tmp/ivl/libexec/
cp -r "$OSS/lib/ivl" /tmp/ivl/lib/
cp "$OSS"/lib/*.dylib /tmp/ivl/lib/

# smoke test
printf 'module t; initial begin $display("ok"); $finish; end endmodule\n' \
    > /tmp/ivl_smoke.v
/tmp/ivl/libexec/iverilog -o /tmp/ivl_smoke.vvp /tmp/ivl_smoke.v
/tmp/ivl/libexec/vvp /tmp/ivl_smoke.vvp | grep -q "ok"
rm -f /tmp/ivl_smoke.v /tmp/ivl_smoke.vvp
echo "[setup] no-space iverilog runtime ready at /tmp/ivl"
echo "[setup] use: IVERILOG=/tmp/ivl/libexec/iverilog VVP=/tmp/ivl/libexec/vvp ..."
