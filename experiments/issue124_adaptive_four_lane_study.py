#!/usr/bin/env python3
"""Schedule up to four operations and encode them in four rotating lanes."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import json
import argparse
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = ROOT / "schedule_v19_issue2_priority_174.py"
REFERENCE_PATH = (
    ROOT
    / "analysis_output_issue2_174_priority"
    / "final_priority_comparison.json"
)
OUTPUT_ROOT = ROOT / "analysis_output_issue124_four_lane_174"
OUTPUT_JSON = OUTPUT_ROOT / "issue124_adaptive_study.json"
OUTPUT_CSV = OUTPUT_ROOT / "issue124_workloads.csv"

SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
SLOT_BITS = 34
CONFIG_BITS = 5
EOP_CODE = 0b11111
POOL_CASES = ("gelu_x64", "softmax_x64", "layernorm_x64")

STRATEGIES = (
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

WORKLOAD_SPECS = {
    "softmax": {"y": 512, "modes": (0, 1, 2)},
    "layernorm": {"y": 768, "modes": (0,)},
    "gelu": {"y": 3072, "modes": (2,)},
    "logsoftmax": {"y": 2048, "modes": (0, 1, 2)},
    "softplus": {"y": 1024, "modes": (0, 1, 2)},
    "logsumexp": {"y": 1024, "modes": (0, 1, 2)},
}


def load_scheduler() -> Any:
    spec = importlib.util.spec_from_file_location("scheduler174", SCHEDULER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SCHEDULER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_schedule(path: Path) -> list[list[int]]:
    schedule = []
    for line in path.read_text().splitlines():
        packed = int(line, 16)
        control = packed & 0xF
        packed >>= 4
        reversed_slots = []
        for _ in SLOT_NAMES:
            reversed_slots.append(packed & ((1 << SLOT_BITS) - 1))
            packed >>= SLOT_BITS
        schedule.append(
            list(reversed(reversed_slots)) + [control >> 1, control & 1]
        )
    return schedule


def encode_rotating_lanes(schedule: list[list[int]]) -> dict[str, Any]:
    config_stream: list[int] = []
    lane_streams: list[list[int]] = [[], [], [], []]
    physical_assignments: list[list[int | None] | str] = []
    phase_stream: list[int] = []
    bank_enables: list[list[int]] = []
    phase = 0

    for row in schedule:
        phase_stream.append(phase)
        if row[6]:
            if any(row[:5]):
                raise AssertionError("EOP row contains a functional operation")
            config_stream.append(EOP_CODE)
            physical_assignments.append("eop")
            bank_enables.append([0, 0, 0, 0])
            continue
        active = [slot for slot, value in enumerate(row[:5]) if value]
        if len(active) > 4:
            raise AssertionError("Schedule exceeds four active operations")
        mask = sum(1 << slot for slot in active)
        if mask == EOP_CODE:
            raise AssertionError("Five-active mask collides with EOP")
        assignment: list[int | None] = [None, None, None, None]
        enables = [0, 0, 0, 0]
        for rank, slot in enumerate(active):
            lane = (phase + rank) % 4
            assignment[lane] = slot
            enables[lane] = 1
            lane_streams[lane].append(row[slot])
        config_stream.append(mask)
        physical_assignments.append(assignment)
        bank_enables.append(enables)
        phase = (phase + len(active)) % 4

    decoded: list[list[int]] = []
    positions = [0, 0, 0, 0]
    phase = 0
    for code in config_stream:
        if code == EOP_CODE:
            decoded.append([0, 0, 0, 0, 0, 0, 1])
            continue
        active = [slot for slot in range(5) if code & (1 << slot)]
        row = [0, 0, 0, 0, 0, 0, 0]
        for rank, slot in enumerate(active):
            lane = (phase + rank) % 4
            row[slot] = lane_streams[lane][positions[lane]]
            positions[lane] += 1
        decoded.append(row)
        phase = (phase + len(active)) % 4

    if decoded != schedule:
        raise AssertionError("Rotating four-lane roundtrip failed")
    if positions != [len(stream) for stream in lane_streams]:
        raise AssertionError("Not all rotating-lane events were consumed")
    return {
        "config_stream": config_stream,
        "lane_streams": lane_streams,
        "phase_stream": phase_stream,
        "physical_assignments": physical_assignments,
        "bank_enables": bank_enables,
        "lane_depths": [len(stream) for stream in lane_streams],
        "roundtrip_bit_exact": True,
    }


def write_streams(directory: Path, encoded: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "config_mask_5bit.txt").open("w") as handle:
        for code in encoded["config_stream"]:
            handle.write(f"{code:02x}\n")
    for lane, stream in enumerate(encoded["lane_streams"]):
        with (directory / f"lane{lane}_34bit.txt").open("w") as handle:
            for value in stream:
                handle.write(f"{value:09x}\n")


def analyze_selected(
    row: dict[str, Any],
    schedule: list[list[int]],
    reference: dict[str, Any],
) -> dict[str, Any]:
    encoded = encode_rotating_lanes(schedule)
    occupancy = {str(count): 0 for count in range(5)}
    for cycle in schedule[:-1]:
        count = sum(value != 0 for value in cycle[:5])
        occupancy[str(count)] += 1
    events = sum(
        count * cycles for count, cycles in (
            (int(key), value) for key, value in occupancy.items()
        )
    )
    capacity_modes = {
        "idle": occupancy["0"],
        "one_valid": occupancy["1"],
        "two_valid": occupancy["2"],
        "three_valid": occupancy["3"],
        "four_valid": occupancy["4"],
    }
    return {
        "case": row["case"],
        "mode": row["mode"],
        "priority_strategy": row["priority_strategy"],
        "issue124_cycles": len(schedule),
        "optimized_issue5_cycles": reference["optimized_issue5_cycles"],
        "optimized_issue2_cycles": reference["issue2_cycles"],
        "cycle_change_vs_issue5": (
            len(schedule) / reference["optimized_issue5_cycles"] - 1.0
        ),
        "cycle_change_vs_issue2": (
            len(schedule) / reference["issue2_cycles"] - 1.0
        ),
        "events": events,
        "occupancy_cycles": occupancy,
        "capacity_mode_cycles": capacity_modes,
        "lane_depths": encoded["lane_depths"],
        "max_lane_depth": max(encoded["lane_depths"]),
        "config_bits_used": CONFIG_BITS * len(schedule),
        "payload_bits_used": SLOT_BITS * events,
        "ideal_bits": CONFIG_BITS * len(schedule) + SLOT_BITS * events,
        "roundtrip_bit_exact": encoded["roundtrip_bit_exact"],
        "_encoded": encoded,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reuse-sweep",
        action="store_true",
        help="reuse existing 364 sweep schedules and regenerate encoding/results",
    )
    args = parser.parse_args()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    reference = json.loads(REFERENCE_PATH.read_text())
    reference_by_case = {row["case"]: row for row in reference["workloads"]}
    all_results: list[dict[str, Any]] = []
    schedules: dict[tuple[str, int, str], tuple[list[list[int]], Path]] = {}

    if args.reuse_sweep:
        print("[1/4] Reusing the existing 364 legal issue-4 schedules.")
        previous = json.loads(OUTPUT_JSON.read_text())
        all_results = previous["search"]["all_results"]
        for result in all_results:
            function = result["case"].rsplit("_x", 1)[0]
            spec = WORKLOAD_SPECS[function]
            directory = (
                OUTPUT_ROOT
                / "sweep"
                / (
                    f"{result['case']}_y{spec['y']}_mode{result['mode']}_"
                    f"{result['priority_strategy']}"
                )
            )
            schedule = load_schedule(directory / "schedule.txt")
            schedules[(
                result["case"],
                result["mode"],
                result["priority_strategy"],
            )] = (schedule, directory)
    else:
        scheduler = load_scheduler()
        print("[1/4] Running 13 priority strategies with MAX_ISSUE_SLOTS=4.")
        for function, spec in WORKLOAD_SPECS.items():
            for x in (32, 64):
                case = f"{function}_x{x}"
                case_runs = 0
                case_best: int | None = None
                for mode in spec["modes"]:
                    for strategy in STRATEGIES:
                        directory = (
                            OUTPUT_ROOT
                            / "sweep"
                            / f"{case}_y{spec['y']}_mode{mode}_{strategy}"
                        )
                        directory.mkdir(parents=True, exist_ok=True)
                        with (directory / "scheduler.log").open("w") as log_handle:
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
                                    MAX_ISSUE_SLOTS=4,
                                    PRIORITY_STRATEGY=strategy,
                                    out_dir=str(directory),
                                )
                        result = {
                            "case": case,
                            "mode": mode,
                            "priority_strategy": strategy,
                            "cycles": len(schedule),
                        }
                        all_results.append(result)
                        schedules[(case, mode, strategy)] = (schedule, directory)
                        case_runs += 1
                        case_best = (
                            len(schedule)
                            if case_best is None
                            else min(case_best, len(schedule))
                        )
                print(f"      {case}: {case_runs} runs, best={case_best} cycles")

    print("[2/4] Selecting the shortest legal schedule per workload.")
    selected_results = []
    selected_root = OUTPUT_ROOT / "selected"
    for case in sorted(reference_by_case):
        candidates = [row for row in all_results if row["case"] == case]
        winner = min(
            candidates,
            key=lambda row: (
                row["cycles"],
                STRATEGIES.index(row["priority_strategy"]),
                row["mode"],
            ),
        )
        schedule, _ = schedules[
            (case, winner["mode"], winner["priority_strategy"])
        ]
        analyzed = analyze_selected(
            winner, schedule, reference_by_case[case]
        )
        write_streams(selected_root / case, analyzed["_encoded"])
        del analyzed["_encoded"]
        selected_results.append(analyzed)
        print(
            f"      {case}: {analyzed['issue124_cycles']} cycles, "
            f"strategy={winner['priority_strategy']}, mode={winner['mode']}"
        )

    print("[3/4] Verifying five-bit mask and rotating-lane reconstruction.")
    if not all(row["roundtrip_bit_exact"] for row in selected_results):
        raise AssertionError("One or more selected schedules failed roundtrip")
    print(f"      {len(selected_results)}/12 schedules passed bit-exact roundtrip.")

    issue124_cycles = sum(row["issue124_cycles"] for row in selected_results)
    issue5_cycles = sum(row["optimized_issue5_cycles"] for row in selected_results)
    issue2_cycles = sum(row["optimized_issue2_cycles"] for row in selected_results)
    aggregate_modes = {
        key: sum(row["capacity_mode_cycles"][key] for row in selected_results)
        for key in selected_results[0]["capacity_mode_cycles"]
    }
    aggregate = {
        "issue124_cycles": issue124_cycles,
        "optimized_issue5_cycles": issue5_cycles,
        "optimized_issue2_cycles": issue2_cycles,
        "cycle_change_vs_issue5": issue124_cycles / issue5_cycles - 1.0,
        "cycle_change_vs_issue2": issue124_cycles / issue2_cycles - 1.0,
        "capacity_mode_cycles": aggregate_modes,
        "events": sum(row["events"] for row in selected_results),
        "roundtrip_cases": sum(
            row["roundtrip_bit_exact"] for row in selected_results
        ),
    }
    pool = [row for row in selected_results if row["case"] in POOL_CASES]
    pool_lane_depths = [
        sum(row["lane_depths"][lane] for row in pool) for lane in range(4)
    ]
    pool_summary = {
        "cases": list(POOL_CASES),
        "cycles": sum(row["issue124_cycles"] for row in pool),
        "events": sum(row["events"] for row in pool),
        "lane_depths": pool_lane_depths,
        "capacity_mode_cycles": {
            key: sum(row["capacity_mode_cycles"][key] for row in pool)
            for key in pool[0]["capacity_mode_cycles"]
        },
    }

    print("[4/4] Writing selected instruction streams and summaries.")
    output = {
        "architecture": {
            "requested_capacity_points": [1, 2, 4],
            "actual_supported_valid_operations_per_cycle": [0, 1, 2, 3, 4],
            "mode_field": None,
            "three_valid_operations": (
                "represented directly by a three-bit-set mask; exactly three "
                "payload SRAMs are enabled"
            ),
            "config": (
                "5-bit target-slot mask; 11111=EOP, 00000=empty"
            ),
            "payload_order": "ascending target-slot index",
            "lane_assignment": (
                "physical lane=(phase+payload_rank) mod 4; "
                "phase advances by valid payload count"
            ),
            "stall_rule": (
                "advance only on a ready/valid acceptance event; a stall holds "
                "config PC, phase, all lane pointers, pipeline valid/mask/phase, "
                "SRAM enables, and output registers together"
            ),
            "program_entry": (
                "reset phase to zero and load four lane base/limit descriptors"
            ),
            "control_flow_scope": (
                "linear traces; branches or loops require checkpointing config "
                "PC, phase, and four payload positions"
            ),
        },
        "search": {
            "strategies": list(STRATEGIES),
            "runs": len(all_results),
            "all_results": all_results,
        },
        "workloads": selected_results,
        "aggregate": aggregate,
        "three_x64_pool": pool_summary,
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2))
    with OUTPUT_CSV.open("w", newline="") as handle:
        fields = [
            "case",
            "mode",
            "priority_strategy",
            "optimized_issue5_cycles",
            "issue124_cycles",
            "optimized_issue2_cycles",
            "cycle_change_vs_issue5",
            "cycle_change_vs_issue2",
            "events",
            "lane_depths",
            "capacity_mode_cycles",
            "roundtrip_bit_exact",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in selected_results:
            writer.writerow({field: row[field] for field in fields})
    print(json.dumps(aggregate, indent=2))
    print(f"ADAPTIVE_ISSUE124_DONE {OUTPUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
