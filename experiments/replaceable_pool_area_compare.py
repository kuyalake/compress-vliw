#!/usr/bin/env python3
"""Area comparison for the fixed three-function replaceable instruction pool."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "experiments" / "issue2_equal34_sram_compare.py"
OUTPUT_PATH = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "replaceable_pool_area_compare.json"
)

CONFIG_WIDTH = 5
CONFIG_DEPTH = 8192
PAYLOAD_WIDTH = 34
A_BANKS = 5
A_BANK_DEPTH = 2048
A_COMPACT_BANK_DEPTHS = (2048, 2048, 2048, 1024, 2048)
A_COMPACT_EVENT_READS = (1094, 1088, 1856, 640, 1088)
B_BANKS = 2
B_BANK_DEPTH = 4096
DEPTH_AWARE_LANE_DEPTHS = (4096, 2048)
DEPTH_AWARE_LANE_READS = (4026, 1740)
PAYLOAD_EVENT_READS = 5766
A_CONFIG_READS = 5453
B_CONFIG_READS = 5475


def load_helper() -> Any:
    spec = importlib.util.spec_from_file_location("cacti_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cacti-root", type=Path, required=True)
    args = parser.parse_args()
    cacti_root = args.cacti_root.resolve()
    helper = load_helper()
    template = (cacti_root / "cache.cfg").read_text()

    config_macro = helper.run_macro(
        cacti_root, template, CONFIG_WIDTH, CONFIG_DEPTH
    )
    a_payload_macro = helper.run_macro(
        cacti_root, template, PAYLOAD_WIDTH, A_BANK_DEPTH
    )
    a_compact_scalar_macro = helper.run_macro(
        cacti_root, template, PAYLOAD_WIDTH, 1024
    )
    b_payload_macro = helper.run_macro(
        cacti_root, template, PAYLOAD_WIDTH, B_BANK_DEPTH
    )

    candidate_a = {
        "organization": {
            "config": [CONFIG_WIDTH, CONFIG_DEPTH, 1],
            "payload": [PAYLOAD_WIDTH, A_BANK_DEPTH, A_BANKS],
        },
        "logical_bits": (
            CONFIG_WIDTH * CONFIG_DEPTH
            + A_BANKS * PAYLOAD_WIDTH * A_BANK_DEPTH
        ),
        "allocated_bits": (
            config_macro["allocated_bits"]
            + A_BANKS * a_payload_macro["allocated_bits"]
        ),
        "sram_area_mm2": (
            config_macro["area_mm2"]
            + A_BANKS * a_payload_macro["area_mm2"]
        ),
        "sram_leakage_mw": (
            config_macro["leakage_mw"]
            + A_BANKS * a_payload_macro["leakage_mw"]
        ),
        "payload_read_energy_nj": a_payload_macro["read_energy_nj"],
        "config_read_energy_nj": config_macro["read_energy_nj"],
        "macro_count": 1 + A_BANKS,
    }
    candidate_a_compact = {
        "organization": {
            "config": [CONFIG_WIDTH, CONFIG_DEPTH, 1],
            "payload_depths": list(A_COMPACT_BANK_DEPTHS),
        },
        "logical_bits": (
            CONFIG_WIDTH * CONFIG_DEPTH
            + PAYLOAD_WIDTH * sum(A_COMPACT_BANK_DEPTHS)
        ),
        "allocated_bits": (
            config_macro["allocated_bits"]
            + 4 * a_payload_macro["allocated_bits"]
            + a_compact_scalar_macro["allocated_bits"]
        ),
        "sram_area_mm2": (
            config_macro["area_mm2"]
            + 4 * a_payload_macro["area_mm2"]
            + a_compact_scalar_macro["area_mm2"]
        ),
        "sram_leakage_mw": (
            config_macro["leakage_mw"]
            + 4 * a_payload_macro["leakage_mw"]
            + a_compact_scalar_macro["leakage_mw"]
        ),
        "macro_count": 6,
    }
    issue2 = {
        "organization": {
            "config": [CONFIG_WIDTH, CONFIG_DEPTH, 1],
            "payload": [PAYLOAD_WIDTH, B_BANK_DEPTH, B_BANKS],
        },
        "logical_bits": (
            CONFIG_WIDTH * CONFIG_DEPTH
            + B_BANKS * PAYLOAD_WIDTH * B_BANK_DEPTH
        ),
        "allocated_bits": (
            config_macro["allocated_bits"]
            + B_BANKS * b_payload_macro["allocated_bits"]
        ),
        "sram_area_mm2": (
            config_macro["area_mm2"]
            + B_BANKS * b_payload_macro["area_mm2"]
        ),
        "sram_leakage_mw": (
            config_macro["leakage_mw"]
            + B_BANKS * b_payload_macro["leakage_mw"]
        ),
        "payload_read_energy_nj": b_payload_macro["read_energy_nj"],
        "config_read_energy_nj": config_macro["read_energy_nj"],
        "macro_count": 1 + B_BANKS,
    }
    issue2_depth_aware = {
        "organization": {
            "config": [CONFIG_WIDTH, CONFIG_DEPTH, 1],
            "payload": [
                [PAYLOAD_WIDTH, DEPTH_AWARE_LANE_DEPTHS[0], 1],
                [PAYLOAD_WIDTH, DEPTH_AWARE_LANE_DEPTHS[1], 1],
            ],
        },
        "logical_bits": (
            CONFIG_WIDTH * CONFIG_DEPTH
            + PAYLOAD_WIDTH * sum(DEPTH_AWARE_LANE_DEPTHS)
        ),
        "allocated_bits": (
            config_macro["allocated_bits"]
            + b_payload_macro["allocated_bits"]
            + a_payload_macro["allocated_bits"]
        ),
        "sram_area_mm2": (
            config_macro["area_mm2"]
            + b_payload_macro["area_mm2"]
            + a_payload_macro["area_mm2"]
        ),
        "sram_leakage_mw": (
            config_macro["leakage_mw"]
            + b_payload_macro["leakage_mw"]
            + a_payload_macro["leakage_mw"]
        ),
        "payload_read_energy_nj": {
            "lane0": b_payload_macro["read_energy_nj"],
            "lane1": a_payload_macro["read_energy_nj"],
        },
        "config_read_energy_nj": config_macro["read_energy_nj"],
        "macro_count": 3,
    }

    # Shared output holding registers and OP gating are common to both designs.
    # Estimate only the incremental two-lane frontend relative to direct slot banks.
    nand2_area_um2 = 2.54144
    mux_ge_per_bit = 3.0
    counter_ge_per_bit = 6.0
    decoder_ge = 100.0
    a_counter_bits = 13 + 5 * 11
    b_counter_bits = 13 + 2 * 12
    depth_aware_counter_bits = 13 + 12 + 11
    routing_ge = 5 * PAYLOAD_WIDTH * mux_ge_per_bit
    counter_saving_ge = (a_counter_bits - b_counter_bits) * counter_ge_per_bit
    incremental_ge = routing_ge + decoder_ge - counter_saving_ge
    incremental_logic_area_mm2 = incremental_ge * nand2_area_um2 / 1e6
    issue2_total_estimated_area = (
        issue2["sram_area_mm2"] + incremental_logic_area_mm2
    )
    depth_aware_counter_saving_ge = (
        a_counter_bits - depth_aware_counter_bits
    ) * counter_ge_per_bit
    depth_aware_incremental_ge = (
        routing_ge + decoder_ge - depth_aware_counter_saving_ge
    )
    depth_aware_incremental_logic_area_mm2 = (
        depth_aware_incremental_ge * nand2_area_um2 / 1e6
    )
    depth_aware_total_estimated_area = (
        issue2_depth_aware["sram_area_mm2"]
        + depth_aware_incremental_logic_area_mm2
    )
    candidate_a_program_read_energy_nj = (
        A_CONFIG_READS * candidate_a["config_read_energy_nj"]
        + PAYLOAD_EVENT_READS * candidate_a["payload_read_energy_nj"]
    )
    candidate_a_compact_program_read_energy_nj = (
        A_CONFIG_READS * config_macro["read_energy_nj"]
        + sum(A_COMPACT_EVENT_READS[index] * (
            a_compact_scalar_macro["read_energy_nj"]
            if depth == 1024
            else a_payload_macro["read_energy_nj"]
        ) for index, depth in enumerate(A_COMPACT_BANK_DEPTHS))
    )
    issue2_program_read_energy_nj = (
        B_CONFIG_READS * issue2["config_read_energy_nj"]
        + PAYLOAD_EVENT_READS * issue2["payload_read_energy_nj"]
    )
    depth_aware_program_read_energy_nj = (
        B_CONFIG_READS * issue2_depth_aware["config_read_energy_nj"]
        + DEPTH_AWARE_LANE_READS[0] * b_payload_macro["read_energy_nj"]
        + DEPTH_AWARE_LANE_READS[1] * a_payload_macro["read_energy_nj"]
    )

    comparison = {
        "logical_bits_change": (
            issue2["logical_bits"] / candidate_a["logical_bits"] - 1.0
        ),
        "allocated_bits_change": (
            issue2["allocated_bits"] / candidate_a["allocated_bits"] - 1.0
        ),
        "sram_area_change": (
            issue2["sram_area_mm2"] / candidate_a["sram_area_mm2"] - 1.0
        ),
        "sram_leakage_change": (
            issue2["sram_leakage_mw"] / candidate_a["sram_leakage_mw"] - 1.0
        ),
        "payload_read_energy_per_access_change": (
            issue2["payload_read_energy_nj"]
            / candidate_a["payload_read_energy_nj"]
            - 1.0
        ),
        "three_program_read_energy_change": (
            issue2_program_read_energy_nj
            / candidate_a_program_read_energy_nj
            - 1.0
        ),
        "incremental_logic_ge": incremental_ge,
        "incremental_logic_area_mm2": incremental_logic_area_mm2,
        "estimated_area_with_logic_change": (
            issue2_total_estimated_area / candidate_a["sram_area_mm2"] - 1.0
        ),
    }
    depth_aware_comparison = {
        "logical_bits_change": (
            issue2_depth_aware["logical_bits"]
            / candidate_a["logical_bits"]
            - 1.0
        ),
        "allocated_bits_change": (
            issue2_depth_aware["allocated_bits"]
            / candidate_a["allocated_bits"]
            - 1.0
        ),
        "sram_area_change": (
            issue2_depth_aware["sram_area_mm2"]
            / candidate_a["sram_area_mm2"]
            - 1.0
        ),
        "sram_leakage_change": (
            issue2_depth_aware["sram_leakage_mw"]
            / candidate_a["sram_leakage_mw"]
            - 1.0
        ),
        "three_program_read_energy_change": (
            depth_aware_program_read_energy_nj
            / candidate_a_program_read_energy_nj
            - 1.0
        ),
        "incremental_logic_ge": depth_aware_incremental_ge,
        "incremental_logic_area_mm2": depth_aware_incremental_logic_area_mm2,
        "estimated_area_with_logic_change": (
            depth_aware_total_estimated_area
            / candidate_a["sram_area_mm2"]
            - 1.0
        ),
        "change_vs_balanced_issue2": {
            "allocated_bits": (
                issue2_depth_aware["allocated_bits"]
                / issue2["allocated_bits"]
                - 1.0
            ),
            "sram_area": (
                issue2_depth_aware["sram_area_mm2"]
                / issue2["sram_area_mm2"]
                - 1.0
            ),
            "three_program_read_energy": (
                depth_aware_program_read_energy_nj
                / issue2_program_read_energy_nj
                - 1.0
            ),
        },
        "change_vs_candidate_a_compact": {
            "logical_bits": (
                issue2_depth_aware["logical_bits"]
                / candidate_a_compact["logical_bits"]
                - 1.0
            ),
            "allocated_bits": (
                issue2_depth_aware["allocated_bits"]
                / candidate_a_compact["allocated_bits"]
                - 1.0
            ),
            "sram_area": (
                issue2_depth_aware["sram_area_mm2"]
                / candidate_a_compact["sram_area_mm2"]
                - 1.0
            ),
            "sram_leakage": (
                issue2_depth_aware["sram_leakage_mw"]
                / candidate_a_compact["sram_leakage_mw"]
                - 1.0
            ),
            "three_program_read_energy": (
                depth_aware_program_read_energy_nj
                / candidate_a_compact_program_read_energy_nj
                - 1.0
            ),
        },
    }

    output = {
        "model": {
            "tool": "HP CACTI",
            "technology_nm": 32,
            "cache_type": "ram",
            "ports": "1 read-write per macro",
            "width_allocation": "whole bytes",
            "program_pool": "GELU X64 + Softmax X64 + LayerNorm X64, replaceable",
            "warning": "CACTI and gate-equivalent screening estimate; not foundry SRAM compiler or RTL synthesis",
        },
        "macros": {
            "config_5x8192": config_macro,
            "payload_34x2048": a_payload_macro,
            "payload_34x1024": a_compact_scalar_macro,
            "payload_34x4096": b_payload_macro,
        },
        "candidate_a": candidate_a,
        "candidate_a_compact": candidate_a_compact,
        "issue2": issue2,
        "issue2_depth_aware": issue2_depth_aware,
        "logic_estimate": {
            "candidate_a_counter_bits": a_counter_bits,
            "issue2_counter_bits": b_counter_bits,
            "routing_ge": routing_ge,
            "decoder_ge": decoder_ge,
            "counter_saving_ge": counter_saving_ge,
            "incremental_ge": incremental_ge,
            "incremental_area_mm2": incremental_logic_area_mm2,
            "issue2_sram_plus_incremental_logic_mm2": issue2_total_estimated_area,
            "depth_aware_counter_bits": depth_aware_counter_bits,
            "depth_aware_incremental_ge": depth_aware_incremental_ge,
            "depth_aware_incremental_area_mm2": (
                depth_aware_incremental_logic_area_mm2
            ),
            "depth_aware_sram_plus_incremental_logic_mm2": (
                depth_aware_total_estimated_area
            ),
        },
        "three_program_read_energy": {
            "payload_event_reads": PAYLOAD_EVENT_READS,
            "candidate_a_config_reads": A_CONFIG_READS,
            "issue2_config_reads": B_CONFIG_READS,
            "candidate_a_nj": candidate_a_program_read_energy_nj,
            "candidate_a_compact_nj": (
                candidate_a_compact_program_read_energy_nj
            ),
            "issue2_nj": issue2_program_read_energy_nj,
            "depth_aware_lane_reads": list(DEPTH_AWARE_LANE_READS),
            "depth_aware_issue2_nj": depth_aware_program_read_energy_nj,
        },
        "comparison": comparison,
        "depth_aware_comparison": depth_aware_comparison,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
