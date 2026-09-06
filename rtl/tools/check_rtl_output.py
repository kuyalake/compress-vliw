#!/usr/bin/env python3
"""Compare an RTL simulation output against a golden reference (rtl/plan.md 6.2).

Both files use one line per accepted cycle:
    "<load> <store> <vector> <scalar> <sfu> <eop>"
with five 9-hex-digit 34-bit containers and a 1-hex eop bit.

The golden already encodes the low-toggle hold semantics (invalid slot =
last valid container with its OP field zeroed), so the comparison is an
exact per-cycle, per-bit check -- including that invalid cycles never rewrite
non-OP fields.

Usage:
    python3 check_rtl_output.py --rtl rtl_out.txt --golden golden_issue5.txt
                                 [--case softmax_x64] [--verbose N]

Pool mode (program-pool runs, plan.md 6.2): the RTL file contains one segment
per program, separated by "# prog <k>" marker lines:
    python3 check_rtl_output.py --pool --rtl rtl_out_e0_pool.txt \
        --map rtl/data/e0_pool_map.txt --data rtl/data [--raw]
The map file lists "<pos> <case>" per line; segment k is compared against
<data>/<case>/golden_issue5.txt (or golden_raw_issue5.txt with --raw).

Exit code 0 on match, 1 on any mismatch.
"""

import argparse
import sys

SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")


def load_trace(path):
    rows = []
    with open(path) as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 6:
                raise ValueError("%s:%d: expected 6 fields, got %d"
                                 % (path, lineno, len(parts)))
            try:
                row = [int(p, 16) for p in parts]
            except ValueError:
                raise ValueError("%s:%d: bad hex field" % (path, lineno))
            for s in range(5):
                if row[s] >> 34:
                    raise ValueError("%s:%d: slot %s exceeds 34 bits"
                                     % (path, lineno, SLOT_NAMES[s]))
            if row[5] not in (0, 1):
                raise ValueError("%s:%d: eop must be 0/1" % (path, lineno))
            rows.append(row)
    return rows


def compare_one(rtl_rows, golden_rows, tag, verbose):
    """Compare one segment; returns the number of field mismatches."""
    if verbose:
        for i in range(min(verbose, len(rtl_rows), len(golden_rows))):
            print("cycle %d" % i)
            print("  rtl    : %s" % " ".join("%09x" % c for c in rtl_rows[i][:5])
                  + " %d" % rtl_rows[i][5])
            print("  golden : %s" % " ".join("%09x" % c for c in golden_rows[i][:5])
                  + " %d" % golden_rows[i][5])

    errors = 0
    if len(rtl_rows) != len(golden_rows):
        print("%sFAIL: cycle count mismatch: rtl=%d golden=%d"
              % (tag, len(rtl_rows), len(golden_rows)))
        errors += 1

    first_bad = None
    for i in range(min(len(rtl_rows), len(golden_rows))):
        r, g = rtl_rows[i], golden_rows[i]
        for s in range(5):
            if r[s] != g[s]:
                if first_bad is None:
                    first_bad = (i, SLOT_NAMES[s], g[s], r[s])
                errors += 1
        if r[5] != g[5]:
            if first_bad is None:
                first_bad = (i, "eop", g[5], r[5])
            errors += 1

    if first_bad is not None:
        i, slot, exp, got = first_bad
        print("%sFAIL: first mismatch at cycle %d slot %s: expected %09x, got %09x"
              % (tag, i, slot, exp, got))

    # EOP discipline: exactly the last golden cycle has eop=1
    if golden_rows:
        for i, row in enumerate(golden_rows):
            want = 1 if i == len(golden_rows) - 1 else 0
            if row[5] != want:
                print("%sFAIL: golden eop violation at cycle %d" % (tag, i))
                errors += 1
                break
        if rtl_rows and len(rtl_rows) >= len(golden_rows) \
                and rtl_rows[len(golden_rows) - 1][5] != 1:
            print("%sFAIL: RTL did not assert eop on the last cycle" % tag)
            errors += 1

    if errors == 0:
        print("%sPASS: %d cycles bit-exact (hold semantics verified)"
              % (tag, len(golden_rows)))
    else:
        print("%sFAIL: %d field mismatches" % (tag, errors))
    return errors


