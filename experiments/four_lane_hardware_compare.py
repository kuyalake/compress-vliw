#!/usr/bin/env python3
"""CACTI and companion-logic screening model for grouped four-lane storage."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "experiments" / "issue2_equal34_sram_compare.py"
MAPPING_PATH = (
    ROOT / "analysis_output_four_lane_174" / "four_lane_mapping_study.json"
)
STREAM_ROOT = ROOT / "analysis_output_four_lane_174"
OUTPUT_PATH = STREAM_ROOT / "four_lane_hardware_compare.json"
TWO_LANE_PPA = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "replaceable_pool_area_compare.json"
)

POOL_CASES = ("gelu_x64", "softmax_x64", "layernorm_x64")
CONFIG_DEPTH = 8192
CONFIG_WIDTH = 6
PAYLOAD_WIDTH = 34
FREQUENCY_GHZ = 1.0
SUPPLY_VOLTAGE = 0.9
NAND2_AREA_UM2 = 2.54144
CAPACITANCE_RANGE_FF_PER_GE = (0.5, 2.0)
LEAKAGE_RANGE_NW_PER_GE = (1.0, 20.0)


def load_helper() -> Any:
    spec = importlib.util.spec_from_file_location("cacti_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def popcount(value: int) -> int:
    return bin(value).count("1")


def build_local_states() -> dict[int, tuple[int | None, int | None]]:
    choices: tuple[int | None, ...] = (None, 0, 1, 2, 3, 4)
    states = [
        (local0, local1)
        for local0 in choices
        for local1 in choices
        if local0 is None or local1 is None or local0 != local1
    ]
    return {code: state for code, state in enumerate(states)}


LOCAL_STATES = build_local_states()


def read_hex_stream(path: Path) -> list[int]:
    return [int(line, 16) for line in path.read_text().splitlines()]


def measure_activity(policy: str, lane_widths: list[int]) -> dict[str, Any]:
    config_toggles = 0
    enable_toggles = 0
    pair_toggles = 0
    router_toggles = 0
    counter_toggles = 0
    transitions = 0
    total_cycles = 0

    for case in POOL_CASES:
        directory = STREAM_ROOT / policy / case
        configs = read_hex_stream(directory / "config_6bit.txt")
        lane_streams = [
            read_hex_stream(directory / f"lane{lane}_34bit.txt")
            for lane in range(4)
        ]
        positions = [0, 0, 0, 0]
        counters = [0, 0, 0, 0]
        config_counter = 0
        previous_config = 0
        previous_enables = 0
        previous_pair = 0
        previous_router = 0

        for code in configs:
            enables = 0
            pair_words = [0, 0]
            slot_words = [0, 0, 0, 0, 0]
            if code != 63:
                group = code >> 5
                local_state = LOCAL_STATES[code & 0x1F]
                for local_lane, slot in enumerate(local_state):
                    if slot is None:
                        continue
                    lane = 2 * group + local_lane
                    payload = lane_streams[lane][positions[lane]]
                    positions[lane] += 1
                    enables |= 1 << lane
                    pair_words[local_lane] = payload
                    slot_words[slot] = payload
                    before = counters[lane]
                    counters[lane] += 1
                    counter_toggles += popcount(before ^ counters[lane])

            pair_value = (pair_words[0] << PAYLOAD_WIDTH) | pair_words[1]
            router_value = 0
            for payload in slot_words:
                router_value = (router_value << PAYLOAD_WIDTH) | payload

            config_toggles += popcount(previous_config ^ code)
            enable_toggles += popcount(previous_enables ^ enables)
            pair_toggles += popcount(previous_pair ^ pair_value)
            router_toggles += popcount(previous_router ^ router_value)
            previous_config = code
            previous_enables = enables
            previous_pair = pair_value
            previous_router = router_value

            before_config = config_counter
            config_counter += 1
            counter_toggles += popcount(before_config ^ config_counter)
            transitions += 1
            total_cycles += 1

        if positions != [len(stream) for stream in lane_streams]:
            raise AssertionError(f"{policy}/{case}: unread lane payloads")

    counter_bits = 13 + sum(lane_widths)
    activities = {
        "decoder_and_enable": (
            (config_toggles + enable_toggles)
            / ((CONFIG_WIDTH + 4) * transitions)
        ),
        "pair_mux": pair_toggles / (2 * PAYLOAD_WIDTH * transitions),
        "two_to_five_router": (
            router_toggles / (5 * PAYLOAD_WIDTH * transitions)
        ),
        "counters": counter_toggles / (counter_bits * transitions),
    }
    return {
        "cycles": total_cycles,
        "raw_toggles": {
            "config": config_toggles,
            "bank_enables": enable_toggles,
            "pair_mux_output": pair_toggles,
            "router_output": router_toggles,
            "counters": counter_toggles,
        },
        "activity_factors": activities,
        "counter_bits": counter_bits,
    }


def logic_estimate(policy: str, lane_widths: list[int]) -> dict[str, Any]:
    activity = measure_activity(policy, lane_widths)
    category_ge = {
        "decoder_and_enable": 140.0,
        "pair_mux": 2 * PAYLOAD_WIDTH * 3.0,
        "two_to_five_router": 5 * PAYLOAD_WIDTH * 3.0,
        "counters": activity["counter_bits"] * 6.0,
    }
    total_ge = sum(category_ge.values())
    switched_ge = sum(
        category_ge[name] * activity["activity_factors"][name]
        for name in category_ge
    )
    dynamic_power_range_mw = [
        switched_ge * capacitance * SUPPLY_VOLTAGE**2 * FREQUENCY_GHZ
        / 1000.0
        for capacitance in CAPACITANCE_RANGE_FF_PER_GE
    ]
    leakage_power_range_mw = [
        total_ge * leakage / 1_000_000.0
        for leakage in LEAKAGE_RANGE_NW_PER_GE
    ]
    return {
        "categories_ge": category_ge,
        "total_ge": total_ge,
        "area_mm2": total_ge * NAND2_AREA_UM2 / 1e6,
        "measured_activity": activity,
        "effective_switched_ge_per_cycle": switched_ge,
        "assumptions": {
            "voltage_v": SUPPLY_VOLTAGE,
            "frequency_ghz": FREQUENCY_GHZ,
            "effective_capacitance_ff_per_ge_range": list(
                CAPACITANCE_RANGE_FF_PER_GE
            ),
            "leakage_nw_per_ge_range": list(LEAKAGE_RANGE_NW_PER_GE),
            "warning": (
                "Screening range only; replace with synthesized netlist, "
                "standard-cell library, and SAIF/VCD power analysis."
            ),
        },
        "dynamic_power_mw_range": dynamic_power_range_mw,
        "leakage_power_mw_range": leakage_power_range_mw,
    }


def build_organization(
    name: str,
    depths: list[int],
    event_reads: list[int],
    config_macro: dict[str, Any],
    macros: dict[int, dict[str, Any]],
    logic: dict[str, Any],
    cycles: int,
) -> dict[str, Any]:
    if len(depths) != 4 or len(event_reads) != 4:
        raise ValueError("Four depths and read counts are required")
    sram_area = config_macro["area_mm2"] + sum(
        macros[depth]["area_mm2"] for depth in depths
    )
    sram_leakage = config_macro["leakage_mw"] + sum(
        macros[depth]["leakage_mw"] for depth in depths
    )
    read_energy = cycles * config_macro["read_energy_nj"] + sum(
        reads * macros[depth]["read_energy_nj"]
        for reads, depth in zip(event_reads, depths)
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
        "name": name,
        "organization": {
            "config": [CONFIG_WIDTH, CONFIG_DEPTH, 1],
            "payload_depths": depths,
            "payload_event_reads": event_reads,
        },
        "logical_bits": (
            CONFIG_WIDTH * CONFIG_DEPTH + PAYLOAD_WIDTH * sum(depths)
        ),
        "cacti_allocated_bits": (
            config_macro["allocated_bits"]
            + sum(macros[depth]["allocated_bits"] for depth in depths)
        ),
        "sram_area_mm2": sram_area,
        "logic_area_mm2": logic["area_mm2"],
        "total_area_mm2": sram_area + logic["area_mm2"],
        "sram_leakage_mw": sram_leakage,
        "program_read_energy_nj": read_energy,
        "program_read_energy_pj_per_event": (
            1000.0 * read_energy / sum(event_reads)
        ),
        "average_sram_dynamic_power_mw_at_1ghz": sram_dynamic_power,
        "logic_dynamic_power_mw_range": logic["dynamic_power_mw_range"],
        "logic_leakage_power_mw_range": logic["leakage_power_mw_range"],
        "total_active_power_mw_range": total_power_range,
        "logic": logic,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cacti-root", type=Path, required=True)
    args = parser.parse_args()
    helper = load_helper()
    template = (args.cacti_root / "cache.cfg").read_text()
    mapping = json.loads(MAPPING_PATH.read_text())
    two_lane = json.loads(TWO_LANE_PPA.read_text())

    config_macro = helper.run_macro(
        args.cacti_root, template, CONFIG_WIDTH, CONFIG_DEPTH
    )
    config_macro_physical8 = helper.run_macro(
        args.cacti_root, template, 8, CONFIG_DEPTH
    )
    macros = {
        depth: helper.run_macro(
            args.cacti_root, template, PAYLOAD_WIDTH, depth
        )
        for depth in (1024, 2048)
    }
    cycles = sum(
        row["cycles_T"] for row in mapping["general_symmetric"]["workloads"]
    )
    if cycles != 5475:
        raise AssertionError(f"Unexpected pool cycle count {cycles}")

    general_depths = [2048, 2048, 2048, 2048]
    general_reads = mapping["general_symmetric"]["lane_depths"]
    fitted_depths = [2048, 2048, 1024, 1024]
    fitted_reads = mapping["pool_fitted"]["lane_depths"]
    general_logic = logic_estimate("general_symmetric", [11, 11, 11, 11])
    fitted_logic = logic_estimate("pool_fitted", [11, 11, 10, 10])

    general = build_organization(
        "four_lane_general_symmetric",
        general_depths,
        general_reads,
        config_macro,
        macros,
        general_logic,
        cycles,
    )
    fitted = build_organization(
        "four_lane_pool_fitted",
        fitted_depths,
        fitted_reads,
        config_macro,
        macros,
        fitted_logic,
        cycles,
    )
    general_physical8 = build_organization(
        "four_lane_general_physical_8bit_config_port",
        general_depths,
        general_reads,
        config_macro_physical8,
        macros,
        general_logic,
        cycles,
    )
    fitted_physical8 = build_organization(
        "four_lane_pool_fitted_physical_8bit_config_port",
        fitted_depths,
        fitted_reads,
        config_macro_physical8,
        macros,
        fitted_logic,
        cycles,
    )

    references = {
        "candidate_a_symmetric": {
            "sram_area_mm2": two_lane["candidate_a"]["sram_area_mm2"],
            "estimated_total_area_mm2": (
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
        "candidate_a_compact": {
            "sram_area_mm2": two_lane["candidate_a_compact"]["sram_area_mm2"],
            "estimated_total_area_mm2": (
                two_lane["candidate_a_compact"]["sram_area_mm2"]
                + (67 * 6 + 60) * NAND2_AREA_UM2 / 1e6
            ),
            "program_read_energy_nj": (
                two_lane["three_program_read_energy"]["candidate_a_compact_nj"]
            ),
            "sram_only_active_power_mw": (
                two_lane["three_program_read_energy"]["candidate_a_compact_nj"]
                / (5453 / 1000.0)
                + two_lane["candidate_a_compact"]["sram_leakage_mw"]
            ),
        },
        "two_lane_general_symmetric": {
            "sram_area_mm2": two_lane["issue2"]["sram_area_mm2"],
            "estimated_total_area_mm2": (
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
        "two_lane_pool_fitted": {
            "sram_area_mm2": two_lane["issue2_depth_aware"]["sram_area_mm2"],
            "estimated_total_area_mm2": (
                two_lane["issue2_depth_aware"]["sram_area_mm2"]
                + (36 * 6 + 100 + 510) * NAND2_AREA_UM2 / 1e6
            ),
            "program_read_energy_nj": (
                two_lane["three_program_read_energy"]["depth_aware_issue2_nj"]
            ),
            "sram_only_active_power_mw": (
                two_lane["three_program_read_energy"]["depth_aware_issue2_nj"]
                / (5475 / 1000.0)
                + two_lane["issue2_depth_aware"]["sram_leakage_mw"]
            ),
        },
    }
    comparisons = {
        "general_vs_a_symmetric": {
            "sram_area_change": (
                general["sram_area_mm2"]
                / references["candidate_a_symmetric"]["sram_area_mm2"]
                - 1.0
            ),
            "program_read_energy_change": (
                general["program_read_energy_nj"]
                / references["candidate_a_symmetric"]["program_read_energy_nj"]
                - 1.0
            ),
            "estimated_total_area_change": (
                general["total_area_mm2"]
                / references["candidate_a_symmetric"]["estimated_total_area_mm2"]
                - 1.0
            ),
            "total_power_range_change_vs_reference_sram_only": [
                power
                / references["candidate_a_symmetric"]["sram_only_active_power_mw"]
                - 1.0
                for power in general["total_active_power_mw_range"]
            ],
        },
        "general_vs_two_lane_general": {
            "sram_area_change": (
                general["sram_area_mm2"]
                / references["two_lane_general_symmetric"]["sram_area_mm2"]
                - 1.0
            ),
            "program_read_energy_change": (
                general["program_read_energy_nj"]
                / references["two_lane_general_symmetric"]["program_read_energy_nj"]
                - 1.0
            ),
            "estimated_total_area_change": (
                general["total_area_mm2"]
                / references["two_lane_general_symmetric"]["estimated_total_area_mm2"]
                - 1.0
            ),
            "total_power_range_change_vs_reference_sram_only": [
                power
                / references["two_lane_general_symmetric"]["sram_only_active_power_mw"]
                - 1.0
                for power in general["total_active_power_mw_range"]
            ],
        },
        "fitted_vs_a_compact": {
            "sram_area_change": (
                fitted["sram_area_mm2"]
                / references["candidate_a_compact"]["sram_area_mm2"]
                - 1.0
            ),
            "program_read_energy_change": (
                fitted["program_read_energy_nj"]
                / references["candidate_a_compact"]["program_read_energy_nj"]
                - 1.0
            ),
            "estimated_total_area_change": (
                fitted["total_area_mm2"]
                / references["candidate_a_compact"]["estimated_total_area_mm2"]
                - 1.0
            ),
            "total_power_range_change_vs_reference_sram_only": [
                power
                / references["candidate_a_compact"]["sram_only_active_power_mw"]
                - 1.0
                for power in fitted["total_active_power_mw_range"]
            ],
        },
        "fitted_vs_two_lane_fitted": {
            "sram_area_change": (
                fitted["sram_area_mm2"]
                / references["two_lane_pool_fitted"]["sram_area_mm2"]
                - 1.0
            ),
            "program_read_energy_change": (
                fitted["program_read_energy_nj"]
                / references["two_lane_pool_fitted"]["program_read_energy_nj"]
                - 1.0
            ),
            "estimated_total_area_change": (
                fitted["total_area_mm2"]
                / references["two_lane_pool_fitted"]["estimated_total_area_mm2"]
                - 1.0
            ),
            "total_power_range_change_vs_reference_sram_only": [
                power
                / references["two_lane_pool_fitted"]["sram_only_active_power_mw"]
                - 1.0
                for power in fitted["total_active_power_mw_range"]
            ],
        },
    }
    output = {
        "model": {
            "tool": "HP CACTI plus gate-equivalent logic screening",
            "technology_nm": 32,
            "frequency_ghz": FREQUENCY_GHZ,
            "program_pool": list(POOL_CASES),
            "warning": (
                "SRAM values are CACTI screening estimates. Logic power is a "
                "measured-toggle range, not post-layout signoff."
            ),
            "read_gating_assumption": (
                "Only lanes carrying valid events are read. Unselected groups "
                "and the unused lane of a single-event cycle remain disabled."
            ),
        },
        "macros": {
            "config_6x8192": config_macro,
            "config_8x8192_sensitivity": config_macro_physical8,
            "payload_34x1024": macros[1024],
            "payload_34x2048": macros[2048],
        },
        "four_lane_general": general,
        "four_lane_pool_fitted": fitted,
        "physical_8bit_config_port_sensitivity": {
            "general": general_physical8,
            "pool_fitted": fitted_physical8,
            "purpose": (
                "Conservative sensitivity when the SRAM compiler exposes the "
                "whole allocated byte instead of a six-bit read port."
            ),
        },
        "references": references,
        "comparisons": comparisons,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps({
        "general": {
            "lane_reads": general_reads,
            "total_area_mm2": general["total_area_mm2"],
            "program_read_energy_nj": general["program_read_energy_nj"],
            "total_active_power_mw_range": general["total_active_power_mw_range"],
            "physical8_total_area_mm2": general_physical8["total_area_mm2"],
            "physical8_program_read_energy_nj": (
                general_physical8["program_read_energy_nj"]
            ),
        },
        "pool_fitted": {
            "lane_reads": fitted_reads,
            "total_area_mm2": fitted["total_area_mm2"],
            "program_read_energy_nj": fitted["program_read_energy_nj"],
            "total_active_power_mw_range": fitted["total_active_power_mw_range"],
            "physical8_total_area_mm2": fitted_physical8["total_area_mm2"],
            "physical8_program_read_energy_nj": (
                fitted_physical8["program_read_energy_nj"]
            ),
        },
        "comparisons": comparisons,
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
