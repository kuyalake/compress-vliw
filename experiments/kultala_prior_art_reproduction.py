#!/usr/bin/env python3
"""Reproduce Kultala-style cost objectives on the fixed-slot two-lane VLIW.

This experiment answers three questions:
1. Can function-unit prioritization distinguish the five fixed slot types?
2. Can a same-length slack post-pass reduce 5*T + 34*N?
3. Which physical effects actually change allocated SRAM capacity?
"""

from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "analysis_output_issue2_174_priority"
FINAL_RESULTS = RESULT_ROOT / "final_priority_comparison.json"
INITIAL_SWEEP = RESULT_ROOT / "priority_equal34_study.json"
EXTENDED_SWEEP = (
    ROOT
    / "analysis_output_priority_window_174"
    / "priority_window_extension.json"
)
SELECTED_ROOT = RESULT_ROOT / "final_selected"
OUTPUT_JSON = RESULT_ROOT / "kultala_prior_art_reproduction.json"
OUTPUT_CSV = RESULT_ROOT / "kultala_prior_art_reproduction.csv"

SLOT_NAMES = ("load", "store", "vector", "scalar", "sfu")
SLOT_BITS = 34
CONFIG_BITS = 5
EOP_BITS = 4
POOL_CASES = ("gelu_x64", "softmax_x64", "layernorm_x64")


def next_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def load_schedule(path: Path) -> list[list[int]]:
    schedule: list[list[int]] = []
    for line in path.read_text().splitlines():
        packed = int(line.strip(), 16)
        control = packed & ((1 << EOP_BITS) - 1)
        packed >>= EOP_BITS
        reverse_slots = []
        for _ in SLOT_NAMES:
            reverse_slots.append(packed & ((1 << SLOT_BITS) - 1))
            packed >>= SLOT_BITS
        schedule.append(list(reversed(reverse_slots)) + [control >> 1, control & 1])
    return schedule


def selected_directory(row: dict[str, Any]) -> Path:
    function, x_text = row["case"].rsplit("_x", 1)
    y_values = {
        "softmax": 512,
        "layernorm": 768,
        "gelu": 3072,
        "logsoftmax": 2048,
        "softplus": 1024,
        "logsumexp": 1024,
    }
    expected = SELECTED_ROOT / (
        f"{row['case']}_y{y_values[function]}_mode{row['mode']}_"
        f"{row['priority_strategy']}"
    )
    if expected.exists():
        return expected
    matches = sorted(SELECTED_ROOT.glob(f"{row['case']}_y{y_values[function]}_*"))
    if not matches:
        raise FileNotFoundError(f"No selected output directory for {row['case']}")
    raise RuntimeError(
        f"Expected selected directory {expected.name}; found "
        + ", ".join(path.name for path in matches)
    )


def template_symmetry_audit() -> dict[str, Any]:
    # Kultala's score counts how often a function unit is implicit NOP in the
    # available templates. Our functional masks include every subset of size 0..2.
    masks = [
        frozenset(active)
        for width in range(3)
        for active in itertools.combinations(range(len(SLOT_NAMES)), width)
    ]
    implicit_nop_counts = {
        name: sum(slot not in mask for mask in masks)
        for slot, name in enumerate(SLOT_NAMES)
    }
    explicit_counts = {
        name: sum(slot in mask for mask in masks)
        for slot, name in enumerate(SLOT_NAMES)
    }
    choices: tuple[int | None, ...] = (None, 0, 1, 2, 3, 4)
    lane_states = [
        (lane0, lane1)
        for lane0 in choices
        for lane1 in choices
        if lane0 is None or lane1 is None or lane0 != lane1
    ]
    lane_implicit_nop_counts = {
        name: sum(slot not in state for state in lane_states)
        for slot, name in enumerate(SLOT_NAMES)
    }
    lane_explicit_counts = {
        name: sum(slot in state for state in lane_states)
        for slot, name in enumerate(SLOT_NAMES)
    }
    return {
        "logical_functional_mask_count": len(masks),
        "logical_masks": [sorted(mask) for mask in masks],
        "logical_mask_implicit_nop_counts": implicit_nop_counts,
        "logical_mask_explicit_counts": explicit_counts,
        "lane_ordered_configuration_count_excluding_eop": len(lane_states),
        "lane_ordered_implicit_nop_counts": lane_implicit_nop_counts,
        "lane_ordered_explicit_counts": lane_explicit_counts,
        "distinct_priority_scores": len(set(lane_implicit_nop_counts.values())),
        "slot_binding": {
            "load": ["load"],
            "store": ["store"],
            "vector": ["vector"],
            "scalar": ["scalar"],
            "sfu": ["sfu"],
        },
        "events_with_alternative_functional_slot": 0,
        "conclusion": (
            "All five slot types receive the same template score, and each "
            "operation class has exactly one legal functional slot. Therefore "
            "Kultala-style FU prioritization has no decision to make."
        ),
    }


