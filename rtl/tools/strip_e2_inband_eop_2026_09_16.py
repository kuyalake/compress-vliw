#!/usr/bin/env python3
"""Convert the E2 (4-lane, max-4 schedule) model-pool streams from in-band
EOP to implicit EOP (2026-09-16 uniformity fix).

Before: each program's config region holds prog_len entries, the last being
        the in-band EOP marker 5'b11111 (config reads = sum(prog_len)).
After:  config holds prog_len-1 real entries per program; the hardware
        generates the final all-NOP + eop cycle from the prog_len counter
        (identical to the E1 / E2-5 / E2-3 / E2-2 convention).

The output cycle stream is unchanged (T cycles, last = all-NOP + eop), so
golden_issue4.txt and the tb emission checks are unaffected.  Rewrites in
place, per pool (BERT/SD-UNet/LLaMA):
  e2_config5.memh : drops the marker entry at cfg_base_p + prog_len_p - 1
  e2_meta.hex     : cfg_total -= n_prog; per-program cfg_base shifted down

Run from the repo root:  python3 rtl/tools/strip_e2_inband_eop_2026_09_16.py
"""
import pathlib
import sys

BASE = pathlib.Path("rtl/data_model_pools")
POOLS = ["BERT", "SD-UNet", "LLaMA"]
EOP_MARKER = 0x1F  # 5'b11111


def main() -> int:
    for pool in POOLS:
        meta_path = BASE / pool / "e2_meta.hex"
        cfg_path = BASE / pool / "e2_config5.memh"
        meta = [int(x, 16) for x in meta_path.read_text().split()]
        cfg = [int(x, 16) for x in cfg_path.read_text().split()]

        n_prog, cfg_total = meta[0], meta[1]
        assert len(cfg) == cfg_total, f"{pool}: config lines {len(cfg)} != cfg_total {cfg_total}"

        progs = []
        for p in range(n_prog):
            off = 6 + 6 * p
            progs.append((meta[off], meta[off + 1], meta[off + 2:off + 6]))

        # 1. verify every program's last config entry is the in-band marker
        drop = set()
        for p, (cfg_base, prog_len, _) in enumerate(progs):
            pos = cfg_base + prog_len - 1
            assert cfg[pos] == EOP_MARKER, (
                f"{pool}: prog {p} last config entry at {pos} is "
                f"{cfg[pos]:#05x}, expected {EOP_MARKER:#05x} (not in-band EOP data?)")
            drop.add(pos)

        # 2. strip markers; shift cfg_base down by the number of drops below it
        new_cfg = [w for i, w in enumerate(cfg) if i not in drop]
        new_total = cfg_total - n_prog
        assert len(new_cfg) == new_total

        new_meta = [n_prog, new_total] + meta[2:6]
        for cfg_base, prog_len, lane_bases in progs:
            new_base = cfg_base - sum(1 for d in drop if d < cfg_base)
            new_meta += [new_base, prog_len] + lane_bases

        cfg_path.write_text("".join(f"{w:x}\n" for w in new_cfg))
        meta_path.write_text("".join(f"{w:x}\n" for w in new_meta))
        print(f"{pool}: cfg_total {cfg_total} -> {new_total} "
              f"(-{n_prog} in-band EOP entries); prog_len unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
