#!/usr/bin/env python3
"""Build a fair five-issue priority-optimized reference for the 174-bit study."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = ROOT / "schedule_v19_issue2_priority_174.py"
OUTPUT_ROOT = ROOT / "analysis_output_issue5_174_priority"
ISSUE2_RESULT = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "priority_equal34_study.json"
)

PRIORITY_STRATEGIES = (
    "index",
    "shortest_latency",
    "latency",
    "critical_path",
    "critical_fanout",
    "critical_age",
)

WORKLOAD_SPECS = {
    "softmax": {"y": 512, "modes": (0, 1, 2)},
    "layernorm": {"y": 768, "modes": (0,)},
    "gelu": {"y": 3072, "modes": (2,)},
    "logsoftmax": {"y": 2048, "modes": (0, 1, 2)},
    "softplus": {"y": 1024, "modes": (0, 1, 2)},
    "logsumexp": {"y": 1024, "modes": (0, 1, 2)},
}


def load_scheduler() -> Any:
    spec = importlib.util.spec_from_file_location(
        "schedule_v19_issue2_priority_174", SCHEDULER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import scheduler from {SCHEDULER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    scheduler = load_scheduler()
    issue2 = json.loads(ISSUE2_RESULT.read_text())
    issue2_by_case = {item["case"]: item for item in issue2["workloads"]}
    all_results = []

    for function, spec in WORKLOAD_SPECS.items():
        for x in (32, 64):
            case = f"{function}_x{x}"
            for mode in spec["modes"]:
                for strategy in PRIORITY_STRATEGIES:
                    out_dir = (
                        OUTPUT_ROOT
                        / f"{case}_y{spec['y']}_mode{mode}_{strategy}"
                    )
                    out_dir.mkdir(parents=True, exist_ok=True)
                    with (out_dir / "scheduler.log").open("w") as log_handle:
                        with contextlib.redirect_stdout(log_handle):
                            schedule, _, _ = scheduler.run_scheduler(
                                FUNCTION=function,
                                X=x,
                                Y=spec["y"],
                                mode=mode,
                                NUM_VE=256,
                                VGPR_CAP=256,
                                SGPR_CAP=256,
                                MASK_FIFO=8,
                                add_rqo_option0=32,
                                add_rqo_option1=16,
                                add_rqo_option2=16,
                                MAX_ISSUE_SLOTS=5,
                                PRIORITY_STRATEGY=strategy,
                                out_dir=str(out_dir),
                            )
                    result = {
                        "case": case,
                        "mode": mode,
                        "priority_strategy": strategy,
                        "cycles": len(schedule),
                    }
                    all_results.append(result)
                    print(f"{case} mode={mode} {strategy}: {len(schedule)} cycles")

    selected = []
    for case, issue2_result in issue2_by_case.items():
        candidates = [item for item in all_results if item["case"] == case]
        winner = min(
            candidates,
            key=lambda item: (
                item["cycles"],
                PRIORITY_STRATEGIES.index(item["priority_strategy"]),
                item["mode"],
            ),
        )
        selected.append({
            **winner,
            "issue2_mode": issue2_result["mode"],
            "issue2_priority_strategy": issue2_result["priority_strategy"],
            "issue2_cycles": issue2_result["issue2_cycles"],
            "issue2_cycle_change_vs_optimized_issue5": (
                issue2_result["issue2_cycles"] / winner["cycles"] - 1.0
            ),
        })

    aggregate_issue5 = sum(item["cycles"] for item in selected)
    aggregate_issue2 = sum(item["issue2_cycles"] for item in selected)
    report = {
        "all_results": all_results,
        "workloads": selected,
        "aggregate": {
            "optimized_issue5_cycles": aggregate_issue5,
            "optimized_issue2_cycles": aggregate_issue2,
            "issue2_cycle_change_vs_optimized_issue5": (
                aggregate_issue2 / aggregate_issue5 - 1.0
            ),
        },
    }
    (OUTPUT_ROOT / "issue5_priority_reference.json").write_text(
        json.dumps(report, indent=2)
    )
    with (OUTPUT_ROOT / "issue5_vs_issue2.csv").open("w", newline="") as handle:
        fields = [
            "case",
            "mode",
            "priority_strategy",
            "cycles",
            "issue2_mode",
            "issue2_priority_strategy",
            "issue2_cycles",
            "issue2_cycle_change_vs_optimized_issue5",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in selected:
            writer.writerow({field: item[field] for field in fields})

    print(json.dumps(report["aggregate"], indent=2))


if __name__ == "__main__":
    main()
