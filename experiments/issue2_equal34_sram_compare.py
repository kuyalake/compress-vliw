#!/usr/bin/env python3
"""Compare equal-34-bit Candidate A and two-lane SRAMs with HP CACTI."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ISSUE2_RESULTS = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "final_priority_comparison.json"
)
OUTPUT_PATH = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "equal34_sram_compare.json"
)

SLOT_WIDTHS = {
    "load": 34,
    "store": 34,
    "vector": 34,
    "scalar": 34,
    "sfu": 34,
}


def next_power_of_two(value: int) -> int:
    return 1 if value <= 1 else 1 << (value - 1).bit_length()


def replace_active_setting(text: str, prefix: str, replacement: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(prefix)}.*$")
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace active CACTI setting: {prefix}")
    return updated


def make_config(template: str, width: int, depth: int) -> str:
    block_bytes = max(1, math.ceil(width / 8))
    size_bytes = block_bytes * depth
    config = template
    settings = {
        "-size (bytes)": f"-size (bytes) {size_bytes}",
        "-block size (bytes)": f"-block size (bytes) {block_bytes}",
        "-associativity": "-associativity 1",
        "-read-write port": "-read-write port 1",
        "-exclusive read port": "-exclusive read port 0",
        "-exclusive write port": "-exclusive write port 0",
        "-single ended read ports": "-single ended read ports 0",
        "-UCA bank count": "-UCA bank count 1",
        "-technology (u)": "-technology (u) 0.032",
        "-output/input bus width": f"-output/input bus width {width}",
        "-operating temperature (K)": "-operating temperature (K) 300",
        "-cache type": '-cache type "ram"',
        "-tag size (b)": '-tag size (b) "default"',
        "-access mode (normal, sequential, fast)": '-access mode (normal, sequential, fast) - "normal"',
        "-design objective (weight delay, dynamic power, leakage power, cycle time, area)":
            "-design objective (weight delay, dynamic power, leakage power, cycle time, area) 0:0:0:100:0",
        "-deviate (delay, dynamic power, leakage power, cycle time, area)":
            "-deviate (delay, dynamic power, leakage power, cycle time, area) 20:100000:100000:100000:100000",
        "-Optimize ED or ED^2 (ED, ED^2, NONE):":
            '-Optimize ED or ED^2 (ED, ED^2, NONE): "NONE"',
    }
    for prefix, replacement in settings.items():
        config = replace_active_setting(config, prefix, replacement)
    return config


def parse_metric(output: str, label: str) -> float:
    match = re.search(rf"{re.escape(label)}\s*:?\s*([0-9.eE+-]+)", output)
    if match is None:
        raise RuntimeError(f"Missing CACTI metric: {label}")
    return float(match.group(1))


def parse_cacti(output: str) -> dict[str, float]:
    dimensions = re.search(
        r"Cache height x width \(mm\):\s*([0-9.eE+-]+)\s*x\s*([0-9.eE+-]+)",
        output,
    )
    if dimensions is None:
        raise RuntimeError("CACTI did not produce cache dimensions")
    height = float(dimensions.group(1))
    width = float(dimensions.group(2))
    return {
        "access_time_ns": parse_metric(output, "Access time (ns)"),
        "cycle_time_ns": parse_metric(output, "Cycle time (ns)"),
        "read_energy_nj": parse_metric(output, "Total dynamic read energy per access (nJ)"),
        "write_energy_nj": parse_metric(output, "Total dynamic write energy per access (nJ)"),
        "leakage_mw": parse_metric(output, "Total leakage power of a bank (mW)"),
        "height_mm": height,
        "width_mm": width,
        "area_mm2": height * width,
    }


def run_macro(
    cacti_root: Path,
    template: str,
    logical_width: int,
    logical_depth: int,
) -> dict[str, Any]:
    initial_depth = next_power_of_two(logical_depth)
    errors: list[str] = []
    for scale in range(8):
        physical_depth = initial_depth << scale
        config = make_config(template, logical_width, physical_depth)
        with tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False) as handle:
            handle.write(config)
            config_path = Path(handle.name)
        try:
            result = subprocess.run(
                [str(cacti_root / "cacti"), "-infile", str(config_path)],
                cwd=cacti_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
        finally:
            config_path.unlink(missing_ok=True)
        if result.returncode == 0 and "Cache height x width (mm)" in result.stdout:
            metrics = parse_cacti(result.stdout)
            return {
                "logical_width": logical_width,
                "logical_depth": logical_depth,
                "physical_depth": physical_depth,
                "logical_bits": logical_width * logical_depth,
                "allocated_word_bits": 8 * math.ceil(logical_width / 8),
                "allocated_bits": 8 * math.ceil(logical_width / 8) * physical_depth,
                **metrics,
            }
        errors.append(result.stdout[-500:])
    raise RuntimeError(
        f"No legal CACTI organization for {logical_width}x{logical_depth}: "
        + " | ".join(errors)
    )


def macro_key(width: int, depth: int) -> str:
    return f"{width}x{depth}"


def sum_macro_metrics(macros: dict[str, dict[str, Any]]) -> dict[str, float]:
    return {
        "area_mm2": sum(macro["area_mm2"] for macro in macros.values()),
        "leakage_mw": sum(macro["leakage_mw"] for macro in macros.values()),
        "logical_bits": sum(macro["logical_bits"] for macro in macros.values()),
        "allocated_bits": sum(macro["allocated_bits"] for macro in macros.values()),
        "max_access_time_ns": max(macro["access_time_ns"] for macro in macros.values()),
        "max_cycle_time_ns": max(macro["cycle_time_ns"] for macro in macros.values()),
    }


def optimize_segmented_macro(
    width: int,
    logical_depth: int,
    modeled: dict[str, dict[str, Any]],
    max_segments: int = 2,
) -> dict[str, Any]:
    unique_options: dict[int, dict[str, Any]] = {}
    for macro in modeled.values():
        if macro["logical_width"] != width:
            continue
        depth = macro["physical_depth"]
        if depth not in unique_options or macro["area_mm2"] < unique_options[depth]["area_mm2"]:
            unique_options[depth] = macro
    options = sorted(unique_options.values(), key=lambda macro: macro["physical_depth"])
    if not options:
        raise RuntimeError(f"No CACTI options for width {width}")

    candidates: list[list[dict[str, Any]]] = []
    for first in options:
        candidates.append([first])
        if max_segments >= 2:
            for second in options:
                candidates.append([first, second])
    feasible = [
        segments
        for segments in candidates
        if sum(segment["physical_depth"] for segment in segments) >= logical_depth
    ]
    segments = min(
        feasible,
        key=lambda item: (
            sum(segment["area_mm2"] for segment in item),
            len(item),
            sum(segment["physical_depth"] for segment in item),
        ),
    )
    capacity = sum(segment["physical_depth"] for segment in segments)
    area = sum(segment["area_mm2"] for segment in segments)
    return {
        "logical_width": width,
        "logical_depth": logical_depth,
        "physical_depth": capacity,
        "segment_depths": [segment["physical_depth"] for segment in segments],
        "segments": [
            {
                "physical_depth": segment["physical_depth"],
                "read_energy_nj": segment["read_energy_nj"],
            }
            for segment in segments
        ],
        "segment_count": len(segments),
        "area_mm2": area,
        "leakage_mw": sum(segment["leakage_mw"] for segment in segments),
        "allocated_bits": sum(segment["allocated_bits"] for segment in segments),
        "max_access_time_ns": max(segment["access_time_ns"] for segment in segments),
        "max_cycle_time_ns": max(segment["cycle_time_ns"] for segment in segments),
    }


def sum_segmented_metrics(macros: dict[str, dict[str, Any]]) -> dict[str, float]:
    return {
        "area_mm2": sum(macro["area_mm2"] for macro in macros.values()),
        "leakage_mw": sum(macro["leakage_mw"] for macro in macros.values()),
        "allocated_bits": sum(macro["allocated_bits"] for macro in macros.values()),
        "macro_count": sum(macro["segment_count"] for macro in macros.values()),
        "max_access_time_ns": max(macro["max_access_time_ns"] for macro in macros.values()),
        "max_cycle_time_ns": max(macro["max_cycle_time_ns"] for macro in macros.values()),
    }


def stream_read_energy(accesses: int, segments: tuple[dict[str, float], ...]) -> float:
    remaining = accesses
    energy = 0.0
    for segment in segments:
        reads = min(remaining, int(segment["physical_depth"]))
        energy += reads * segment["read_energy_nj"]
        remaining -= reads
        if remaining == 0:
            break
    if remaining:
        raise RuntimeError("Segmented macro capacity is too small")
    return energy


def optimize_suite_read_energy(
    macros: dict[str, dict[str, Any]],
    workload_organizations: dict[str, dict[str, Any]],
    access_field: str,
) -> dict[str, Any]:
    stream_results: dict[str, Any] = {}
    total_energy = 0.0
    for stream, macro in macros.items():
        accesses = [
            organization[access_field].get(stream, 0)
            for organization in workload_organizations.values()
        ]
        orders = list(itertools.permutations(macro["segments"]))
        best_order = min(
            orders,
            key=lambda order: sum(
                stream_read_energy(count, order)
                for count in accesses
            ),
        )
        energy = sum(stream_read_energy(count, best_order) for count in accesses)
        total_energy += energy
        stream_results[stream] = {
            "segment_order": [segment["physical_depth"] for segment in best_order],
            "suite_read_energy_nj": energy,
        }
    return {
        "streams": stream_results,
        "suite_read_energy_nj": total_energy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cacti-root", type=Path, required=True)
    args = parser.parse_args()
    cacti_root = args.cacti_root.resolve()
    template = (cacti_root / "cache.cfg").read_text()
    issue2 = json.loads(ISSUE2_RESULTS.read_text())

    required_shapes: set[tuple[int, int]] = set()
    workload_organizations: dict[str, dict[str, Any]] = {}
    for workload in issue2["workloads"]:
        a_shapes = {"config": (5, workload["optimized_issue5_cycles"] - 1)}
        a_shapes.update(
            {
                slot: (width, workload["slot_counts"][slot])
                for slot, width in SLOT_WIDTHS.items()
                if workload["slot_counts"][slot] > 0
            }
        )
        lane_shapes = {
            "config": (5, workload["issue2_cycles"]),
            "lane0": (34, workload["lane_depths"][0]),
            "lane1": (34, workload["lane_depths"][1]),
        }
        required_shapes.update(a_shapes.values())
        required_shapes.update(lane_shapes.values())
        workload_organizations[workload["case"]] = {
            "candidate_a_shapes": a_shapes,
            "issue2_shapes": lane_shapes,
            "candidate_a_accesses": {
                "config": workload["optimized_issue5_cycles"] - 1,
                **workload["slot_counts"],
            },
            "issue2_accesses": {
                "config": workload["issue2_cycles"],
                "lane0": workload["lane_depths"][0],
                "lane1": workload["lane_depths"][1],
            },
        }

    for width in (5, 34):
        for depth in (32, 64, 128, 256, 512, 1024, 2048, 4096):
            required_shapes.add((width, depth))

    modeled: dict[str, dict[str, Any]] = {}
    for width, depth in sorted(required_shapes):
        key = macro_key(width, depth)
        if key not in modeled:
            print(f"Modeling {key}")
            modeled[key] = run_macro(cacti_root, template, width, depth)

    workload_results: dict[str, Any] = {}
    for case, organization in workload_organizations.items():
        candidate_results: dict[str, Any] = {}
        for candidate, shape_field, access_field in (
            ("candidate_a", "candidate_a_shapes", "candidate_a_accesses"),
            ("issue2", "issue2_shapes", "issue2_accesses"),
        ):
            macros = {
                name: modeled[macro_key(*shape)]
                for name, shape in organization[shape_field].items()
            }
            summary = sum_macro_metrics(macros)
            summary["dynamic_read_energy_nj"] = sum(
                macros[name]["read_energy_nj"] * accesses
                for name, accesses in organization[access_field].items()
                if name in macros
            )
            candidate_results[candidate] = {
                "macros": macros,
                "summary": summary,
            }
        a = candidate_results["candidate_a"]["summary"]
        b = candidate_results["issue2"]["summary"]
        candidate_results["comparison"] = {
            "sram_area_change": b["area_mm2"] / a["area_mm2"] - 1.0,
            "sram_read_energy_change": (
                b["dynamic_read_energy_nj"] / a["dynamic_read_energy_nj"] - 1.0
            ),
            "sram_leakage_change": b["leakage_mw"] / a["leakage_mw"] - 1.0,
        }
        workload_results[case] = candidate_results

    max_a_shapes = {
        "config": (
            5,
            max(
                organization["candidate_a_shapes"]["config"][1]
                for organization in workload_organizations.values()
            ),
        )
    }
    for slot, width in SLOT_WIDTHS.items():
        max_a_shapes[slot] = (
            width,
            max(
                organization["candidate_a_shapes"].get(slot, (width, 0))[1]
                for organization in workload_organizations.values()
            ),
        )
    max_issue2_shapes = {
        name: (
            width,
            max(
                organization["issue2_shapes"][name][1]
                for organization in workload_organizations.values()
            ),
        )
        for name, width in (("config", 5), ("lane0", 34), ("lane1", 34))
    }
    universal_a_macros = {
        name: modeled.get(macro_key(*shape))
        or run_macro(cacti_root, template, *shape)
        for name, shape in max_a_shapes.items()
    }
    universal_issue2_macros = {
        name: modeled.get(macro_key(*shape))
        or run_macro(cacti_root, template, *shape)
        for name, shape in max_issue2_shapes.items()
    }
    universal_a = sum_macro_metrics(universal_a_macros)
    universal_issue2 = sum_macro_metrics(universal_issue2_macros)
    segmented_a_macros = {
        name: optimize_segmented_macro(width, depth, modeled)
        for name, (width, depth) in max_a_shapes.items()
    }
    segmented_issue2_macros = {
        name: optimize_segmented_macro(width, depth, modeled)
        for name, (width, depth) in max_issue2_shapes.items()
    }
    segmented_a = sum_segmented_metrics(segmented_a_macros)
    segmented_issue2 = sum_segmented_metrics(segmented_issue2_macros)
    segmented_a_energy = optimize_suite_read_energy(
        segmented_a_macros,
        workload_organizations,
        "candidate_a_accesses",
    )
    segmented_issue2_energy = optimize_suite_read_energy(
        segmented_issue2_macros,
        workload_organizations,
        "issue2_accesses",
    )
    universal = {
        "candidate_a": {"shapes": max_a_shapes, "macros": universal_a_macros, "summary": universal_a},
        "issue2": {"shapes": max_issue2_shapes, "macros": universal_issue2_macros, "summary": universal_issue2},
        "comparison": {
            "sram_area_change": universal_issue2["area_mm2"] / universal_a["area_mm2"] - 1.0,
            "sram_leakage_change": universal_issue2["leakage_mw"] / universal_a["leakage_mw"] - 1.0,
        },
        "segmented": {
            "candidate_a": {
                "macros": segmented_a_macros,
                "summary": segmented_a,
                "suite_energy": segmented_a_energy,
            },
            "issue2": {
                "macros": segmented_issue2_macros,
                "summary": segmented_issue2,
                "suite_energy": segmented_issue2_energy,
            },
            "comparison": {
                "sram_area_change": segmented_issue2["area_mm2"] / segmented_a["area_mm2"] - 1.0,
                "sram_leakage_change": segmented_issue2["leakage_mw"] / segmented_a["leakage_mw"] - 1.0,
                "suite_read_energy_change": (
                    segmented_issue2_energy["suite_read_energy_nj"]
                    / segmented_a_energy["suite_read_energy_nj"]
                    - 1.0
                ),
                "macro_count_change": segmented_issue2["macro_count"] - segmented_a["macro_count"],
            },
        },
    }

    nand2_area_um2 = 2.54144
    routing_mux_bits = sum(SLOT_WIDTHS.values())
    extra_routing_ge = routing_mux_bits * 3.0
    config_decode_ge = 100.0
    candidate_a_counter_bits = sum(
        math.ceil(math.log2(depth))
        for name, (_, depth) in max_a_shapes.items()
        if name != "config"
    )
    issue2_counter_bits = sum(
        math.ceil(math.log2(depth))
        for name, (_, depth) in max_issue2_shapes.items()
        if name != "config"
    )
    counter_saving_ge = (candidate_a_counter_bits - issue2_counter_bits) * 6.0
    candidate_a_segment_mux_bits = sum(
        macro["logical_width"]
        for name, macro in segmented_a_macros.items()
        if name != "config" and macro["segment_count"] > 1
    )
    issue2_segment_mux_bits = sum(
        macro["logical_width"]
        for name, macro in segmented_issue2_macros.items()
        if name != "config" and macro["segment_count"] > 1
    )
    segment_mux_saving_ge = (
        candidate_a_segment_mux_bits - issue2_segment_mux_bits
    ) * 3.0
    estimated_incremental_ge = (
        extra_routing_ge
        + config_decode_ge
        - counter_saving_ge
        - segment_mux_saving_ge
    )
    estimated_incremental_area_mm2 = estimated_incremental_ge * nand2_area_um2 / 1e6
    estimated_total_a_mm2 = segmented_a["area_mm2"]
    estimated_total_issue2_mm2 = (
        segmented_issue2["area_mm2"] + estimated_incremental_area_mm2
    )
    logic_estimate = {
        "scope": "incremental issue2 logic relative to Candidate A; common output-hold registers and OP gating excluded",
        "assumptions": {
            "two_to_one_mux_ge_per_bit": 3.0,
            "counter_dff_plus_incrementer_ge_per_bit": 6.0,
            "config_decode_ge": config_decode_ge,
            "nand2_area_um2": nand2_area_um2,
        },
        "extra_lane_routing_bits": routing_mux_bits,
        "extra_lane_routing_ge": extra_routing_ge,
        "candidate_a_counter_bits": candidate_a_counter_bits,
        "issue2_counter_bits": issue2_counter_bits,
        "counter_saving_ge": counter_saving_ge,
        "segment_output_mux_saving_ge": segment_mux_saving_ge,
        "estimated_incremental_ge": estimated_incremental_ge,
        "estimated_incremental_area_mm2": estimated_incremental_area_mm2,
        "candidate_a_sram_plus_incremental_logic_mm2": estimated_total_a_mm2,
        "issue2_sram_plus_incremental_logic_mm2": estimated_total_issue2_mm2,
        "estimated_total_area_change": (
            estimated_total_issue2_mm2 / estimated_total_a_mm2 - 1.0
        ),
        "warning": "Analytical gate estimate only; replace with RTL synthesis before publication",
    }

    output = {
        "model": {
            "tool": "HP CACTI",
            "technology_nm": 32,
            "cache_type": "ram",
            "ports": "1 read-write",
            "depth_policy": "next power of two; double until CACTI accepts",
            "width_allocation": "whole bytes",
            "warning": "CACTI is a direction-screening model, not a foundry SRAM compiler",
        },
        "modeled_macros": modeled,
        "workloads": workload_results,
        "universal_max_configuration": universal,
        "logic_estimate": logic_estimate,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps(universal["comparison"], indent=2))


if __name__ == "__main__":
    main()