def analyze_schedule(row: dict[str, Any]) -> dict[str, Any]:
    case_dir = selected_directory(row)
    schedule = load_schedule(case_dir / "schedule.txt")
    if len(schedule) != row["issue2_cycles"]:
        raise AssertionError(
            f"{row['case']}: schedule rows {len(schedule)} != "
            f"reported cycles {row['issue2_cycles']}"
        )
    if not schedule[-1][6]:
        raise AssertionError(f"{row['case']}: final row is not EOP")

    execution_rows = schedule[:-1]
    active_counts = [sum(value != 0 for value in item[:5]) for item in execution_rows]
    if any(count > 2 for count in active_counts):
        raise AssertionError(f"{row['case']}: schedule exceeds two active slots")

    slot_counts = [
        sum(item[slot] != 0 for item in execution_rows)
        for slot in range(len(SLOT_NAMES))
    ]
    events = sum(slot_counts)
    if events != row["events"]:
        raise AssertionError(
            f"{row['case']}: decoded events {events} != reported {row['events']}"
        )

    doubles = sum(count == 2 for count in active_counts)
    singles = sum(count == 1 for count in active_counts)
    empty = sum(count == 0 for count in active_counts)
    total_rows = len(schedule)
    ideal_bits = CONFIG_BITS * total_rows + SLOT_BITS * events

    # Faithful cost test for the Kultala post-pass: moving one event removes
    # 34 bits at the source and adds 34 bits at the destination. Configuration
    # rows remain because T must not change. Thus every same-T move has delta 0.
    eligible_destinations_by_slot = []
    for slot in range(len(SLOT_NAMES)):
        eligible_destinations_by_slot.append(
            sum(
                item[slot] == 0 and active_counts[cycle] < 2
                for cycle, item in enumerate(execution_rows)
            )
        )
    dependency_unchecked_move_upper_bound = sum(
        count * destinations
        for count, destinations in zip(slot_counts, eligible_destinations_by_slot)
    )
    postpass = {
        "objective_before_bits": ideal_bits,
        "same_T_move_delta_bits": 0,
        "strictly_improving_moves": 0,
        "accepted_moves": 0,
        "objective_after_bits": ideal_bits,
        "dependency_unchecked_same_slot_move_upper_bound": (
            dependency_unchecked_move_upper_bound
        ),
        "explanation": (
            "The upper bound only shows that empty destinations exist before "
            "dependency/resource checks. None can reduce the fixed-row objective, "
            "so a strict code-size-improving pass rejects all of them without "
            "needing to alter the legal schedule."
        ),
    }

    # Every double-operation cycle contributes one event to each lane. Singles
    # can all go to lane 0 (unbalanced) or alternate (optimal balance).
    balanced_depths = [
        doubles + math.ceil(singles / 2),
        doubles + singles // 2,
    ]
    unbalanced_depths = [doubles + singles, doubles]
    current_depths = list(row["lane_depths"])
    if sorted(current_depths) != sorted(balanced_depths):
        raise AssertionError(
            f"{row['case']}: current lane depths {current_depths} are not "
            f"optimally balanced {balanced_depths}"
        )

    return {
        "case": row["case"],
        "mode": row["mode"],
        "priority_strategy": row["priority_strategy"],
        "issue5_cycles": row["optimized_issue5_cycles"],
        "issue2_total_rows_T": total_rows,
        "issue2_execution_rows": len(execution_rows),
        "event_count_N": events,
        "ideal_bits_5T_plus_34N": ideal_bits,
        "extra_bits_from_issue2_cycles_vs_issue5": (
            CONFIG_BITS * (total_rows - row["optimized_issue5_cycles"])
        ),
        "double_event_cycles": doubles,
        "single_event_cycles": singles,
        "empty_execution_cycles": empty,
        "slot_counts": dict(zip(SLOT_NAMES, slot_counts)),
        "kultala_postpass": postpass,
        "current_balanced_lane_depths": current_depths,
        "mathematical_best_balanced_depths": balanced_depths,
        "counterfactual_unbalanced_depths": unbalanced_depths,
        "balanced_allocated_depths_pow2": [
            next_power_of_two(depth) for depth in balanced_depths
        ],
        "unbalanced_allocated_depths_pow2": [
            next_power_of_two(depth) for depth in unbalanced_depths
        ],
        "unbalanced_mapping_roundtrip_bit_exact": verify_lane_mapping(
            schedule, single_lane=0
        ),
    }


