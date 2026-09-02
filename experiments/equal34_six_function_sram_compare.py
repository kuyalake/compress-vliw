#!/usr/bin/env python3
"""Aggregate six independently provisioned X=64 function instruction SRAMs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "experiments" / "issue2_equal34_sram_compare.py"
SCHEDULE_RESULTS = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "final_priority_comparison.json"
)
CACTI_RESULTS = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "equal34_sram_compare.json"
)
OUTPUT_PATH = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "equal34_six_function_x64_sram_compare.json"
)


def load_helper() -> Any:
    spec = importlib.util.spec_from_file_location("equal34_cacti_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_metrics(total: dict[str, float], values: dict[str, float]) -> None:
    for key in (
        "area_mm2",
        "leakage_mw",
        "allocated_bits",
        "macro_count",
        "suite_read_energy_nj",
    ):
        total[key] = total.get(key, 0.0) + values.get(key, 0.0)


def main() -> None:
    helper = load_helper()
    schedules = json.loads(SCHEDULE_RESULTS.read_text())
    cacti = json.loads(CACTI_RESULTS.read_text())
    modeled = cacti["modeled_macros"]
    workloads = [
        row for row in schedules["workloads"] if row["case"].endswith("_x64")
    ]
    if len(workloads) != 6:
        raise AssertionError(f"Expected six X=64 functions, got {len(workloads)}")

    totals = {
        "candidate_a": {},
        "issue2": {},
    }
    per_function = {}

    for workload in workloads:
        a_shapes = {
            "config": (5, workload["optimized_issue5_cycles"] - 1),
            **{
                slot: (34, workload["slot_counts"][slot])
                for slot in helper.SLOT_WIDTHS
                if workload["slot_counts"][slot] > 0
            },
        }
        b_shapes = {
            "config": (5, workload["issue2_cycles"]),
            "lane0": (34, workload["lane_depths"][0]),
            "lane1": (34, workload["lane_depths"][1]),
        }
        organizations = {}
        for candidate, shapes, accesses in (
            (
                "candidate_a",
                a_shapes,
                {
                    "config": workload["optimized_issue5_cycles"] - 1,
                    **workload["slot_counts"],
                },
            ),
            (
                "issue2",
                b_shapes,
                {
                    "config": workload["issue2_cycles"],
                    "lane0": workload["lane_depths"][0],
                    "lane1": workload["lane_depths"][1],
                },
            ),
        ):
            segmented = {
                name: helper.optimize_segmented_macro(width, depth, modeled)
                for name, (width, depth) in shapes.items()
            }
            summary = helper.sum_segmented_metrics(segmented)
            energy_org = {
                workload["case"]: {
                    f"{candidate}_accesses": accesses,
                }
            }
            energy = helper.optimize_suite_read_energy(
                segmented,
                energy_org,
                f"{candidate}_accesses",
            )
            values = {
                **summary,
                "suite_read_energy_nj": energy["suite_read_energy_nj"],
            }
            organizations[candidate] = {
                "shapes": shapes,
                "macros": segmented,
                "summary": values,
            }
            add_metrics(totals[candidate], values)

        a = organizations["candidate_a"]["summary"]
        b = organizations["issue2"]["summary"]
        organizations["comparison"] = {
            "sram_area_change": b["area_mm2"] / a["area_mm2"] - 1.0,
            "sram_leakage_change": b["leakage_mw"] / a["leakage_mw"] - 1.0,
            "allocated_bits_change": (
                b["allocated_bits"] / a["allocated_bits"] - 1.0
            ),
            "read_energy_change": (
                b["suite_read_energy_nj"] / a["suite_read_energy_nj"] - 1.0
            ),
            "macro_count_change": b["macro_count"] - a["macro_count"],
        }
        per_function[workload["case"]] = organizations

    a_total = totals["candidate_a"]
    b_total = totals["issue2"]
    comparison = {
        "sram_area_change": b_total["area_mm2"] / a_total["area_mm2"] - 1.0,
        "sram_leakage_change": (
            b_total["leakage_mw"] / a_total["leakage_mw"] - 1.0
        ),
        "allocated_bits_change": (
            b_total["allocated_bits"] / a_total["allocated_bits"] - 1.0
        ),
        "read_energy_change": (
            b_total["suite_read_energy_nj"]
            / a_total["suite_read_energy_nj"]
            - 1.0
        ),
        "macro_count_change": (
            b_total["macro_count"] - a_total["macro_count"]
        ),
    }
    output = {
        "organization": {
            "function_count": 6,
            "stored_shape": "X=64",
            "policy": "one independently sized instruction SRAM organization per function",
            "segmentation": "up to two power-of-two-depth macros per logical stream",
        },
        "per_function": per_function,
        "aggregate": {
            "candidate_a": a_total,
            "issue2": b_total,
            "comparison": comparison,
        },
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(json.dumps(output["aggregate"], indent=2))


if __name__ == "__main__":
    main()