def split_pool_segments(path):
    """Split a pooled RTL output into {position: rows} on '# prog <k>' markers."""
    segments = {}
    current = None
    with open(path) as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                parts = line[1:].split()
                if len(parts) == 2 and parts[0] == "prog":
                    current = int(parts[1])
                    segments[current] = []
                # other comments (e.g. error markers) are ignored here;
                # they will fail parsing inside a segment if fatal
                continue
            if current is None:
                raise ValueError("%s:%d: data before any '# prog' marker"
                                 % (path, lineno))
            parts = line.split()
            if len(parts) != 6:
                raise ValueError("%s:%d: expected 6 fields, got %d"
                                 % (path, lineno, len(parts)))
            segments[current].append([int(p, 16) for p in parts])
    return segments


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", required=True, help="RTL output trace")
    ap.add_argument("--golden", help="golden reference trace (single mode)")
    ap.add_argument("--case", default="", help="case name (for messages)")
    ap.add_argument("--verbose", type=int, default=0,
                    help="print the first N cycles side by side")
    ap.add_argument("--pool", action="store_true",
                    help="pool mode: split --rtl on '# prog' markers")
    ap.add_argument("--map", help="pool map file (<pos> <case> per line)")
    ap.add_argument("--data", help="data root dir (pool mode)")
    ap.add_argument("--raw", action="store_true",
                    help="pool mode: compare against golden_raw_issue5.txt")
    ap.add_argument("--golden-name",
                    help="pool mode: golden file name per case "
                         "(default golden_issue5.txt; --raw overrides)")
    args = ap.parse_args()

    if args.pool:
        return main_pool(args)

    tag = ("[%s] " % args.case) if args.case else ""

    if not args.golden:
        print("%sFAIL: --golden is required in single-trace mode" % tag)
        return 1
    try:
        rtl = load_trace(args.rtl)
        golden = load_trace(args.golden)
    except (OSError, ValueError) as exc:
        print("%sFAIL: %s" % (tag, exc))
        return 1

    return 0 if compare_one(rtl, golden, tag, args.verbose) == 0 else 1


def main_pool(args):
    if not args.map or not args.data:
        print("FAIL: --pool requires --map and --data")
        return 1

    # map file: "<pos> <case>" per line
    pos_to_case = {}
    try:
        with open(args.map) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pos_s, case = line.split()
                pos_to_case[int(pos_s)] = case
    except (OSError, ValueError) as exc:
        print("FAIL: cannot read pool map: %s" % exc)
        return 1

    try:
        segments = split_pool_segments(args.rtl)
    except (OSError, ValueError) as exc:
        print("FAIL: %s" % exc)
        return 1

    if args.raw:
        golden_name = "golden_raw_issue5.txt"
    elif args.golden_name:
        golden_name = args.golden_name
    else:
        golden_name = "golden_issue5.txt"
    total_errors = 0
    for pos in sorted(pos_to_case):
        case = pos_to_case[pos]
        tag = "[pool:%s] " % case
        if pos not in segments:
            print("%sFAIL: no output segment for run position %d" % (tag, pos))
            total_errors += 1
            continue
        try:
            golden = load_trace(
                __import__("pathlib").Path(args.data) / case / golden_name)
        except (OSError, ValueError) as exc:
            print("%sFAIL: %s" % (tag, exc))
            total_errors += 1
            continue
        total_errors += compare_one(segments[pos], golden, tag, args.verbose)

    extra = set(segments) - set(pos_to_case)
    if extra:
        print("[pool] FAIL: unexpected segments at positions %s"
              % sorted(extra))
        total_errors += 1

    if total_errors == 0:
        print("[pool] PASS: all %d programs bit-exact" % len(pos_to_case))
        return 0
    print("[pool] FAIL: %d errors total" % total_errors)
    return 1


if __name__ == "__main__":
    sys.exit(main())
