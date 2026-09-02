#!/usr/bin/env python3
"""Hardware screening model for adaptive 1/2/4-capacity four-lane supply."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "experiments" / "issue2_equal34_sram_compare.py"
STUDY_ROOT = ROOT / "analysis_output_issue124_four_lane_174"
STUDY_PATH = STUDY_ROOT / "issue124_adaptive_study.json"
OUTPUT_PATH = STUDY_ROOT / "issue124_adaptive_hardware_compare.json"
TWO_LANE_PATH = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "replaceable_pool_area_compare.json"
)
GROUPED_FOUR_PATH = (
    ROOT
    / "analysis_output_four_lane_174"
    / "four_lane_hardware_compare.json"
)

POOL_CASES = ("gelu_x64", "softmax_x64", "layernorm_x64")
CONFIG_DEPTH = 8192
PAYLOAD_DEPTH = 2048
CONFIG_WIDTH = 5
PAYLOAD_WIDTH = 34
NAND2_AREA_UM2 = 2.54144
VOLTAGE = 0.9
FREQUENCY_GHZ = 1.0
CAPACITANCE_FF_PER_GE_RANGE = (0.5, 2.0)
LEAKAGE_NW_PER_GE_RANGE = (1.0, 20.0)


def load_helper() -> Any:
    spec = importlib.util.spec_from_file_location("cacti_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def popcount(value: int) -> int:
    return bin(value).count("1")


def read_hex(path: Path) -> list[int]:
    return [int(line, 16) for line in path.read_text().splitlines()]


def measure_activity() -> dict[str, Any]:
    config_toggles = 0
    enable_toggles = 0
    router_toggles = 0
    counter_toggles = 0
    transitions = 0
    for case in POOL_CASES:
        directory = STUDY_ROOT / "selected" / case
        configs = read_hex(directory / "config_mask_5bit.txt")
        lanes = [
            read_hex(directory / f"lane{lane}_34bit.txt")
            for lane in range(4)
        ]
        positions = [0, 0, 0, 0]
        counters = [0, 0, 0, 0]
        config_counter = 0
        phase = 0
        previous_config = 0
        previous_enable = 0
        previous_router = 0
        for code in configs:
            enable = 0
            slots = [0, 0, 0, 0, 0]
            old_phase = phase
            if code != 31:
                active = [slot for slot in range(5) if code & (1 << slot)]
                for rank, slot in enumerate(active):
                    lane = (phase + rank) % 4
                    payload = lanes[lane][positions[lane]]
                    positions[lane] += 1
                    before = counters[lane]
                    counters[lane] += 1
                    counter_toggles += popcount(before ^ counters[lane])
                    enable |= 1 << lane
                    slots[slot] = payload
                phase = (phase + len(active)) % 4
            router = 0
            for payload in slots:
                router = (router << PAYLOAD_WIDTH) | payload
            config_toggles += popcount(previous_config ^ code)
            enable_toggles += popcount(previous_enable ^ enable)
            router_toggles += popcount(previous_router ^ router)
            counter_toggles += popcount(old_phase ^ phase)
            before_config = config_counter
            config_counter += 1
            counter_toggles += popcount(before_config ^ config_counter)
            previous_config = code
            previous_enable = enable
            previous_router = router
            transitions += 1
        if positions != [len(stream) for stream in lanes]:
            raise AssertionError(f"{case}: unread lane payload")

    counter_bits = 13 + 4 * 11 + 2
    activity = {
        "mask_decode_and_enable": (
            (config_toggles + enable_toggles) / (9 * transitions)
        ),
        "four_to_five_router": (
            router_toggles / (5 * PAYLOAD_WIDTH * transitions)
        ),
        "counters_and_phase": counter_toggles / (counter_bits * transitions),
    }
    return {
        "cycles": transitions,
        "counter_bits": counter_bits,
        "raw_toggles": {
            "config": config_toggles,
            "bank_enable": enable_toggles,
            "router_output": router_toggles,
            "counter_and_phase": counter_toggles,
        },
        "activity_factors": activity,
    }


def logic_estimate() -> dict[str, Any]:
    measured = measure_activity()
    categories_ge = {
        "mask_decode_and_enable": 180.0,
        "four_to_five_router": 5 * PAYLOAD_WIDTH * 9.0,
        "counters_and_phase": measured["counter_bits"] * 6.0,
    }
    total_ge = sum(categories_ge.values())
    switched_ge = sum(
        categories_ge[name] * measured["activity_factors"][name]
        for name in categories_ge
    )
    dynamic_range = [
        switched_ge * capacitance * VOLTAGE**2 * FREQUENCY_GHZ / 1000.0
        for capacitance in CAPACITANCE_FF_PER_GE_RANGE
    ]
    leakage_range = [
        total_ge * leakage / 1_000_000.0
        for leakage in LEAKAGE_NW_PER_GE_RANGE
    ]
    return {
        "categories_ge": categories_ge,
        "total_ge": total_ge,
        "area_mm2": total_ge * NAND2_AREA_UM2 / 1e6,
        "measured_activity": measured,
        "effective_switched_ge_per_cycle": switched_ge,
        "dynamic_power_mw_range": dynamic_range,
        "leakage_power_mw_range": leakage_range,
        "assumptions": {
            "voltage_v": VOLTAGE,
            "frequency_ghz": FREQUENCY_GHZ,
            "effective_capacitance_ff_per_ge_range": list(
                CAPACITANCE_FF_PER_GE_RANGE
            ),
            "leakage_nw_per_ge_range": list(LEAKAGE_NW_PER_GE_RANGE),
            "warning": (
                "Routing GE and power are screening estimates; replace with "
                "RTL synthesis and SAIF/VCD power."
            ),
        },
    }


def organization(
    config_macro: dict[str, Any],
    payload_macro: dict[str, Any],
    cycles: int,
    events: int,
    logic: dict[str, Any],
) -> dict[str, Any]:
    sram_area = config_macro["area_mm2"] + 4 * payload_macro["area_mm2"]
    sram_leakage = (
        config_macro["leakage_mw"] + 4 * payload_macro["leakage_mw"]
    )
    read_energy = (
        cycles * config_macro["read_energy_nj"]
        + events * payload_macro["read_energy_nj"]
    )
    execution_time_us = cycles / (FREQUENCY_GHZ * 1000.0)
    sram_dynamic_power = read_energy / execution_time_us
    total_power_range = [
        sram_dynamic_power
        + sram_leakage
        + logic["dynamic_power_mw_range"][index]
        + logic["leakage_power_mw_range"][index]
        for index in range(2)
    ]
    return {
        "organization": {
            "config": [config_macro["logical_width"], CONFIG_DEPTH, 1],
            "payload": [PAYLOAD_WIDTH, PAYLOAD_DEPTH, 4],
        },
        "logical_bits": (
            config_macro["logical_width"] * CONFIG_DEPTH
            + 4 * PAYLOAD_WIDTH * PAYLOAD_DEPTH
        ),
        "cacti_allocated_bits": (
            config_macro["allocated_bits"]
            + 4 * payload_macro["allocated_bits"]
        ),
        "sram_area_mm2": sram_area,
        "logic_area_mm2": logic["area_mm2"],
        "total_area_mm2": sram_area + logic["area_mm2"],
        "sram_leakage_mw": sram_leakage,
        "program_read_energy_nj": read_energy,
        "program_read_energy_pj_per_event": 1000.0 * read_energy / events,
        "average_sram_dynamic_power_mw_at_1ghz": sram_dynamic_power,
        "logic_dynamic_power_mw_range": logic["dynamic_power_mw_range"],
        "logic_leakage_power_mw_range": logic["leakage_power_mw_range"],
        "total_active_power_mw_range": total_power_range,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cacti-root", type=Path, required=True)
    args = parser.parse_args()
    study = json.loads(STUDY_PATH.read_text())
    two_lane = json.loads(TWO_LANE_PATH.read_text())
    grouped = json.loads(GROUPED_FOUR_PATH.read_text())
    helper = load_helper()
    template = (args.cacti_root / "cache.cfg").read_text()
    config5 = helper.run_macro(
        args.cacti_root, template, CONFIG_WIDTH, CONFIG_DEPTH
    )
    config8 = helper.run_macro(args.cacti_root, template, 8, CONFIG_DEPTH)
    payload = helper.run_macro(
        args.cacti_root, template, PAYLOAD_WIDTH, PAYLOAD_DEPTH
    )
    logic = logic_estimate()
    cycles = study["three_x64_pool"]["cycles"]
    events = study["three_x64_pool"]["events"]
    primary = organization(config5, payload, cycles, events, logic)
    physical8 = organization(config8, payload, cycles, events, logic)

    references = {
        "candidate_a_symmetric": {
            "total_area_mm2": (
                two_lane["candidate_a"]["sram_area_mm2"]
                + (68 * 6 + 60) * NAND2_AREA_UM2 / 1e6
            ),
            "program_read_energy_nj": (
                two_lane["three_program_read_energy"]["candidate_a_nj"]
            ),
            "sram_only_active_power_mw": (
                two_lane["three_program_read_energy"]["candidate_a_nj"]
                / (5453 / 1000.0)
                + two_lane["candidate_a"]["sram_leakage_mw"]
            ),
        },
        "two_lane_general": {
            "total_area_mm2": (
                two_lane["issue2"]["sram_area_mm2"]
                + (37 * 6 + 100 + 510) * NAND2_AREA_UM2 / 1e6
            ),
            "program_read_energy_nj": (
                two_lane["three_program_read_energy"]["issue2_nj"]
            ),
            "sram_only_active_power_mw": (
                two_lane["three_program_read_energy"]["issue2_nj"]
                / (5475 / 1000.0)
                + two_lane["issue2"]["sram_leakage_mw"]
            ),
        },
        "grouped_four_lane_general": {
            "total_area_mm2": grouped["four_lane_general"]["total_area_mm2"],
            "program_read_energy_nj": (
                grouped["four_lane_general"]["program_read_energy_nj"]
            ),
            "total_active_power_mw_range": (
                grouped["four_lane_general"]["total_active_power_mw_range"]
            ),
        },
    }
    comparisons = {}
    for name, reference in references.items():
        comparisons[name] = {
            "total_area_change": (
                primary["total_area_mm2"] / reference["total_area_mm2"] - 1.0
            ),
            "program_read_energy_change": (
                primary["program_read_energy_nj"]
                / reference["program_read_energy_nj"]
                - 1.0
            ),
        }
        if "total_active_power_mw_range" in reference:
            comparisons[name]["active_power_range_change"] = [
                primary["total_active_power_mw_range"][index]
                / reference["total_active_power_mw_range"][index]
                - 1.0
                for index in range(2)
            ]
        elif "sram_only_active_power_mw" in reference:
            comparisons[name][
                "active_power_range_change_vs_reference_sram_only"
            ] = [
                power / reference["sram_only_active_power_mw"] - 1.0
                for power in primary["total_active_power_mw_range"]
            ]
    grouped_physical8 = grouped["physical_8bit_config_port_sensitivity"][
        "general"
    ]
    comparisons["grouped_four_lane_physical8_sensitivity"] = {
        "total_area_change": (
            physical8["total_area_mm2"]
            / grouped_physical8["total_area_mm2"]
            - 1.0
        ),
        "program_read_energy_change": (
            physical8["program_read_energy_nj"]
            / grouped_physical8["program_read_energy_nj"]
            - 1.0
        ),
    }

    output = {
        "model": {
            "tool": "HP CACTI plus gate-equivalent logic screening",
            "technology_nm": 32,
            "frequency_ghz": FREQUENCY_GHZ,
            "read_gating": (
                "Exactly popcount(mask) payload lanes are read; every invalid "
                "lane is independently gated."
            ),
            "scope": "GELU X64 + Softmax X64 + LayerNorm X64 pool",
            "pipeline_contract": (
                "State advances on ready/valid acceptance; stalls also hold "
                "in-flight valid, mask, phase, enables, and output registers."
            ),
            "control_flow_scope": (
                "Linear traces unless config PC, phase, and payload positions "
                "are checkpointed at every non-sequential entry."
            ),
        },
        "macros": {
            "config_5x8192": config5,
            "config_8x8192_sensitivity": config8,
            "payload_34x2048": payload,
        },
        "logic": logic,
        "adaptive_issue124": primary,
        "physical_8bit_config_port_sensitivity": physical8,
        "performance": {
            "pool": study["three_x64_pool"],
            "aggregate_12_workloads": study["aggregate"],
        },
        "references": references,
        "comparisons": comparisons,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps({
        "cycles": cycles,
        "events": events,
        "total_area_mm2": primary["total_area_mm2"],
        "program_read_energy_nj": primary["program_read_energy_nj"],
        "total_active_power_mw_range": primary["total_active_power_mw_range"],
        "comparisons": comparisons,
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
