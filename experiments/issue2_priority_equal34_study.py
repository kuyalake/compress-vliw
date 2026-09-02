#!/usr/bin/env python3
"""Compare priority heuristics for a 174-bit equal-slot, two-issue VLIW."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = ROOT / "schedule_v19_issue2_priority_174.py"
BASELINE_SUMMARY_PATH = ROOT / "analysis_output_6x2" / "summary_matrix.csv"
OUTPUT_ROOT = ROOT / "analysis_output_issue2_174_priority"

SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
SLOT_BITS = 34
SLOT_WIDTHS = (SLOT_BITS,) * 5
OP_WIDTHS = (2, 2, 4, 4, 4)
RAW_VLIW_BITS = 174
LANE_BITS = 34
CONFIG_BITS = 5
HEADER_BITS = 256

PRIORITY_STRATEGIES = (
    "index",
    "shortest_latency",
    "latency",
    "critical_path",
    "critical_fanout",
    "critical_age",
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
    spec = importlib.util.spec_from_file_location(
        "schedule_v19_issue2_priority_174", SCHEDULER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import scheduler from {SCHEDULER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_baseline_cycles() -> dict[str, int]:
    with BASELINE_SUMMARY_PATH.open(newline="") as handle:
        return {
            row["case"]: int(row["cycles"])
            for row in csv.DictReader(handle)
        }


def build_config_codebook() -> tuple[
    dict[tuple[int | None, int | None], int], int
]:
    choices: tuple[int | None, ...] = (None, 0, 1, 2, 3, 4)
    states = [
        (lane0, lane1)
        for lane0 in choices
        for lane1 in choices
        if lane0 is None or lane1 is None or lane0 != lane1
    ]
    assert len(states) == 31
    return {state: code for code, state in enumerate(states)}, 31


CONFIG_CODES, EOP_CODE = build_config_codebook()
CONFIG_STATES = {code: state for state, code in CONFIG_CODES.items()}


def encode_two_lane(schedule: list[list[int]]) -> dict[str, Any]:
    config_stream: list[int] = []
    lane_streams: list[list[int]] = [[], []]
    assignments: list[tuple[int | None, int | None] | str] = []

    for row in schedule:
        if row[6]:
            assert not any(row[:5])
            config_stream.append(EOP_CODE)
            assignments.append("eop")
            continue

        active = [slot for slot, value in enumerate(row[:5]) if value != 0]
        if len(active) > 2:
            raise AssertionError(f"Schedule contains {len(active)} active slots")
        if not active:
            assignment: tuple[int | None, int | None] = (None, None)
        elif len(active) == 1:
            slot = active[0]
            assignment = (
                (slot, None)
                if len(lane_streams[0]) <= len(lane_streams[1])
                else (None, slot)
            )
        else:
            assignment = (active[0], active[1])

        for lane, slot in enumerate(assignment):
            if slot is not None:
                lane_streams[lane].append(row[slot])
        config_stream.append(CONFIG_CODES[assignment])
        assignments.append(assignment)

    decoded: list[list[int]] = []
    positions = [0, 0]
    for code in config_stream:
        if code == EOP_CODE:
            decoded.append([0, 0, 0, 0, 0, 0, 1])
            continue
        assignment = CONFIG_STATES[code]
        row = [0, 0, 0, 0, 0, 0, 0]
        for lane, slot in enumerate(assignment):
            if slot is not None:
                row[slot] = lane_streams[lane][positions[lane]]
                positions[lane] += 1
        decoded.append(row)

    assert positions == [len(lane_streams[0]), len(lane_streams[1])]
    assert decoded == schedule
    return {
        "config_stream": config_stream,
        "lane_streams": lane_streams,
        "assignments": assignments,
        "roundtrip_bit_exact": True,
    }


def popcount(value: int) -> int:
    return bin(value).count("1")


def pack_slots(values: list[int]) -> int:
    packed = 0
    for value in values:
        packed = (packed << SLOT_BITS) | value
    return packed


def switching_analysis(schedule: list[list[int]]) -> dict[str, int | float]:
    previous_active = [0] * 5
    previous_zero_word = 0
    previous_hold_word = 0
    zero_toggles = 0
    hold_toggles = 0

    for row in schedule:
        hold_slots: list[int] = []
        for slot, (value, op_width) in enumerate(zip(row[:5], OP_WIDTHS)):
            if value:
                previous_active[slot] = value
                hold_slots.append(value)
            else:
                hold_slots.append(
                    previous_active[slot] & ~((1 << op_width) - 1)
                )
        zero_word = (pack_slots(row[:5]) << 4) | (row[5] << 1) | row[6]
        hold_word = (pack_slots(hold_slots) << 4) | (row[5] << 1) | row[6]
        zero_toggles += popcount(zero_word ^ previous_zero_word)
        hold_toggles += popcount(hold_word ^ previous_hold_word)
        previous_zero_word = zero_word
        previous_hold_word = hold_word

    return {
        "zero_fill_toggles": zero_toggles,
        "hold_payload_toggles": hold_toggles,
        "toggle_reduction": (
            0.0 if zero_toggles == 0 else 1.0 - hold_toggles / zero_toggles
        ),
    }


def analyze_schedule(
    case: str,
    mode: int,
    strategy: str,
    baseline_cycles: int,
    schedule: list[list[int]],
) -> dict[str, Any]:
    encoded = encode_two_lane(schedule)
    counts = {
        name: sum(row[slot] != 0 for row in schedule)
        for slot, name in enumerate(SLOT_NAMES)
    }
    cycles = len(schedule)
    events = sum(counts.values())
    raw_bits = RAW_VLIW_BITS * cycles
    candidate_a_bits = HEADER_BITS + CONFIG_BITS * (cycles - 1) + SLOT_BITS * events
    issue2_bits = HEADER_BITS + CONFIG_BITS * cycles + LANE_BITS * events
    lane_depths = [len(stream) for stream in encoded["lane_streams"]]
    switching = switching_analysis(schedule)

    return {
        "case": case,
        "mode": mode,
        "priority_strategy": strategy,
        "baseline_cycles": baseline_cycles,
        "issue2_cycles": cycles,
        "cycle_change": cycles / baseline_cycles - 1.0,
        "slot_counts": counts,
        "events": events,
        "lane_depths": lane_depths,
        "lane_depth_imbalance": abs(lane_depths[0] - lane_depths[1]),
        "raw_174_bits": raw_bits,
        "candidate_a_equal34_bits": candidate_a_bits,
        "candidate_a_equal34_ratio": candidate_a_bits / raw_bits,
        "issue2_vertical_bits": issue2_bits,
        "issue2_vertical_ratio": issue2_bits / raw_bits,
        "issue2_overhead_vs_a": issue2_bits / candidate_a_bits - 1.0,
        "roundtrip_bit_exact": encoded["roundtrip_bit_exact"],
        **switching,
        "_encoded": encoded,
    }


def write_selected_streams(case_dir: Path, encoded: dict[str, Any]) -> None:
    with (case_dir / "issue2_config.txt").open("w") as handle:
        for code in encoded["config_stream"]:
            handle.write(f"{code:02x}\n")
    for lane, stream in enumerate(encoded["lane_streams"]):
        with (case_dir / f"issue2_lane{lane}.txt").open("w") as handle:
            for value in stream:
                handle.write(f"{value:09x}\n")


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = {
        "baseline_cycles": sum(item["baseline_cycles"] for item in results),
        "issue2_cycles": sum(item["issue2_cycles"] for item in results),
        "raw_174_bits": sum(item["raw_174_bits"] for item in results),
        "candidate_a_equal34_bits": sum(
            item["candidate_a_equal34_bits"] for item in results
        ),
        "issue2_vertical_bits": sum(item["issue2_vertical_bits"] for item in results),
        "zero_fill_toggles": sum(item["zero_fill_toggles"] for item in results),
        "hold_payload_toggles": sum(
            item["hold_payload_toggles"] for item in results
        ),
    }
    aggregate["cycle_change"] = (
        aggregate["issue2_cycles"] / aggregate["baseline_cycles"] - 1.0
    )
    aggregate["candidate_a_equal34_ratio"] = (
        aggregate["candidate_a_equal34_bits"] / aggregate["raw_174_bits"]
    )
    aggregate["issue2_vertical_ratio"] = (
        aggregate["issue2_vertical_bits"] / aggregate["raw_174_bits"]
    )
    aggregate["issue2_overhead_vs_a"] = (
        aggregate["issue2_vertical_bits"]
        / aggregate["candidate_a_equal34_bits"]
        - 1.0
    )
    aggregate["toggle_reduction"] = (
        1.0
        - aggregate["hold_payload_toggles"]
        / aggregate["zero_fill_toggles"]
    )
    return aggregate


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    scheduler = load_scheduler()
    baseline_cycles = load_baseline_cycles()
    all_results: list[dict[str, Any]] = []
    schedules: dict[tuple[str, int, str], tuple[list[list[int]], Path]] = {}

    for function, spec in WORKLOAD_SPECS.items():
        for x in (32, 64):
            case = f"{function}_x{x}"
            for mode in spec["modes"]:
                for strategy in PRIORITY_STRATEGIES:
                    case_dir = (
                        OUTPUT_ROOT
                        / f"{case}_y{spec['y']}_mode{mode}_{strategy}"
                    )
                    case_dir.mkdir(parents=True, exist_ok=True)
                    with (case_dir / "scheduler.log").open("w") as log_handle:
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
                                MAX_ISSUE_SLOTS=2,
                                PRIORITY_STRATEGY=strategy,
                                out_dir=str(case_dir),
                            )
                    result = analyze_schedule(
                        case,
                        mode,
                        strategy,
                        baseline_cycles[case],
                        schedule,
                    )
                    schedules[(case, mode, strategy)] = (schedule, case_dir)
                    all_results.append(result)
                    print(
                        f"{case} mode={mode} {strategy}: "
                        f"{result['issue2_cycles']} cycles"
                    )

    selected: list[dict[str, Any]] = []
    for case in baseline_cycles:
        candidates = [item for item in all_results if item["case"] == case]
        winner = min(
            candidates,
            key=lambda item: (
                item["issue2_cycles"],
                item["lane_depth_imbalance"],
                PRIORITY_STRATEGIES.index(item["priority_strategy"]),
                item["mode"],
            ),
        )
        schedule, case_dir = schedules[
            (case, winner["mode"], winner["priority_strategy"])
        ]
        write_selected_streams(case_dir, winner["_encoded"])
        selected_result = {key: value for key, value in winner.items() if key != "_encoded"}
        selected.append(selected_result)

    strategy_aggregates = {}
    for strategy in PRIORITY_STRATEGIES:
        per_case = []
        for case in baseline_cycles:
            candidates = [
                item
                for item in all_results
                if item["case"] == case and item["priority_strategy"] == strategy
            ]
            per_case.append(min(candidates, key=lambda item: (item["issue2_cycles"], item["mode"])))
        strategy_aggregates[strategy] = aggregate_results(per_case)

    aggregate = aggregate_results(selected)
    report = {
        "format": {
            "raw_vliw_bits": RAW_VLIW_BITS,
            "functional_slots": 5,
            "functional_slot_bits": SLOT_BITS,
            "control_bits": 4,
            "mem_addr_bits": 20,
            "config_bits": CONFIG_BITS,
            "lane_bits": LANE_BITS,
            "normal_config_states": len(CONFIG_CODES),
            "eop_code": EOP_CODE,
        },
        "priority_strategies": list(PRIORITY_STRATEGIES),
        "all_results": [
            {key: value for key, value in item.items() if key != "_encoded"}
            for item in all_results
        ],
        "strategy_aggregates": strategy_aggregates,
        "workloads": selected,
        "aggregate": aggregate,
    }
    (OUTPUT_ROOT / "priority_equal34_study.json").write_text(
        json.dumps(report, indent=2)
    )

    fields = [
        "case",
        "mode",
        "priority_strategy",
        "baseline_cycles",
        "issue2_cycles",
        "cycle_change",
        "events",
        "lane_depths",
        "lane_depth_imbalance",
        "candidate_a_equal34_bits",
        "candidate_a_equal34_ratio",
        "issue2_vertical_bits",
        "issue2_vertical_ratio",
        "issue2_overhead_vs_a",
        "toggle_reduction",
        "roundtrip_bit_exact",
    ]
    with (OUTPUT_ROOT / "selected_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in selected:
            writer.writerow({field: item[field] for field in fields})

    with (OUTPUT_ROOT / "strategy_summary.csv").open("w", newline="") as handle:
        fields = [
            "priority_strategy",
            "issue2_cycles",
            "cycle_change",
            "candidate_a_equal34_ratio",
            "issue2_vertical_ratio",
            "toggle_reduction",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for strategy, values in strategy_aggregates.items():
            writer.writerow({"priority_strategy": strategy, **{
                field: values[field] for field in fields[1:]
            }})

    print(
        "Best per case: "
        f"cycles={aggregate['issue2_cycles']} "
        f"({aggregate['cycle_change']:+.2%}), "
        f"A={aggregate['candidate_a_equal34_ratio']:.2%}, "
        f"issue2={aggregate['issue2_vertical_ratio']:.2%}"
    )


if __name__ == "__main__":
    main()
