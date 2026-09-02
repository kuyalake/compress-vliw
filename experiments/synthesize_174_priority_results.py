#!/usr/bin/env python3
"""Select, rerun, verify, and summarize the complete 174-bit priority sweep."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "analysis_output_issue2_174_priority"
SCHEDULER_PATH = ROOT / "schedule_v19_issue2_priority_174.py"
ANALYSIS_PATH = ROOT / "experiments" / "issue2_priority_equal34_study.py"

INITIAL_ISSUE2 = OUTPUT_ROOT / "priority_equal34_study.json"
INITIAL_ISSUE5 = (
    ROOT
    / "analysis_output_issue5_174_priority"
    / "issue5_priority_reference.json"
)
EXTENSION = (
    ROOT
    / "analysis_output_priority_window_174"
    / "priority_window_extension.json"
)

WORKLOAD_SPECS = {
    "softmax": {"y": 512},
    "layernorm": {"y": 768},
    "gelu": {"y": 3072},
    "logsoftmax": {"y": 2048},
    "softplus": {"y": 1024},
    "logsumexp": {"y": 1024},
}

STRATEGY_COMPLEXITY_ORDER = (
    "index",
    "shortest_latency",
    "latency",
    "critical_path",
    "critical_fanout",
    "critical_age",
    "window8_latency",
    "window16_latency",
    "window8_critical",
    "window16_critical",
    "pair_window8",
    "pair_window16",
    "pair_critical",
)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_issue2(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case": row["case"],
        "mode": row["mode"],
        "priority_strategy": row["priority_strategy"],
        "cycles": row.get("issue2_cycles", row.get("cycles")),
    }


def normalize_issue5(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "case": row["case"],
        "mode": row["mode"],
        "priority_strategy": row["priority_strategy"],
        "cycles": row["cycles"],
    }


def main() -> None:
    initial_issue2 = json.loads(INITIAL_ISSUE2.read_text())
    initial_issue5 = json.loads(INITIAL_ISSUE5.read_text())
    extension = json.loads(EXTENSION.read_text())

    issue2_rows = [
        normalize_issue2(row) for row in initial_issue2["all_results"]
    ]
    issue2_rows.extend(
        normalize_issue2(row)
        for row in extension["results"]
        if row["issue_width"] == 2
    )
    issue5_rows = [
        normalize_issue5(row) for row in initial_issue5["all_results"]
    ]
    issue5_rows.extend(
        normalize_issue5(row)
        for row in extension["results"]
        if row["issue_width"] == 5
    )

    cases = sorted({row["case"] for row in issue2_rows})
    best_issue2 = {
        case: min(
            (row for row in issue2_rows if row["case"] == case),
            key=lambda row: (
                row["cycles"],
                STRATEGY_COMPLEXITY_ORDER.index(row["priority_strategy"]),
                row["mode"],
            ),
        )
        for case in cases
    }
    best_issue5 = {
        case: min(
            (row for row in issue5_rows if row["case"] == case),
            key=lambda row: (
                row["cycles"],
                STRATEGY_COMPLEXITY_ORDER.index(row["priority_strategy"]),
                row["mode"],
            ),
        )
        for case in cases
    }

    scheduler = load_module("priority174_scheduler", SCHEDULER_PATH)
    analysis = load_module("priority174_analysis", ANALYSIS_PATH)
    final_results = []
    selected_root = OUTPUT_ROOT / "final_selected"
    selected_root.mkdir(parents=True, exist_ok=True)

    for case in cases:
        function, x_text = case.rsplit("_x", 1)
        winner2 = best_issue2[case]
        winner5 = best_issue5[case]
        out_dir = selected_root / (
            f"{case}_y{WORKLOAD_SPECS[function]['y']}"
            f"_mode{winner2['mode']}_{winner2['priority_strategy']}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "scheduler.log").open("w") as log_handle:
            with contextlib.redirect_stdout(log_handle):
                schedule, _, _ = scheduler.run_scheduler(
                    FUNCTION=function,
                    X=int(x_text),
                    Y=WORKLOAD_SPECS[function]["y"],
                    mode=winner2["mode"],
                    NUM_VE=256,
                    VGPR_CAP=256,
                    SGPR_CAP=256,
                    MASK_FIFO=8,
                    add_rqo_option0=32,
                    add_rqo_option1=16,
                    add_rqo_option2=16,
                    MAX_ISSUE_SLOTS=2,
                    PRIORITY_STRATEGY=winner2["priority_strategy"],
                    out_dir=str(out_dir),
                )
        if len(schedule) != winner2["cycles"]:
            raise AssertionError(
                f"{case}: rerun cycles {len(schedule)} != {winner2['cycles']}"
            )
        result = analysis.analyze_schedule(
            case,
            winner2["mode"],
            winner2["priority_strategy"],
            winner5["cycles"],
            schedule,
        )
        analysis.write_selected_streams(out_dir, result["_encoded"])
        del result["_encoded"]
        result["optimized_issue5_mode"] = winner5["mode"]
        result["optimized_issue5_priority_strategy"] = winner5["priority_strategy"]
        result["optimized_issue5_cycles"] = winner5["cycles"]
        result["cycle_change_vs_optimized_issue5"] = (
            result["issue2_cycles"] / winner5["cycles"] - 1.0
        )
        result["raw_issue5_174_bits"] = 174 * winner5["cycles"]
        result["candidate_a_equal34_bits"] = (
            256 + 5 * (winner5["cycles"] - 1) + 34 * result["events"]
        )
        result["candidate_a_equal34_ratio"] = (
            result["candidate_a_equal34_bits"]
            / result["raw_issue5_174_bits"]
        )
        result["issue2_overhead_vs_a"] = (
            result["issue2_vertical_bits"]
            / result["candidate_a_equal34_bits"]
            - 1.0
        )
        final_results.append(result)

    issue5_cycles = sum(row["optimized_issue5_cycles"] for row in final_results)
    issue2_cycles = sum(row["issue2_cycles"] for row in final_results)
    raw_issue5_bits = sum(row["raw_issue5_174_bits"] for row in final_results)
    raw_issue2_bits = sum(row["raw_174_bits"] for row in final_results)
    a_bits = sum(row["candidate_a_equal34_bits"] for row in final_results)
    b_bits = sum(row["issue2_vertical_bits"] for row in final_results)
    aggregate = {
        "optimized_issue5_cycles": issue5_cycles,
        "optimized_issue2_cycles": issue2_cycles,
        "cycle_change_vs_optimized_issue5": issue2_cycles / issue5_cycles - 1.0,
        "raw_issue5_174_bits": raw_issue5_bits,
        "raw_issue2_174_bits": raw_issue2_bits,
        "candidate_a_equal34_bits": a_bits,
        "candidate_a_equal34_ratio": a_bits / raw_issue5_bits,
        "issue2_vertical_bits": b_bits,
        "issue2_vertical_ratio": b_bits / raw_issue2_bits,
        "issue2_overhead_vs_a": b_bits / a_bits - 1.0,
        "roundtrip_cases": sum(row["roundtrip_bit_exact"] for row in final_results),
    }

    strategy_rows = []
    for issue_width, rows in ((2, issue2_rows), (5, issue5_rows)):
        strategies = sorted({row["priority_strategy"] for row in rows})
        global_best = issue2_cycles if issue_width == 2 else issue5_cycles
        for strategy in strategies:
            total = 0
            for case in cases:
                candidates = [
                    row
                    for row in rows
                    if row["case"] == case
                    and row["priority_strategy"] == strategy
                ]
                total += min(candidates, key=lambda row: row["cycles"])["cycles"]
            strategy_rows.append({
                "issue_width": issue_width,
                "priority_strategy": strategy,
                "best_mode_total_cycles": total,
                "overhead_vs_per_case_oracle": total / global_best - 1.0,
            })

    output = {
        "format": initial_issue2["format"],
        "search_space": {
            "issue2_strategies": sorted({
                row["priority_strategy"] for row in issue2_rows
            }),
            "issue5_strategies": sorted({
                row["priority_strategy"] for row in issue5_rows
            }),
            "issue2_runs": len(issue2_rows),
            "issue5_runs": len(issue5_rows),
        },
        "workloads": final_results,
        "strategy_summary": strategy_rows,
        "aggregate": aggregate,
    }
    (OUTPUT_ROOT / "final_priority_comparison.json").write_text(
        json.dumps(output, indent=2)
    )

    fields = [
        "case",
        "optimized_issue5_mode",
        "optimized_issue5_priority_strategy",
        "optimized_issue5_cycles",
        "mode",
        "priority_strategy",
        "issue2_cycles",
        "cycle_change_vs_optimized_issue5",
        "events",
        "lane_depths",
        "candidate_a_equal34_bits",
        "issue2_vertical_bits",
        "issue2_overhead_vs_a",
        "roundtrip_bit_exact",
    ]
    with (OUTPUT_ROOT / "final_workload_comparison.csv").open(
        "w", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in final_results:
            writer.writerow({field: row[field] for field in fields})

    with (OUTPUT_ROOT / "final_strategy_comparison.csv").open(
        "w", newline=""
    ) as handle:
        fields = [
            "issue_width",
            "priority_strategy",
            "best_mode_total_cycles",
            "overhead_vs_per_case_oracle",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(strategy_rows)

    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