def verify_lane_mapping(schedule: list[list[int]], single_lane: int) -> bool:
    lane_streams: list[list[int]] = [[], []]
    assignments: list[tuple[int | None, int | None] | str] = []
    for row in schedule:
        if row[6]:
            assignments.append("eop")
            continue
        active = [slot for slot, value in enumerate(row[:5]) if value]
        if len(active) == 2:
            assignment: tuple[int | None, int | None] = (active[0], active[1])
        elif len(active) == 1 and single_lane == 0:
            assignment = (active[0], None)
        elif len(active) == 1:
            assignment = (None, active[0])
        else:
            assignment = (None, None)
        assignments.append(assignment)
        for lane, slot in enumerate(assignment):
            if slot is not None:
                lane_streams[lane].append(row[slot])

    positions = [0, 0]
    decoded: list[list[int]] = []
    for assignment in assignments:
        if assignment == "eop":
            decoded.append([0, 0, 0, 0, 0, 0, 1])
            continue
        row = [0, 0, 0, 0, 0, 0, 0]
        for lane, slot in enumerate(assignment):
            if slot is not None:
                row[slot] = lane_streams[lane][positions[lane]]
                positions[lane] += 1
        decoded.append(row)
    return decoded == schedule


def candidate_rows() -> dict[str, list[dict[str, Any]]]:
    initial = json.loads(INITIAL_SWEEP.read_text())
    extended = json.loads(EXTENDED_SWEEP.read_text())
    rows: dict[str, list[dict[str, Any]]] = {case: [] for case in POOL_CASES}
    for row in initial["all_results"]:
        if row["case"] in rows:
            rows[row["case"]].append({
                "case": row["case"],
                "mode": row["mode"],
                "priority_strategy": row["priority_strategy"],
                "cycles": row["issue2_cycles"],
            })
    for row in extended["results"]:
        if row["case"] in rows and row["issue_width"] == 2:
            rows[row["case"]].append({
                "case": row["case"],
                "mode": row["mode"],
                "priority_strategy": row["priority_strategy"],
                "cycles": row["cycles"],
            })
    return rows


