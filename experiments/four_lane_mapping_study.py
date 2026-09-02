#!/usr/bin/env python3
"""Map legal two-issue schedules onto four grouped payload lanes.

The DAG schedule is intentionally unchanged.  Four physical lanes are arranged
as two selectable groups: (lane0, lane1) and (lane2, lane3).  Each cycle selects
one group and reuses the existing ordered two-lane-to-five-slot mapping.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = ROOT / "analysis_output_issue2_174_priority"
FINAL_RESULTS = INPUT_ROOT / "final_priority_comparison.json"
SELECTED_ROOT = INPUT_ROOT / "final_selected"
OUTPUT_ROOT = ROOT / "analysis_output_four_lane_174"
OUTPUT_JSON = OUTPUT_ROOT / "four_lane_mapping_study.json"
OUTPUT_CSV = OUTPUT_ROOT / "four_lane_workloads.csv"

SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
SLOT_BITS = 34
CONTROL_BITS = 4
CONFIG_BITS = 6
EOP_CODE = 0b111111
POOL_CASES = ("gelu_x64", "softmax_x64", "layernorm_x64")


def build_local_codebook() -> tuple[
    dict[tuple[int | None, int | None], int],
    dict[int, tuple[int | None, int | None]],
]:
    choices: tuple[int | None, ...] = (None, 0, 1, 2, 3, 4)
    states = [
        (local0, local1)
        for local0 in choices
        for local1 in choices
        if local0 is None or local1 is None or local0 != local1
    ]
    assert len(states) == 31
    forward = {state: code for code, state in enumerate(states)}
    return forward, {code: state for state, code in forward.items()}


LOCAL_CODES, LOCAL_STATES = build_local_codebook()


def load_schedule(path: Path) -> list[list[int]]:
    schedule = []
    for line in path.read_text().splitlines():
        packed = int(line.strip(), 16)
        control = packed & ((1 << CONTROL_BITS) - 1)
        packed >>= CONTROL_BITS
        reversed_slots = []
        for _ in SLOT_NAMES:
            reversed_slots.append(packed & ((1 << SLOT_BITS) - 1))
            packed >>= SLOT_BITS
        schedule.append(
            list(reversed(reversed_slots)) + [control >> 1, control & 1]
        )
    return schedule


def selected_directory(row: dict[str, Any]) -> Path:
    function = row["case"].rsplit("_x", 1)[0]
    y_values = {
        "softmax": 512,
        "layernorm": 768,
        "gelu": 3072,
        "logsoftmax": 2048,
        "softplus": 1024,
        "logsumexp": 1024,
    }
    path = SELECTED_ROOT / (
        f"{row['case']}_y{y_values[function]}_mode{row['mode']}_"
        f"{row['priority_strategy']}"
    )
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def choose_general_lane(
    active_count: int, lane_counts: list[int]
) -> tuple[int, tuple[int, ...]]:
    candidates: list[tuple[tuple[int, int, int, int], int, tuple[int, ...]]] = []
    if active_count == 2:
        options = ((0, (0, 1)), (1, (2, 3)))
    elif active_count == 1:
        options = tuple((lane // 2, (lane,)) for lane in range(4))
    else:
        return 0, ()
    for group, lanes in options:
        projected = list(lane_counts)
        for lane in lanes:
            projected[lane] += 1
        score = (
            max(projected),
            sum(value * value for value in projected),
            max(projected[0], projected[1]) + max(projected[2], projected[3]),
            group,
        )
        candidates.append((score, group, lanes))
    _, group, lanes = min(candidates, key=lambda item: item[0])
    return group, lanes


def choose_pool_fitted_lane(
    active_count: int,
    lane_counts: list[int],
    fitted_state: dict[str, int],
) -> tuple[int, tuple[int, ...]]:
    if active_count == 2:
        if fitted_state["small_pair_doubles_remaining"] > 0:
            fitted_state["small_pair_doubles_remaining"] -= 1
            return 1, (2, 3)
        return 0, (0, 1)
    if active_count == 1:
        lane = 0 if lane_counts[0] <= lane_counts[1] else 1
        return 0, (lane,)
    return 0, ()


def encode_program(
    schedule: list[list[int]],
    policy: str,
    global_lane_counts: list[int],
    fitted_state: dict[str, int] | None = None,
) -> dict[str, Any]:
    config_stream: list[int] = []
    lane_streams: list[list[int]] = [[], [], [], []]
    assignments: list[tuple[int | None, ...] | str] = []
    bank_enables: list[list[int]] = []

    for row in schedule:
        if row[6]:
            config_stream.append(EOP_CODE)
            assignments.append("eop")
            bank_enables.append([0, 0, 0, 0])
            continue
        active = [slot for slot, value in enumerate(row[:5]) if value]
        if len(active) > 2:
            raise AssertionError("Input schedule exceeds two active operations")
        if policy == "general_symmetric":
            group, physical_lanes = choose_general_lane(
                len(active), global_lane_counts
            )
        elif policy == "pool_fitted":
            if fitted_state is None:
                raise ValueError("pool_fitted requires fitted_state")
            group, physical_lanes = choose_pool_fitted_lane(
                len(active), global_lane_counts, fitted_state
            )
        else:
            raise ValueError(policy)

        local_assignment: list[int | None] = [None, None]
        physical_assignment: list[int | None] = [None, None, None, None]
        enables = [0, 0, 0, 0]
        for index, slot in enumerate(active):
            lane = physical_lanes[index]
            local_lane = lane % 2
            local_assignment[local_lane] = slot
            physical_assignment[lane] = slot
            lane_streams[lane].append(row[slot])
            global_lane_counts[lane] += 1
            enables[lane] = 1

        local_state = tuple(local_assignment)
        local_code = LOCAL_CODES[local_state]
        code = (group << 5) | local_code
        if code in (31, EOP_CODE):
            raise AssertionError(f"Normal mapping used reserved code {code}")
        config_stream.append(code)
        assignments.append(tuple(physical_assignment))
        bank_enables.append(enables)

    decoded = []
    positions = [0, 0, 0, 0]
    for code in config_stream:
        if code == EOP_CODE:
            decoded.append([0, 0, 0, 0, 0, 0, 1])
            continue
        if code in (31, 32):
            raise AssertionError(f"Reserved/non-canonical config code {code}")
        group = code >> 5
        local_code = code & 0x1F
        local_state = LOCAL_STATES[local_code]
        row = [0, 0, 0, 0, 0, 0, 0]
        for local_lane, slot in enumerate(local_state):
            if slot is None:
                continue
            physical_lane = 2 * group + local_lane
            row[slot] = lane_streams[physical_lane][positions[physical_lane]]
            positions[physical_lane] += 1
        decoded.append(row)
    if decoded != schedule:
        raise AssertionError("Four-lane decode did not reproduce the schedule")
    if positions != [len(stream) for stream in lane_streams]:
        raise AssertionError("Not all lane events were consumed")

    return {
        "config_stream": config_stream,
        "lane_streams": lane_streams,
        "assignments": assignments,
        "bank_enables": bank_enables,
        "lane_depths": [len(stream) for stream in lane_streams],
        "roundtrip_bit_exact": True,
    }


def write_streams(
    output_dir: Path, encoded: dict[str, Any]
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "config_6bit.txt").open("w") as handle:
        for code in encoded["config_stream"]:
            handle.write(f"{code:02x}\n")
    for lane, stream in enumerate(encoded["lane_streams"]):
        with (output_dir / f"lane{lane}_34bit.txt").open("w") as handle:
            for value in stream:
                handle.write(f"{value:09x}\n")


def run_policy(
    rows: list[dict[str, Any]],
    policy: str,
    fitted_small_pair_doubles: int = 0,
) -> dict[str, Any]:
    lane_counts = [0, 0, 0, 0]
    fitted_state = {
        "small_pair_doubles_remaining": fitted_small_pair_doubles
    }
    workloads = []
    for row in rows:
        schedule = load_schedule(selected_directory(row) / "schedule.txt")
        before = list(lane_counts)
        encoded = encode_program(
            schedule,
            policy,
            lane_counts,
            fitted_state if policy == "pool_fitted" else None,
        )
        after = list(lane_counts)
        per_program_depths = [
            after[index] - before[index] for index in range(4)
        ]
        if per_program_depths != encoded["lane_depths"]:
            raise AssertionError("Global and program-local lane counts disagree")
        write_streams(
            OUTPUT_ROOT / policy / row["case"],
            encoded,
        )
        workloads.append({
            "case": row["case"],
            "cycles_T": len(schedule),
            "events_N": sum(per_program_depths),
            "lane_depths": per_program_depths,
            "roundtrip_bit_exact": encoded["roundtrip_bit_exact"],
            "_encoded": encoded,
        })
    return {
        "policy": policy,
        "lane_depths": lane_counts,
        "workloads": workloads,
        "roundtrip_cases": sum(
            item["roundtrip_bit_exact"] for item in workloads
        ),
        "fitted_small_pair_doubles_remaining": (
            fitted_state["small_pair_doubles_remaining"]
            if policy == "pool_fitted"
            else None
        ),
    }


def serializable_policy(result: dict[str, Any]) -> dict[str, Any]:
    clean = dict(result)
    clean["workloads"] = []
    for workload in result["workloads"]:
        item = dict(workload)
        item.pop("_encoded")
        clean["workloads"].append(item)
    return clean


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    final = json.loads(FINAL_RESULTS.read_text())
    row_by_case = {row["case"]: row for row in final["workloads"]}
    pool_rows = [row_by_case[case] for case in POOL_CASES]

    total_doubles = 0
    total_singles = 0
    for row in pool_rows:
        schedule = load_schedule(selected_directory(row) / "schedule.txt")
        counts = [sum(value != 0 for value in cycle[:5]) for cycle in schedule[:-1]]
        total_doubles += sum(count == 2 for count in counts)
        total_singles += sum(count == 1 for count in counts)
    # Put 835 double cycles (1670 events) in the shallow pair.  The remaining
    # 905 doubles plus 2286 singles exactly fill the two 2048-deep lanes.
    small_pair_doubles = 835
    if 2 * (total_doubles - small_pair_doubles) + total_singles != 4096:
        raise AssertionError("Current pool no longer matches fitted mapping")

    print("[1/3] Mapping the three X64 programs onto four symmetric lanes.")
    general = run_policy(pool_rows, "general_symmetric")
    print(f"      Required lane depths: {general['lane_depths']}")

    print("[2/3] Mapping the pool onto two 2048 + two 1024 lanes.")
    fitted = run_policy(
        pool_rows,
        "pool_fitted",
        fitted_small_pair_doubles=small_pair_doubles,
    )
    print(f"      Required lane depths: {fitted['lane_depths']}")
    if fitted["fitted_small_pair_doubles_remaining"] != 0:
        raise AssertionError("Not all planned shallow-pair doubles were placed")

    print("[3/3] Verifying deterministic reconstruction.")
    if general["roundtrip_cases"] != 3 or fitted["roundtrip_cases"] != 3:
        raise AssertionError("Roundtrip verification failed")
    print("      6/6 policy-program encodings reproduce every 174-bit schedule row.")

    output = {
        "architecture": {
            "issue_limit": 2,
            "functional_slots": list(SLOT_NAMES),
            "payload_lanes": 4,
            "lane_groups": [[0, 1], [2, 3]],
            "active_groups_per_cycle": 1,
            "config_bits": CONFIG_BITS,
            "config_format": {
                "bit_5": "lane group: 0 selects lanes 0/1, 1 selects lanes 2/3",
                "bits_4_0": "existing 31-state ordered local-lane to slot mapping",
                "eop": EOP_CODE,
                "reserved": [31, 32],
                "canonical_empty": 0,
            },
            "semantic_normal_codes": 61,
            "minimum_config_bits": 6,
            "hardware_intent": (
                "Two 34-bit 2:1 pair-selection muxes followed by the existing "
                "two-lane-to-five-slot router; no FIFO or dynamic scheduler."
            ),
            "stall_rule": (
                "A global stall must freeze the configuration PC and all four "
                "payload pointers in the same cycle."
            ),
        },
        "pool": {
            "cases": list(POOL_CASES),
            "double_cycles": total_doubles,
            "single_cycles": total_singles,
            "events": 2 * total_doubles + total_singles,
        },
        "general_symmetric": serializable_policy(general),
        "pool_fitted": serializable_policy(fitted),
        "main_findings": [
            "Four lanes do not change DAG issue cycles because the issue limit "
            "remains two; they change only physical event placement.",
            "A one-bit group selector lets the existing five-bit local mapping "
            "be reused, limiting configuration width to six bits.",
            "Both four-lane mappings decode bit-exactly to every original row.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2))

    with OUTPUT_CSV.open("w", newline="") as handle:
        fields = [
            "policy", "case", "cycles_T", "events_N", "lane_depths",
            "roundtrip_bit_exact",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in (general, fitted):
            for workload in result["workloads"]:
                writer.writerow({
                    "policy": result["policy"],
                    **{
                        field: workload[field]
                        for field in fields
                        if field not in ("policy",)
                    },
                })
    print(f"      Wrote {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"      Wrote {OUTPUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
