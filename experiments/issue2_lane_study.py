#!/usr/bin/env python3
"""First-round two-issue scheduling and two-lane encoding experiment."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = ROOT / "schedule_v18_issue2.py"
BASELINE_SUMMARY_PATH = ROOT / "analysis_output_6x2" / "summary_matrix.csv"
OUTPUT_ROOT = ROOT / "analysis_output_issue2_152"

SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
SLOT_WIDTHS = (26, 26, 34, 31, 31)
OP_WIDTHS = (2, 2, 4, 4, 4)
RAW_VLIW_BITS = 152
LANE_BITS = 34
CONFIG_BITS = 5
HEADER_BITS = 256

WORKLOAD_SPECS = {
    "softmax": {"y": 512, "modes": (0, 1, 2)},
    "layernorm": {"y": 768, "modes": (0,)},
    "gelu": {"y": 3072, "modes": (2,)},
    "logsoftmax": {"y": 2048, "modes": (0, 1, 2)},
    "softplus": {"y": 1024, "modes": (0, 1, 2)},
    "logsumexp": {"y": 1024, "modes": (0, 1, 2)},
}


def load_scheduler() -> Any:
    spec = importlib.util.spec_from_file_location("schedule_v18_issue2", SCHEDULER_PATH)
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


def build_config_codebook() -> tuple[dict[tuple[int | None, int | None], int], int]:
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
    lane_assignments: list[tuple[int | None, int | None] | str] = []

    for row in schedule:
        if row[6]:
            assert not any(row[:5])
            config_stream.append(EOP_CODE)
            lane_assignments.append("eop")
            continue

        active_slots = [slot for slot, value in enumerate(row[:5]) if value != 0]
        if len(active_slots) > 2:
            raise AssertionError(f"Schedule contains {len(active_slots)} active slots")

        if not active_slots:
            assignment: tuple[int | None, int | None] = (None, None)
        elif len(active_slots) == 1:
            slot = active_slots[0]
            assignment = (slot, None) if len(lane_streams[0]) <= len(lane_streams[1]) else (None, slot)
        else:
            assignment = (active_slots[0], active_slots[1])

        for lane, slot in enumerate(assignment):
            if slot is not None:
                lane_streams[lane].append(row[slot])
        config_stream.append(CONFIG_CODES[assignment])
        lane_assignments.append(assignment)

    decoded: list[list[int]] = []
    lane_positions = [0, 0]
    for code in config_stream:
        if code == EOP_CODE:
            decoded.append([0, 0, 0, 0, 0, 0, 1])
            continue
        assignment = CONFIG_STATES[code]
        row = [0, 0, 0, 0, 0, 0, 0]
        for lane, slot in enumerate(assignment):
            if slot is not None:
                row[slot] = lane_streams[lane][lane_positions[lane]]
                lane_positions[lane] += 1
        decoded.append(row)

    assert lane_positions == [len(lane_streams[0]), len(lane_streams[1])]
    assert decoded == schedule

    return {
        "config_stream": config_stream,
        "lane_streams": lane_streams,
        "lane_assignments": lane_assignments,
        "roundtrip_bit_exact": True,
    }


def pack_slots(slot_values: list[int]) -> int:
    packed = 0
    for value, width in zip(slot_values, SLOT_WIDTHS):
        packed = (packed << width) | value
    return packed


def popcount(value: int) -> int:
    return bin(value).count("1")


def switching_analysis(schedule: list[list[int]]) -> dict[str, int | float]:
    previous_active = [0] * 5
    previous_zero_word = 0
    previous_hold_word = 0
    zero_fill_toggles = 0
    hold_toggles = 0

    for row in schedule:
        zero_slots = row[:5]
        hold_slots: list[int] = []
        for slot, (value, op_width) in enumerate(zip(row[:5], OP_WIDTHS)):
            if value != 0:
                previous_active[slot] = value
                hold_slots.append(value)
            else:
                hold_slots.append(previous_active[slot] & ~((1 << op_width) - 1))

        zero_word = (pack_slots(zero_slots) << 4) | (row[5] << 1) | row[6]
        hold_word = (pack_slots(hold_slots) << 4) | (row[5] << 1) | row[6]
        zero_fill_toggles += popcount(zero_word ^ previous_zero_word)
        hold_toggles += popcount(hold_word ^ previous_hold_word)
        previous_zero_word = zero_word
        previous_hold_word = hold_word

    reduction = 0.0 if zero_fill_toggles == 0 else 1.0 - hold_toggles / zero_fill_toggles
    return {
        "zero_fill_toggles": zero_fill_toggles,
        "hold_payload_toggles": hold_toggles,
        "toggle_reduction": reduction,
    }


def write_lane_files(case_dir: Path, encoded: dict[str, Any]) -> None:
    with (case_dir / "issue2_config.txt").open("w") as handle:
        for code in encoded["config_stream"]:
            handle.write(f"{code:02x}\n")
    for lane, stream in enumerate(encoded["lane_streams"]):
        with (case_dir / f"issue2_lane{lane}.txt").open("w") as handle:
            for value in stream:
                handle.write(f"{value:09x}\n")


def analyze_schedule(
    case_name: str,
    mode: int,
    baseline_cycles: int,
    schedule: list[list[int]],
) -> dict[str, Any]:
    encoded = encode_two_lane(schedule)
    counts = {
        name: sum(row[slot] != 0 for row in schedule)
        for slot, name in enumerate(SLOT_NAMES)
    }
    active_histogram = {
        str(active): sum(sum(value != 0 for value in row[:5]) == active for row in schedule)
        for active in range(3)
    }
    cycles = len(schedule)
    events = sum(counts.values())
    candidate_a_bits = (
        HEADER_BITS
        + CONFIG_BITS * (cycles - 1)
        + sum(counts[name] * width for name, width in zip(SLOT_NAMES, SLOT_WIDTHS))
    )
    issue2_vertical_bits = HEADER_BITS + CONFIG_BITS * cycles + LANE_BITS * events
    issue2_horizontal_bits = (CONFIG_BITS + 2 * LANE_BITS) * cycles
    lane_depths = [len(stream) for stream in encoded["lane_streams"]]
    switching = switching_analysis(schedule)

    return {
        "case": case_name,
        "mode": mode,
        "baseline_cycles": baseline_cycles,
        "issue2_cycles": cycles,
        "cycle_change": cycles / baseline_cycles - 1.0,
        "slot_counts": counts,
        "active_slot_histogram": active_histogram,
        "events": events,
        "max_active_slots": max(
            sum(value != 0 for value in row[:5])
            for row in schedule
        ),
        "lane_depths": lane_depths,
        "lane_depth_imbalance": abs(lane_depths[0] - lane_depths[1]),
        "raw_152_bits": RAW_VLIW_BITS * cycles,
        "candidate_a_bits": candidate_a_bits,
        "candidate_a_ratio": candidate_a_bits / (RAW_VLIW_BITS * cycles),
        "issue2_vertical_bits": issue2_vertical_bits,
        "issue2_vertical_ratio": issue2_vertical_bits / (RAW_VLIW_BITS * cycles),
        "issue2_overhead_vs_a": issue2_vertical_bits / candidate_a_bits - 1.0,
        "issue2_horizontal_bits": issue2_horizontal_bits,
        "issue2_horizontal_ratio": issue2_horizontal_bits / (RAW_VLIW_BITS * cycles),
        "roundtrip_bit_exact": encoded["roundtrip_bit_exact"],
        **switching,
        "_encoded": encoded,
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    scheduler = load_scheduler()
    baseline_cycles = load_baseline_cycles()
    selected_results: list[dict[str, Any]] = []
    all_mode_cycles: dict[str, dict[str, int]] = {}

    for function, spec in WORKLOAD_SPECS.items():
        for x in (32, 64):
            case_name = f"{function}_x{x}"
            mode_results: list[tuple[int, list[list[int]], Path]] = []
            all_mode_cycles[case_name] = {}

            for mode in spec["modes"]:
                mode_dir = OUTPUT_ROOT / f"{case_name}_y{spec['y']}_mode{mode}"
                mode_dir.mkdir(parents=True, exist_ok=True)
                log_path = mode_dir / "scheduler.log"
                with log_path.open("w") as log_handle, contextlib.redirect_stdout(log_handle):
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
                        out_dir=str(mode_dir),
                    )
                all_mode_cycles[case_name][str(mode)] = len(schedule)
                mode_results.append((mode, schedule, mode_dir))

            selected_mode, selected_schedule, selected_dir = min(
                mode_results,
                key=lambda item: len(item[1]),
            )
            result = analyze_schedule(
                case_name,
                selected_mode,
                baseline_cycles[case_name],
                selected_schedule,
            )
            write_lane_files(selected_dir, result["_encoded"])
            del result["_encoded"]
            selected_results.append(result)
            print(
                f"{case_name}: mode={selected_mode}, "
                f"cycles={result['issue2_cycles']} ({result['cycle_change']:+.2%}), "
                f"two-lane={result['issue2_vertical_ratio']:.2%}, "
                f"toggle={result['toggle_reduction']:.2%}"
            )

    aggregate = {
        "baseline_cycles": sum(result["baseline_cycles"] for result in selected_results),
        "issue2_cycles": sum(result["issue2_cycles"] for result in selected_results),
        "raw_152_bits": sum(result["raw_152_bits"] for result in selected_results),
        "candidate_a_bits": sum(result["candidate_a_bits"] for result in selected_results),
        "issue2_vertical_bits": sum(result["issue2_vertical_bits"] for result in selected_results),
        "issue2_horizontal_bits": sum(result["issue2_horizontal_bits"] for result in selected_results),
        "zero_fill_toggles": sum(result["zero_fill_toggles"] for result in selected_results),
        "hold_payload_toggles": sum(result["hold_payload_toggles"] for result in selected_results),
    }
    aggregate["cycle_change"] = (
        aggregate["issue2_cycles"] / aggregate["baseline_cycles"] - 1.0
    )
    aggregate["candidate_a_ratio"] = (
        aggregate["candidate_a_bits"] / aggregate["raw_152_bits"]
    )
    aggregate["issue2_vertical_ratio"] = (
        aggregate["issue2_vertical_bits"] / aggregate["raw_152_bits"]
    )
    aggregate["issue2_overhead_vs_a"] = (
        aggregate["issue2_vertical_bits"] / aggregate["candidate_a_bits"] - 1.0
    )
    aggregate["issue2_horizontal_ratio"] = (
        aggregate["issue2_horizontal_bits"] / aggregate["raw_152_bits"]
    )
    aggregate["toggle_reduction"] = (
        1.0
        - aggregate["hold_payload_toggles"] / aggregate["zero_fill_toggles"]
    )

    report = {
        "format": {
            "raw_vliw_bits": RAW_VLIW_BITS,
            "config_bits": CONFIG_BITS,
            "lane_bits": LANE_BITS,
            "normal_config_states": len(CONFIG_CODES),
            "eop_code": EOP_CODE,
        },
        "all_mode_cycles": all_mode_cycles,
        "workloads": selected_results,
        "aggregate": aggregate,
    }
    with (OUTPUT_ROOT / "issue2_lane_study.json").open("w") as handle:
        json.dump(report, handle, indent=2)

    fieldnames = [
        "case", "mode", "baseline_cycles", "issue2_cycles", "cycle_change",
        "events", "max_active_slots", "lane_depths", "lane_depth_imbalance",
        "candidate_a_bits", "candidate_a_ratio", "issue2_vertical_bits",
        "issue2_vertical_ratio", "issue2_overhead_vs_a",
        "issue2_horizontal_bits", "issue2_horizontal_ratio",
        "zero_fill_toggles", "hold_payload_toggles", "toggle_reduction",
        "roundtrip_bit_exact",
    ]
    with (OUTPUT_ROOT / "issue2_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in selected_results:
            writer.writerow({field: result[field] for field in fieldnames})

    print(
        "Aggregate: "
        f"cycles={aggregate['issue2_cycles']} ({aggregate['cycle_change']:+.2%}), "
        f"A={aggregate['candidate_a_ratio']:.2%}, "
        f"two-lane={aggregate['issue2_vertical_ratio']:.2%}, "
        f"toggle={aggregate['toggle_reduction']:.2%}"
    )


if __name__ == "__main__":
    main()