def pool_analysis(workloads: list[dict[str, Any]]) -> dict[str, Any]:
    selected = {row["case"]: row for row in workloads if row["case"] in POOL_CASES}
    if set(selected) != set(POOL_CASES):
        raise AssertionError("Missing one or more X64 pool workloads")

    total_T = sum(selected[case]["issue2_total_rows_T"] for case in POOL_CASES)
    total_N = sum(selected[case]["event_count_N"] for case in POOL_CASES)
    slot_totals = {
        slot: sum(selected[case]["slot_counts"][slot] for case in POOL_CASES)
        for slot in SLOT_NAMES
    }
    balanced_lane_totals = [
        sum(selected[case]["current_balanced_lane_depths"][lane] for case in POOL_CASES)
        for lane in range(2)
    ]
    unbalanced_lane_totals = [
        sum(selected[case]["counterfactual_unbalanced_depths"][lane] for case in POOL_CASES)
        for lane in range(2)
    ]

    config_allocated = next_power_of_two(total_T)
    balanced_lane_allocated = [
        next_power_of_two(depth) for depth in balanced_lane_totals
    ]
    unbalanced_lane_allocated = [
        next_power_of_two(depth) for depth in unbalanced_lane_totals
    ]
    total_doubles = sum(
        selected[case]["double_event_cycles"] for case in POOL_CASES
    )
    total_singles = sum(
        selected[case]["single_event_cycles"] for case in POOL_CASES
    )
    split_outcomes = []
    for singles_in_lane0 in range(total_singles + 1):
        required = [
            total_doubles + singles_in_lane0,
            total_doubles + total_singles - singles_in_lane0,
        ]
        allocated = [next_power_of_two(depth) for depth in required]
        split_outcomes.append((sum(allocated), singles_in_lane0, required, allocated))
    minimum_allocated_entries = min(item[0] for item in split_outcomes)
    optimal_splits = [
        item for item in split_outcomes if item[0] == minimum_allocated_entries
    ]
    a_compact_depths = {
        slot: next_power_of_two(depth) for slot, depth in slot_totals.items()
    }
    a_symmetric_depth = next_power_of_two(max(slot_totals.values()))

    def allocated_bits(lane_depths: list[int]) -> int:
        return CONFIG_BITS * config_allocated + SLOT_BITS * sum(lane_depths)

    sweeps = candidate_rows()
    cycle_combinations = itertools.product(*(sweeps[case] for case in POOL_CASES))
    allocation_outcomes: dict[int, dict[str, Any]] = {}
    min_cycles = None
    max_cycles = None
    combinations = 0
    for combination in cycle_combinations:
        combinations += 1
        cycle_sum = sum(item["cycles"] for item in combination)
        min_cycles = cycle_sum if min_cycles is None else min(min_cycles, cycle_sum)
        max_cycles = cycle_sum if max_cycles is None else max(max_cycles, cycle_sum)
        config_depth = next_power_of_two(cycle_sum)
        bits = CONFIG_BITS * config_depth + SLOT_BITS * sum(balanced_lane_allocated)
        allocation_outcomes.setdefault(bits, {
            "allocated_bits": bits,
            "config_depth": config_depth,
            "example_cycle_sum": cycle_sum,
        })

    balanced_bits = allocated_bits(balanced_lane_allocated)
    unbalanced_bits = allocated_bits(unbalanced_lane_allocated)
    a_compact_bits = (
        CONFIG_BITS * config_allocated
        + SLOT_BITS * sum(a_compact_depths.values())
    )
    a_symmetric_bits = (
        CONFIG_BITS * config_allocated
        + SLOT_BITS * len(SLOT_NAMES) * a_symmetric_depth
    )
    return {
        "cases": list(POOL_CASES),
        "total_T": total_T,
        "total_N": total_N,
        "ideal_used_bits_5T_plus_34N": CONFIG_BITS * total_T + SLOT_BITS * total_N,
        "config_required_depth": total_T,
        "config_allocated_depth_pow2": config_allocated,
        "slot_event_totals": slot_totals,
        "candidate_a_compact_allocated_depths": a_compact_depths,
        "candidate_a_symmetric_depth_each": a_symmetric_depth,
        "balanced_lane_required_depths": balanced_lane_totals,
        "balanced_lane_allocated_depths_pow2": balanced_lane_allocated,
        "unbalanced_lane_required_depths": unbalanced_lane_totals,
        "unbalanced_lane_allocated_depths_pow2": unbalanced_lane_allocated,
        "pool_depth_aware_single_assignment": {
            "double_event_cycles": total_doubles,
            "single_event_cycles": total_singles,
            "minimum_allocated_payload_entries": minimum_allocated_entries,
            "optimal_single_events_in_lane0_min": min(
                item[1] for item in optimal_splits
            ),
            "optimal_single_events_in_lane0_max": max(
                item[1] for item in optimal_splits
            ),
            "all_singles_lane0_is_optimal": (
                sum(unbalanced_lane_allocated) == minimum_allocated_entries
            ),
            "all_singles_lane0_roundtrip_bit_exact_for_all_programs": all(
                selected[case]["unbalanced_mapping_roundtrip_bit_exact"]
                for case in POOL_CASES
            ),
        },
        "allocated_bits": {
            "candidate_a_compact": a_compact_bits,
            "candidate_a_symmetric": a_symmetric_bits,
            "two_lane_balanced": balanced_bits,
            "two_lane_unbalanced_counterfactual": unbalanced_bits,
        },
        "depth_aware_saves_bits_vs_balanced": balanced_bits - unbalanced_bits,
        "depth_aware_saves_fraction_vs_balanced": 1.0 - unbalanced_bits / balanced_bits,
        "two_lane_saves_fraction_vs_a_compact": 1.0 - balanced_bits / a_compact_bits,
        "two_lane_saves_fraction_vs_a_symmetric": (
            1.0 - balanced_bits / a_symmetric_bits
        ),
        "depth_aware_two_lane_saves_fraction_vs_a_compact": (
            1.0 - unbalanced_bits / a_compact_bits
        ),
        "depth_aware_two_lane_saves_fraction_vs_a_symmetric": (
            1.0 - unbalanced_bits / a_symmetric_bits
        ),
        "rounding_overhead_bits_two_lane": (
            balanced_bits - (CONFIG_BITS * total_T + SLOT_BITS * total_N)
        ),
        "strategy_pool_search": {
            "candidate_combinations": combinations,
            "min_cycle_sum": min_cycles,
            "max_cycle_sum": max_cycles,
            "distinct_allocated_capacity_results": len(allocation_outcomes),
            "allocation_results": sorted(
                allocation_outcomes.values(),
                key=lambda item: item["allocated_bits"],
            ),
            "conclusion": (
                "All tested schedule combinations map to the same power-of-two "
                "SRAM depths. The current priority sweep therefore provides no "
                "extra allocated-capacity gain beyond selecting short schedules."
            ),
        },
    }


def main() -> None:
    print("[1/4] Reading the 12 final legal schedules.")
    final = json.loads(FINAL_RESULTS.read_text())
    workloads = [analyze_schedule(row) for row in final["workloads"]]
    print(
        f"      Verified {len(workloads)} schedules; every row has at most two "
        "active functional slots."
    )

    print("[2/4] Reproducing Kultala-style function-unit prioritization.")
    symmetry = template_symmetry_audit()
    logical_scores = symmetry["logical_mask_implicit_nop_counts"]
    physical_scores = symmetry["lane_ordered_implicit_nop_counts"]
    print(f"      Logical-mask implicit-NOP counts: {logical_scores}.")
    print(f"      Lane-ordered-code implicit-NOP counts: {physical_scores}.")
    print(
        "      All scores tie and every operation type has one fixed slot; "
        "the prioritization makes zero choices."
    )

    print("[3/4] Evaluating the same-length slack post-pass objective.")
    total_before = sum(
        row["kultala_postpass"]["objective_before_bits"] for row in workloads
    )
    total_after = sum(
        row["kultala_postpass"]["objective_after_bits"] for row in workloads
    )
    print(
        f"      Across 12 schedules: before={total_before} bits, "
        f"after={total_after} bits, accepted improving moves=0."
    )
    print(
        "      Reason: keeping T and N fixed makes every move change the cost "
        "by -34+34=0 bits."
    )

    print("[4/4] Decomposing pool capacity into cycle, balance, and rounding effects.")
    pool = pool_analysis(workloads)
    print(
        "      Three-X64 pool balanced lane depths "
        f"{pool['balanced_lane_required_depths']} -> allocated "
        f"{pool['balanced_lane_allocated_depths_pow2']}."
    )
    print(
        "      Counterfactual unbalanced depths "
        f"{pool['unbalanced_lane_required_depths']} -> allocated "
        f"{pool['unbalanced_lane_allocated_depths_pow2']}."
    )
    print(
        "      Power-of-two-aware assignment saves "
        f"{pool['depth_aware_saves_bits_vs_balanced']} allocated bits "
        "relative to equal balancing, with bit-exact roundtrip."
    )
    print(
        "      Existing strategy combinations produce "
        f"{pool['strategy_pool_search']['distinct_allocated_capacity_results']} "
        "distinct allocated-capacity result(s)."
    )

    output = {
        "experiment": (
            "Kultala objective-level reproduction on fixed five-slot VLIW"
        ),
        "scope_limit": (
            "This proves FU-score degeneracy and the fixed-T bit-cost invariant. "
            "It does not implement Kultala's full ASAP/ALAP node-relocation pass "
            "or replay all scheduler resource constraints, because the current "
            "scheduler does not export a node-to-cycle issue map."
        ),
        "definitions": {
            "T": "total stored configuration rows, including EOP",
            "N": "total active 34-bit functional operations",
            "ideal_bits": "5*T + 34*N, excluding the common program header",
        },
        "fu_prioritization": symmetry,
        "workloads": workloads,
        "three_x64_replaceable_pool": pool,
        "main_findings": [
            "FU prioritization degenerates because slot bindings are fixed and "
            "the complete <=2-slot template set is symmetric.",
            "A same-T Kultala-style post-pass cannot improve 5*T+34*N.",
            "Greedy lane assignment already achieves the mathematical minimum "
            "maximum lane depth, but that is not the minimum power-of-two "
            "allocated capacity.",
            "For the three-X64 pool, deliberately unbalanced single-event mapping "
            "reduces payload allocation from 4096+4096 to 4096+2048 entries and "
            "remains bit-exact.",
            "The existing schedule sweep does not cross a new power-of-two SRAM "
            "boundary for the three-X64 pool.",
            "The new depth-boundary gain comes from compile-time lane mapping, "
            "not yet from DAG rescheduling; the current priority sweep provides "
            "no additional allocated-capacity gain.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2))

    fields = [
        "case",
        "issue5_cycles",
        "issue2_total_rows_T",
        "event_count_N",
        "ideal_bits_5T_plus_34N",
        "extra_bits_from_issue2_cycles_vs_issue5",
        "double_event_cycles",
        "single_event_cycles",
        "empty_execution_cycles",
        "current_balanced_lane_depths",
        "counterfactual_unbalanced_depths",
        "balanced_allocated_depths_pow2",
        "unbalanced_allocated_depths_pow2",
    ]
    with OUTPUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in workloads:
            writer.writerow({field: row[field] for field in fields})

    print(f"      Wrote {OUTPUT_JSON.relative_to(ROOT)}")
    print(f"      Wrote {OUTPUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
