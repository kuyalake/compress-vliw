#!/usr/bin/env python3
"""Generate representative FRV-SFU-VLIW traces and compare compression models."""

from __future__ import annotations

import argparse
from collections import Counter
import contextlib
import csv
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
SCHEDULER_PATH = ROOT / "schedule_v17.py"

SLOT_LAYOUTS = {
    "load": [("mem_fmt", 2), ("mem_addr", 28), ("gpr_fmt", 2), ("gpr_addr", 8), ("optype", 2)],
    "store": [("mem_fmt", 2), ("mem_addr", 28), ("gpr_fmt", 2), ("gpr_addr", 8), ("optype", 2)],
    "vector": [
        ("half", 2), ("imm", 1), ("connect", 2), ("dst", 8),
        ("src1", 8), ("src0", 8), ("mask", 1), ("optype", 4),
    ],
    "scalar": [
        ("imm", 1), ("connect", 1), ("dst", 8), ("src1", 8),
        ("src0", 8), ("mask", 1), ("optype", 4),
    ],
    "sfu": [
        ("borrow", 2), ("dst", 8), ("src", 8), ("is_vector", 1),
        ("rounds", 8), ("optype", 4),
    ],
}
SLOT_NAMES = list(SLOT_LAYOUTS)
SLOT_WIDTHS = {name: sum(width for _, width in fields) for name, fields in SLOT_LAYOUTS.items()}
CONTROL_WIDTH = 4
WORD_WIDTH = sum(SLOT_WIDTHS.values()) + CONTROL_WIDTH
VERTICAL_PROFILE_BITS = 64
EVENT_GLOBAL_HEADER_BITS = 64
EVENT_SLOT_DESCRIPTOR_BITS = 64

VARIABLE_FIELDS = {
    "load": {"mem_addr", "gpr_addr"},
    "store": {"mem_addr", "gpr_addr"},
    "vector": {"dst", "src1", "src0"},
    "scalar": {"dst", "src1", "src0"},
    "sfu": {"dst", "src"},
}

WORKLOAD_SPECS = {
    "softmax": {"y": 512, "modes": [0, 1, 2]},
    "layernorm": {"y": 768, "modes": [0]},
    "gelu": {"y": 3072, "modes": [2]},
    "logsoftmax": {"y": 2048, "modes": [0, 1, 2]},
    "softplus": {"y": 1024, "modes": [0, 1, 2]},
    "logsumexp": {"y": 1024, "modes": [0, 1, 2]},
}
WORKLOADS = {
    f"{function}_x{x}": {
        "function": function,
        "x": x,
        "y": spec["y"],
        "modes": spec["modes"],
    }
    for function, spec in WORKLOAD_SPECS.items()
    for x in (32, 64)
}


def load_scheduler() -> Any:
    spec = importlib.util.spec_from_file_location("schedule_v17", SCHEDULER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import scheduler from {SCHEDULER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ceil_log2_cardinality(n: int) -> int:
    return 0 if n <= 1 else math.ceil(math.log2(n))


def unpack(value: int, layout: list[tuple[str, int]]) -> dict[str, int]:
    total = sum(width for _, width in layout)
    result: dict[str, int] = {}
    remaining = total
    for name, width in layout:
        remaining -= width
        result[name] = (value >> remaining) & ((1 << width) - 1)
    return result


def pack_fields(fields: dict[str, int], layout: list[tuple[str, int]]) -> int:
    value = 0
    for name, width in layout:
        value = (value << width) | (fields[name] & ((1 << width) - 1))
    return value


def pack_word(row: list[int]) -> int:
    widths = [SLOT_WIDTHS[name] for name in SLOT_NAMES] + [3, 1]
    word = 0
    for value, width in zip(row, widths):
        word = (word << width) | (value & ((1 << width) - 1))
    return word


def structural_signature(row: list[int]) -> tuple[Any, ...]:
    signature: list[Any] = []
    for index, slot in enumerate(SLOT_NAMES):
        value = row[index]
        if value == 0:
            signature.append(None)
            continue
        fields = unpack(value, SLOT_LAYOUTS[slot])
        signature.append(tuple(
            (name, field_value)
            for name, field_value in fields.items()
            if name not in VARIABLE_FIELDS[slot]
        ))
    signature.append((row[5], row[6]))
    return tuple(signature)


def slot_mask(row: list[int]) -> int:
    mask = 0
    for value in row[:5]:
        mask = (mask << 1) | int(value != 0)
    return (mask << 1) | int(row[5] != 0 or row[6] != 0)


def entropy_bits(values: list[int]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def mask_and_field_analysis(schedule: list[list[int]]) -> dict[str, Any]:
    masks = [slot_mask(row) for row in schedule]
    mask_counts = Counter(masks)
    field_details: list[dict[str, Any]] = []
    for slot_index, slot in enumerate(SLOT_NAMES):
        layout = SLOT_LAYOUTS[slot]
        active = [
            (cycle, unpack(row[slot_index], layout))
            for cycle, row in enumerate(schedule)
            if row[slot_index] != 0
        ]
        for field, width in layout:
            values = [fields[field] for _, fields in active]
            event_repeat_pairs = max(0, len(values) - 1)
            event_repeats = sum(
                values[index] == values[index - 1] for index in range(1, len(values))
            )
            adjacent_cycle_pairs = 0
            adjacent_cycle_repeats = 0
            for index in range(1, len(active)):
                if active[index][0] == active[index - 1][0] + 1:
                    adjacent_cycle_pairs += 1
                    adjacent_cycle_repeats += int(
                        active[index][1][field] == active[index - 1][1][field]
                    )
            value_counts = Counter(values)
            field_details.append({
                "slot": slot,
                "field": field,
                "width": width,
                "events": len(values),
                "unique_values": len(value_counts),
                "entropy_bits_per_event": entropy_bits(values),
                "most_common_value": value_counts.most_common(1)[0][0] if values else None,
                "most_common_fraction": (
                    value_counts.most_common(1)[0][1] / len(values) if values else 0.0
                ),
                "event_to_event_repeat_pairs": event_repeat_pairs,
                "event_to_event_repeat_fraction": (
                    event_repeats / event_repeat_pairs if event_repeat_pairs else 0.0
                ),
                "adjacent_cycle_pairs": adjacent_cycle_pairs,
                "adjacent_cycle_repeat_fraction": (
                    adjacent_cycle_repeats / adjacent_cycle_pairs
                    if adjacent_cycle_pairs else 0.0
                ),
            })
    weighted_active_bits = sum(
        sum(
            SLOT_WIDTHS[slot] for index, slot in enumerate(SLOT_NAMES)
            if row[index] != 0
        ) + (CONTROL_WIDTH if row[5] != 0 or row[6] != 0 else 0)
        for row in schedule
    )
    field_raw_bits = sum(
        detail["events"] * detail["width"] for detail in field_details
    )
    field_entropy_bits = sum(
        detail["events"] * detail["entropy_bits_per_event"]
        for detail in field_details
    )
    event_repeat_pairs = sum(
        detail["event_to_event_repeat_pairs"] for detail in field_details
    )
    event_repeats = sum(
        detail["event_to_event_repeat_fraction"]
        * detail["event_to_event_repeat_pairs"]
        for detail in field_details
    )
    adjacent_cycle_pairs = sum(
        detail["adjacent_cycle_pairs"] for detail in field_details
    )
    adjacent_cycle_repeats = sum(
        detail["adjacent_cycle_repeat_fraction"] * detail["adjacent_cycle_pairs"]
        for detail in field_details
    )
    return {
        "unique_masks": len(mask_counts),
        "mask_entropy_bits_per_cycle": entropy_bits(masks),
        "top_masks": [
            {
                "mask": f"{mask:06b}",
                "count": count,
                "fraction": count / len(schedule),
            }
            for mask, count in mask_counts.most_common()
        ],
        "weighted_active_payload_bits": weighted_active_bits,
        "weighted_slot_utilization": weighted_active_bits / (len(schedule) * WORD_WIDTH),
        "field_entropy_lower_bound_bits": field_entropy_bits,
        "field_entropy_fraction_of_raw": (
            field_entropy_bits / field_raw_bits if field_raw_bits else 0.0
        ),
        "event_to_event_field_repeat_fraction": (
            event_repeats / event_repeat_pairs if event_repeat_pairs else 0.0
        ),
        "adjacent_cycle_field_repeat_fraction": (
            adjacent_cycle_repeats / adjacent_cycle_pairs if adjacent_cycle_pairs else 0.0
        ),
        "field_details": field_details,
    }


def best_period(sequence: list[Any], max_period: int = 1024) -> dict[str, float | int | None]:
    if len(sequence) < 4:
        return {
            "period": 0, "match_ratio": 0.0, "longest_coverage": 0.0,
            "core_start": None, "core_end": None, "core_length": 0, "repetitions": 0.0,
        }
    best_result: dict[str, float | int | None] = {
        "period": 0, "match_ratio": 0.0, "longest_coverage": 0.0,
        "core_start": None, "core_end": None, "core_length": 0, "repetitions": 0.0,
    }
    best_key = (0.0, 0.0, 0)
    for period in range(1, min(max_period, len(sequence) // 2) + 1):
        matches = [sequence[i] == sequence[i - period] for i in range(period, len(sequence))]
        run = longest = 0
        longest_end = -1
        for offset, match in enumerate(matches):
            if match:
                run += 1
                if run > longest:
                    longest = run
                    longest_end = period + offset
            else:
                run = 0
        match_ratio = sum(matches) / len(matches)
        core_length = longest + period
        if longest < 2 * period:
            continue
        core_start = longest_end - longest + 1 - period
        core_end = longest_end + 1
        coverage = core_length / len(sequence)
        key = (coverage, match_ratio, -period)
        if key > best_key:
            best_key = key
            best_result = {
                "period": period,
                "match_ratio": match_ratio,
                "longest_coverage": coverage,
                "core_start": core_start,
                "core_end": core_end,
                "core_length": core_length,
                "repetitions": core_length / period,
            }
    return best_result


def event_timing_bits(active_cycles: list[int]) -> tuple[int, int]:
    if not active_cycles:
        return 0, 0
    deltas = [active_cycles[0] + 1] + [
        active_cycles[i] - active_cycles[i - 1] for i in range(1, len(active_cycles))
    ]
    width = ceil_log2_cardinality(max(deltas) + 1)
    return width * len(deltas), width


def event_timing_dictionary_bits(active_cycles: list[int], total_cycles: int) -> tuple[int, dict[str, Any]]:
    if not active_cycles:
        return 0, {
            "initial_cycle": None,
            "initial_cycle_bits": 0,
            "max_inter_event_gap": 0,
            "unique_inter_event_gaps": 0,
            "gap_value_width": 0,
            "gap_dictionary_bits": 0,
            "gap_index_width": 0,
            "gap_index_stream_bits": 0,
            "common_gaps": [],
        }
    gaps = [active_cycles[i] - active_cycles[i - 1] for i in range(1, len(active_cycles))]
    gap_values = sorted(set(gaps))
    index_width = ceil_log2_cardinality(len(gap_values))
    initial_width = ceil_log2_cardinality(total_cycles + 1)
    gap_value_width = ceil_log2_cardinality(max(gap_values) + 1) if gap_values else 0
    gap_dictionary_bits = len(gap_values) * gap_value_width
    gap_index_stream_bits = len(gaps) * index_width
    bits = initial_width + gap_dictionary_bits + gap_index_stream_bits
    frequencies = sorted(
        ((gap, gaps.count(gap)) for gap in gap_values),
        key=lambda item: (-item[1], item[0]),
    )
    return bits, {
        "initial_cycle": active_cycles[0],
        "initial_cycle_bits": initial_width,
        "max_inter_event_gap": max(gaps) if gaps else 0,
        "unique_inter_event_gaps": len(gap_values),
        "gap_value_width": gap_value_width,
        "gap_dictionary_bits": gap_dictionary_bits,
        "gap_index_width": index_width,
        "gap_index_stream_bits": gap_index_stream_bits,
        "common_gaps": frequencies[:6],
    }


def dictionary_bits(values: list[int], width: int) -> tuple[int, int, int]:
    if not values:
        return 0, 0, 0
    unique = sorted(set(values))
    index_width = ceil_log2_cardinality(len(unique))
    return len(unique) * width + len(values) * index_width, len(unique), index_width


def delta_dictionary_bits(values: list[int], width: int) -> tuple[int, int, int]:
    if not values:
        return 0, 0, 0
    if len(values) == 1:
        return width, 0, 0
    mask = (1 << width) - 1
    deltas = [(values[i] - values[i - 1]) & mask for i in range(1, len(values))]
    unique = sorted(set(deltas))
    index_width = ceil_log2_cardinality(len(unique))
    bits = width + len(unique) * width + len(deltas) * index_width
    return bits, len(unique), index_width


def is_modular_affine(values: list[int], width: int) -> tuple[bool, int]:
    if len(values) < 3:
        return False, 0
    mask = (1 << width) - 1
    stride = (values[1] - values[0]) & mask
    return all(((values[i] - values[i - 1]) & mask) == stride for i in range(2, len(values))), stride


def build_hybrid_event_codec(schedule: list[list[int]]) -> dict[str, Any]:
    codec: dict[str, Any] = {"slots": {}, "control_events": []}
    for slot_index, slot in enumerate(SLOT_NAMES):
        events = [(cycle, row[slot_index]) for cycle, row in enumerate(schedule) if row[slot_index] != 0]
        active_cycles = [cycle for cycle, _ in events]
        timing_deltas = ([active_cycles[0] + 1] if active_cycles else []) + [
            active_cycles[i] - active_cycles[i - 1] for i in range(1, len(active_cycles))
        ]
        decoded = [unpack(value, SLOT_LAYOUTS[slot]) for _, value in events]
        fields_codec: dict[str, Any] = {}
        for field, width in SLOT_LAYOUTS[slot]:
            values = [entry[field] for entry in decoded]
            raw_bits = len(values) * width
            dict_values = sorted(set(values))
            dict_index = {value: index for index, value in enumerate(dict_values)}
            dict_codes = [dict_index[value] for value in values]
            dict_bits = len(dict_values) * width + len(values) * ceil_log2_cardinality(len(dict_values))

            if values:
                mask = (1 << width) - 1
                deltas = [(values[i] - values[i - 1]) & mask for i in range(1, len(values))]
                delta_values = sorted(set(deltas))
                delta_index = {value: index for index, value in enumerate(delta_values)}
                delta_codes = [delta_index[value] for value in deltas]
                delta_bits = (
                    width
                    + len(delta_values) * width
                    + len(deltas) * ceil_log2_cardinality(len(delta_values))
                )
            else:
                delta_values, delta_codes, delta_bits = [], [], 0

            mode, _ = min(
                [("raw", raw_bits), ("dictionary", dict_bits), ("delta_dictionary", delta_bits)],
                key=lambda item: item[1],
            )
            if mode == "raw":
                fields_codec[field] = {"mode": mode, "width": width, "values": values}
            elif mode == "dictionary":
                fields_codec[field] = {
                    "mode": mode,
                    "width": width,
                    "table": dict_values,
                    "codes": dict_codes,
                }
            else:
                fields_codec[field] = {
                    "mode": mode,
                    "width": width,
                    "initial": values[0] if values else 0,
                    "delta_table": delta_values,
                    "codes": delta_codes,
                }
        codec["slots"][slot] = {
            "timing_deltas": timing_deltas,
            "fields": fields_codec,
        }
    codec["control_events"] = [
        (cycle, row[5], row[6])
        for cycle, row in enumerate(schedule)
        if row[5] != 0 or row[6] != 0
    ]
    return codec


def decode_hybrid_event_codec(codec: dict[str, Any], cycles: int) -> list[list[int]]:
    reconstructed = [[0, 0, 0, 0, 0, 0, 0] for _ in range(cycles)]
    for slot_index, slot in enumerate(SLOT_NAMES):
        slot_codec = codec["slots"][slot]
        event_cycles: list[int] = []
        current_cycle = -1
        for delta in slot_codec["timing_deltas"]:
            current_cycle += delta
            event_cycles.append(current_cycle)
        field_values: dict[str, list[int]] = {}
        for field, width in SLOT_LAYOUTS[slot]:
            field_codec = slot_codec["fields"][field]
            mode = field_codec["mode"]
            if mode == "raw":
                values = list(field_codec["values"])
            elif mode == "dictionary":
                values = [field_codec["table"][code] for code in field_codec["codes"]]
            else:
                values = []
                if event_cycles:
                    current = field_codec["initial"]
                    values.append(current)
                    mask = (1 << width) - 1
                    for code in field_codec["codes"]:
                        current = (current + field_codec["delta_table"][code]) & mask
                        values.append(current)
            field_values[field] = values
        for event_index, cycle in enumerate(event_cycles):
            fields = {
                field: field_values[field][event_index]
                for field, _ in SLOT_LAYOUTS[slot]
            }
            reconstructed[cycle][slot_index] = pack_fields(fields, SLOT_LAYOUTS[slot])
    for cycle, reserved, eop in codec["control_events"]:
        reconstructed[cycle][5] = reserved
        reconstructed[cycle][6] = eop
    return reconstructed


def affine_group_analysis(schedule: list[list[int]]) -> dict[str, Any]:
    total_weight = constant_weight = affine_weight = 0
    examples: list[dict[str, Any]] = []
    for slot_index, slot in enumerate(SLOT_NAMES):
        layout = SLOT_LAYOUTS[slot]
        decoded = [unpack(row[slot_index], layout) for row in schedule if row[slot_index] != 0]
        groups: dict[tuple[tuple[str, int], ...], list[dict[str, int]]] = {}
        for fields in decoded:
            key = tuple((name, value) for name, value in fields.items() if name not in VARIABLE_FIELDS[slot])
            groups.setdefault(key, []).append(fields)
        widths = dict(layout)
        for key, entries in groups.items():
            if len(entries) < 4:
                continue
            for field in VARIABLE_FIELDS[slot]:
                values = [entry[field] for entry in entries]
                total_weight += len(values)
                if len(set(values)) == 1:
                    constant_weight += len(values)
                    continue
                affine, stride = is_modular_affine(values, widths[field])
                if affine:
                    affine_weight += len(values)
                    if len(examples) < 12:
                        examples.append({
                            "slot": slot,
                            "field": field,
                            "occurrences": len(values),
                            "base": values[0],
                            "stride": stride,
                            "structure": dict(key),
                        })
    return {
        "eligible_value_occurrences": total_weight,
        "constant_coverage": constant_weight / total_weight if total_weight else 0.0,
        "affine_nonconstant_coverage": affine_weight / total_weight if total_weight else 0.0,
        "constant_or_affine_coverage": (constant_weight + affine_weight) / total_weight if total_weight else 0.0,
        "examples": examples,
    }


def fit_modular_affine(values: list[int], width: int) -> dict[str, Any]:
    if not values:
        return {"base": 0, "stride": 0, "matches": 0, "residuals": 0}
    mask = (1 << width) - 1
    if len(values) == 1:
        return {"base": values[0], "stride": 0, "matches": 1, "residuals": 0}
    deltas = [
        (values[index] - values[index - 1]) & mask
        for index in range(1, len(values))
    ]
    candidate_strides = [stride for stride, _ in Counter(deltas).most_common(8)]
    candidate_strides.append(0)
    best = (0, 0, 0)
    for stride in dict.fromkeys(candidate_strides):
        bases = [
            (value - index * stride) & mask
            for index, value in enumerate(values)
        ]
        base, _ = Counter(bases).most_common(1)[0]
        matches = sum(
            value == ((base + index * stride) & mask)
            for index, value in enumerate(values)
        )
        if (matches, -stride, -base) > (best[0], -best[2], -best[1]):
            best = (matches, base, stride)
    return {
        "base": best[1],
        "stride": best[2],
        "matches": best[0],
        "residuals": len(values) - best[0],
    }


def period_aligned_affine_analysis(
    schedule: list[list[int]], period_result: dict[str, Any]
) -> dict[str, Any]:
    period = int(period_result["period"])
    core_start = period_result["core_start"]
    core_end = period_result["core_end"]
    if period == 0 or core_start is None or core_end is None:
        return {
            "eligible_occurrences": 0,
            "matched_occurrences": 0,
            "fit_success_fraction": 0.0,
            "residual_fraction": 0.0,
            "exact_series_fraction": 0.0,
            "series": [],
        }
    details: list[dict[str, Any]] = []
    eligible = matched = exact_series = 0
    for phase in range(period):
        phase_cycles = list(range(core_start + phase, core_end, period))
        for slot_index, slot in enumerate(SLOT_NAMES):
            if not phase_cycles or schedule[phase_cycles[0]][slot_index] == 0:
                continue
            decoded = [
                unpack(schedule[cycle][slot_index], SLOT_LAYOUTS[slot])
                for cycle in phase_cycles
            ]
            for field, width in SLOT_LAYOUTS[slot]:
                if field not in VARIABLE_FIELDS[slot]:
                    continue
                values = [entry[field] for entry in decoded]
                if len(values) < 3:
                    continue
                fit = fit_modular_affine(values, width)
                eligible += len(values)
                matched += fit["matches"]
                exact_series += int(fit["residuals"] == 0)
                details.append({
                    "phase": phase,
                    "slot": slot,
                    "field": field,
                    "width": width,
                    "iterations": len(values),
                    **fit,
                    "match_fraction": fit["matches"] / len(values),
                })
    return {
        "eligible_occurrences": eligible,
        "matched_occurrences": matched,
        "fit_success_fraction": matched / eligible if eligible else 0.0,
        "residual_fraction": 1.0 - matched / eligible if eligible else 0.0,
        "exact_series_fraction": (
            exact_series / len(details) if details else 0.0
        ),
        "series": details,
    }


def payload_bandwidth_analysis(schedule: list[list[int]]) -> dict[str, Any]:
    demand = [
        sum(
            SLOT_WIDTHS[slot]
            for index, slot in enumerate(SLOT_NAMES)
            if row[index] != 0
        ) + (CONTROL_WIDTH if row[5] != 0 or row[6] != 0 else 0)
        for row in schedule
    ]
    windows: list[dict[str, Any]] = []
    for width in (1, 2, 4, 8, 16, 32, 64, 128):
        if width > len(demand):
            continue
        running = sum(demand[:width])
        maximum = running
        maximum_start = 0
        for start in range(1, len(demand) - width + 1):
            running += demand[start + width - 1] - demand[start - 1]
            if running > maximum:
                maximum = running
                maximum_start = start
        windows.append({
            "window_cycles": width,
            "max_payload_bits": maximum,
            "max_average_bits_per_cycle": maximum / width,
            "window_start": maximum_start,
        })
    average = sum(demand) / len(demand)
    fixed_bandwidth_prefill: list[dict[str, Any]] = []
    for bandwidth in (32, 64, 96, 128, 160, 184):
        cumulative = 0
        required_prefill = 0
        worst_cycle = 0
        for cycle, bits in enumerate(demand):
            cumulative += bits
            deficit = cumulative - bandwidth * (cycle + 1)
            if deficit > required_prefill:
                required_prefill = deficit
                worst_cycle = cycle
        fixed_bandwidth_prefill.append({
            "fetch_bits_per_cycle": bandwidth,
            "minimum_initial_prefill_bits": required_prefill,
            "worst_deadline_cycle": worst_cycle,
        })
    return {
        "total_payload_bits": sum(demand),
        "average_payload_bits_per_cycle": average,
        "peak_payload_bits_in_one_cycle": max(demand),
        "windows": windows,
        "fixed_bandwidth_prefill": fixed_bandwidth_prefill,
    }


def compression_models(schedule: list[list[int]]) -> dict[str, Any]:
    cycles = len(schedule)
    original_bits = cycles * WORD_WIDTH

    slot_active: dict[str, list[tuple[int, int]]] = {
        slot: [(cycle, row[index]) for cycle, row in enumerate(schedule) if row[index] != 0]
        for index, slot in enumerate(SLOT_NAMES)
    }

    slot_sparse_bits = cycles * len(SLOT_NAMES) + cycles * CONTROL_WIDTH
    slot_sparse_bits += sum(
        len(slot_active[slot]) * SLOT_WIDTHS[slot] for slot in SLOT_NAMES
    )
    control_event_count = sum(1 for row in schedule if row[5] != 0 or row[6] != 0)
    six_slot_vertical_bits = cycles * (len(SLOT_NAMES) + 1)
    six_slot_vertical_bits += sum(
        len(slot_active[slot]) * SLOT_WIDTHS[slot] for slot in SLOT_NAMES
    )
    six_slot_vertical_bits += control_event_count * CONTROL_WIDTH
    max_slot_height = max(
        [len(slot_active[slot]) for slot in SLOT_NAMES] + [control_event_count]
    )
    six_slot_vertical_padded_bits = (
        max_slot_height * WORD_WIDTH
        + cycles * (len(SLOT_NAMES) + 1)
        + VERTICAL_PROFILE_BITS
    )

    words = [pack_word(row) for row in schedule]
    byte_count = WORD_WIDTH // 8
    nonzero_bytes = sum(
        sum(1 for byte in word.to_bytes(byte_count, "big") if byte != 0)
        for word in words
    )
    byte_vertical_bits = cycles * byte_count + nonzero_bytes * 8

    all_layouts = [SLOT_LAYOUTS[name] for name in SLOT_NAMES] + [[("reserved", 3), ("eop", 1)]]
    all_values: list[list[int]] = []
    for row in schedule:
        values: list[int] = []
        for index, slot in enumerate(SLOT_NAMES):
            fields = unpack(row[index], SLOT_LAYOUTS[slot])
            values.extend(fields.values())
        values.extend([row[5], row[6]])
        all_values.append(values)
    field_widths = [width for layout in all_layouts for _, width in layout]
    natural_vertical_bits = cycles * len(field_widths)
    for values in all_values:
        natural_vertical_bits += sum(width for value, width in zip(values, field_widths) if value != 0)

    timing_bits_total = 0
    timing_dictionary_bits_total = 0
    timing_widths: dict[str, int] = {}
    timing_gap_stats: dict[str, Any] = {}
    raw_event_payload_bits = 0
    full_slot_dictionary_bits = 0
    field_dictionary_bits = 0
    field_hybrid_bits = 0
    hybrid_raw_stream_bits = 0
    hybrid_initial_value_bits = 0
    hybrid_dictionary_table_bits = 0
    hybrid_index_stream_bits = 0
    hybrid_field_descriptor_bits = 0
    hybrid_modes = {"raw": 0, "dictionary": 0, "delta_dictionary": 0}
    hybrid_field_details: list[dict[str, Any]] = []

    for slot in SLOT_NAMES:
        events = slot_active[slot]
        cycles_for_slot = [cycle for cycle, _ in events]
        payloads = [value for _, value in events]
        timing_bits, timing_width = event_timing_bits(cycles_for_slot)
        timing_dictionary_bits, gap_stats = event_timing_dictionary_bits(cycles_for_slot, cycles)
        timing_bits_total += timing_bits
        timing_dictionary_bits_total += timing_dictionary_bits
        timing_widths[slot] = timing_width
        timing_gap_stats[slot] = gap_stats
        raw_event_payload_bits += len(payloads) * SLOT_WIDTHS[slot]
        full_slot_dictionary_bits += dictionary_bits(payloads, SLOT_WIDTHS[slot])[0]

        decoded = [unpack(value, SLOT_LAYOUTS[slot]) for value in payloads]
        for field, width in SLOT_LAYOUTS[slot]:
            values = [entry[field] for entry in decoded]
            raw_bits = len(values) * width
            dict_bits = dictionary_bits(values, width)[0]
            delta_bits = delta_dictionary_bits(values, width)[0]
            field_dictionary_bits += dict_bits
            options = {
                "raw": raw_bits,
                "dictionary": dict_bits,
                "delta_dictionary": delta_bits,
            }
            mode, bits = min(options.items(), key=lambda item: item[1])
            field_hybrid_bits += bits + 18
            hybrid_field_descriptor_bits += 18
            hybrid_modes[mode] += 1
            if mode == "raw":
                table_entries = 0
                code_width = width
                hybrid_raw_stream_bits += raw_bits
            elif mode == "dictionary":
                table_entries = dictionary_bits(values, width)[1]
                code_width = dictionary_bits(values, width)[2]
                hybrid_dictionary_table_bits += table_entries * width
                hybrid_index_stream_bits += len(values) * code_width
            else:
                table_entries = delta_dictionary_bits(values, width)[1]
                code_width = delta_dictionary_bits(values, width)[2]
                hybrid_initial_value_bits += width if values else 0
                hybrid_dictionary_table_bits += table_entries * width
                hybrid_index_stream_bits += max(0, len(values) - 1) * code_width
            hybrid_field_details.append({
                "slot": slot,
                "field": field,
                "field_width": width,
                "events": len(values),
                "mode": mode,
                "table_entries": table_entries,
                "code_width": code_width,
                "encoded_bits_with_metadata": bits + 18,
                "raw_bits": raw_bits,
                "saving_fraction": 1.0 - (bits + 18) / raw_bits if raw_bits else 0.0,
            })

    control_events = [
        (cycle, (row[5] << 1) | row[6])
        for cycle, row in enumerate(schedule)
        if row[5] != 0 or row[6] != 0
    ]
    control_cycles = [cycle for cycle, _ in control_events]
    control_timing_bits, control_timing_width = event_timing_bits(control_cycles)
    control_timing_dictionary_bits, control_gap_stats = event_timing_dictionary_bits(
        control_cycles, cycles
    )
    timing_bits_total += control_timing_bits
    timing_dictionary_bits_total += control_timing_dictionary_bits
    timing_widths["control"] = control_timing_width
    timing_gap_stats["control"] = control_gap_stats
    control_payload_bits = len(control_events) * CONTROL_WIDTH

    event_metadata_bits = EVENT_GLOBAL_HEADER_BITS + (
        len(SLOT_NAMES) + 1
    ) * EVENT_SLOT_DESCRIPTOR_BITS
    raw_event_payload_bits += control_payload_bits
    field_hybrid_bits += control_payload_bits
    hybrid_raw_stream_bits += control_payload_bits

    event_raw_bits = event_metadata_bits + timing_bits_total + raw_event_payload_bits
    event_slot_dict_bits = event_metadata_bits + timing_bits_total + full_slot_dictionary_bits + control_payload_bits
    event_field_dict_bits = event_metadata_bits + timing_bits_total + field_dictionary_bits + control_payload_bits
    event_field_hybrid_bits = event_metadata_bits + timing_bits_total + field_hybrid_bits
    event_raw_gap_dictionary_bits = (
        event_metadata_bits + timing_dictionary_bits_total + raw_event_payload_bits
    )
    event_field_hybrid_gap_dictionary_bits = (
        event_metadata_bits + timing_dictionary_bits_total + field_hybrid_bits
    )

    models = {
        "original": original_bits,
        "six_slot_vertical_logical": six_slot_vertical_bits,
        "six_slot_vertical_padded_total": six_slot_vertical_padded_bits,
        "slot_sparse_per_cycle": slot_sparse_bits,
        "li_byte_vertical": byte_vertical_bits,
        "natural_field_vertical": natural_vertical_bits,
        "per_slot_event_raw": event_raw_bits,
        "per_slot_event_raw_gap_dictionary": event_raw_gap_dictionary_bits,
        "per_slot_event_full_dictionary": event_slot_dict_bits,
        "per_slot_event_field_dictionary": event_field_dict_bits,
        "per_slot_event_field_hybrid": event_field_hybrid_bits,
        "per_slot_event_field_hybrid_gap_dictionary": event_field_hybrid_gap_dictionary_bits,
    }
    return {
        "bits": models,
        "ratio_to_original": {name: bits / original_bits for name, bits in models.items()},
        "reduction_vs_li_byte": {
            name: 1.0 - bits / byte_vertical_bits for name, bits in models.items()
        },
        "reduction_vs_six_slot_vertical_padded": {
            name: 1.0 - bits / six_slot_vertical_padded_bits for name, bits in models.items()
        },
        "vertical_storage": {
            "max_slot_height": max_slot_height,
            "padded_payload_bits": max_slot_height * WORD_WIDTH,
            "ifnull_bits": cycles * (len(SLOT_NAMES) + 1),
            "profile_bits": VERTICAL_PROFILE_BITS,
        },
        "event_gap_storage": {
            "global_header_bits": EVENT_GLOBAL_HEADER_BITS,
            "slot_descriptor_bits": (len(SLOT_NAMES) + 1) * EVENT_SLOT_DESCRIPTOR_BITS,
            "initial_cycle_bits": sum(
                details["initial_cycle_bits"] for details in timing_gap_stats.values()
            ),
            "gap_dictionary_bits": sum(
                details["gap_dictionary_bits"] for details in timing_gap_stats.values()
            ),
            "gap_index_stream_bits": sum(
                details["gap_index_stream_bits"] for details in timing_gap_stats.values()
            ),
            "raw_payload_bits": raw_event_payload_bits,
        },
        "field_hybrid_storage": {
            "global_header_bits": EVENT_GLOBAL_HEADER_BITS,
            "slot_descriptor_bits": (len(SLOT_NAMES) + 1) * EVENT_SLOT_DESCRIPTOR_BITS,
            "initial_cycle_bits": sum(
                details["initial_cycle_bits"] for details in timing_gap_stats.values()
            ),
            "gap_dictionary_bits": sum(
                details["gap_dictionary_bits"] for details in timing_gap_stats.values()
            ),
            "gap_index_stream_bits": sum(
                details["gap_index_stream_bits"] for details in timing_gap_stats.values()
            ),
            "field_descriptor_bits": hybrid_field_descriptor_bits,
            "raw_field_stream_bits": hybrid_raw_stream_bits,
            "initial_field_value_bits": hybrid_initial_value_bits,
            "field_dictionary_table_bits": hybrid_dictionary_table_bits,
            "field_index_stream_bits": hybrid_index_stream_bits,
        },
        "timing_widths": timing_widths,
        "timing_gap_stats": timing_gap_stats,
        "hybrid_field_modes": hybrid_modes,
        "hybrid_field_details": hybrid_field_details,
        "nonzero_bytes": nonzero_bytes,
    }


def analyze_schedule(schedule: list[list[int]]) -> dict[str, Any]:
    cycles = len(schedule)
    slot_counts = {
        slot: sum(1 for row in schedule if row[index] != 0)
        for index, slot in enumerate(SLOT_NAMES)
    }
    concurrency = [sum(1 for value in row[:5] if value != 0) for row in schedule]
    full_period = best_period([tuple(row) for row in schedule])
    structure_period = best_period([structural_signature(row) for row in schedule])
    mask_fields = mask_and_field_analysis(schedule)
    aligned_affine = period_aligned_affine_analysis(schedule, structure_period)
    bandwidth = payload_bandwidth_analysis(schedule)
    hybrid_codec = build_hybrid_event_codec(schedule)
    reconstructed = decode_hybrid_event_codec(hybrid_codec, cycles)
    mismatch_cycles = [
        cycle for cycle, (expected, actual) in enumerate(zip(schedule, reconstructed))
        if expected != actual
    ]
    no_functional_slot_cycle_fraction = (
        sum(1 for value in concurrency if value == 0) / cycles
    )
    return {
        "cycles_including_eop": cycles,
        "slot_counts": slot_counts,
        "slot_activity": {slot: count / cycles for slot, count in slot_counts.items()},
        "average_active_slots": sum(concurrency) / cycles,
        "max_active_slots": max(concurrency),
        "no_functional_slot_cycle_fraction": no_functional_slot_cycle_fraction,
        "all_nop_cycle_fraction": no_functional_slot_cycle_fraction,
        "mask_and_fields": mask_fields,
        "full_word_period": full_period,
        "structure_period": structure_period,
        "affine_groups": affine_group_analysis(schedule),
        "period_aligned_affine": aligned_affine,
        "payload_bandwidth": bandwidth,
        "compression": compression_models(schedule),
        "hybrid_roundtrip": {
            "bit_exact": not mismatch_cycles,
            "mismatch_count": len(mismatch_cycles),
            "first_mismatch_cycle": mismatch_cycles[0] if mismatch_cycles else None,
            "verified_timing_representation": "raw_event_deltas",
            "gap_dictionary_container_serialization_verified": False,
        },
    }


def write_trace_csv(path: Path, schedule: Iterable[list[int]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["cycle", *SLOT_NAMES, "reserved", "eop", "word_hex"])
        for cycle, row in enumerate(schedule):
            writer.writerow([
                cycle,
                *(f"0x{row[index]:0{math.ceil(SLOT_WIDTHS[slot] / 4)}x}" for index, slot in enumerate(SLOT_NAMES)),
                row[5],
                row[6],
                f"{pack_word(row):046x}",
            ])


def run(output_root: Path) -> dict[str, Any]:
    scheduler = load_scheduler()
    output_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "word_width": WORD_WIDTH,
        "workloads": {},
        "notes": {
            "gelu_mode": 2,
            "layernorm_mode": 0,
            "other_workload_modes_tested": [0, 1, 2],
            "equivalence_target": "cycle-level effective behavior; bit identity used only for trace reconstruction measurements",
        },
    }

    for case_name, config in WORKLOADS.items():
        workload = config["function"]
        mode_results: dict[int, dict[str, Any]] = {}
        for mode in config["modes"]:
            run_dir = output_root / f"{case_name}_y{config['y']}_mode{mode}"
            run_dir.mkdir(parents=True, exist_ok=True)
            log_path = run_dir / "scheduler.log"
            with log_path.open("w") as log, contextlib.redirect_stdout(log):
                schedule, performance, total_exec_cycles = scheduler.run_scheduler(
                    FUNCTION=workload,
                    X=config["x"],
                    Y=config["y"],
                    mode=mode,
                    NUM_VE=256,
                    VGPR_CAP=256,
                    SGPR_CAP=256,
                    MASK_FIFO=8,
                    add_rqo_option0=32,
                    add_rqo_option1=16,
                    add_rqo_option2=16,
                    out_dir=str(run_dir),
                )
            mode_results[mode] = {
                "schedule": schedule,
                "performance": performance,
                "total_exec_cycles": total_exec_cycles,
            }

        best_mode = min(mode_results, key=lambda mode: len(mode_results[mode]["schedule"]))
        best = mode_results[best_mode]
        trace_path = output_root / f"{case_name}_y{config['y']}_best_trace.csv"
        write_trace_csv(trace_path, best["schedule"])
        summary["workloads"][case_name] = {
            "function": workload,
            "shape": [config["x"], config["y"]],
            "mode_cycles": {
                str(mode): len(result["schedule"]) for mode, result in mode_results.items()
            },
            "selected_mode": best_mode,
            "trace_csv": str(trace_path),
            "analysis": analyze_schedule(best["schedule"]),
        }

    matrix_path = output_root / "summary_matrix.csv"
    with matrix_path.open("w", newline="") as handle:
        fieldnames = [
            "case", "function", "x", "y", "selected_mode", "cycles",
            "load_events", "store_events", "vector_events", "scalar_events", "sfu_events",
            "average_active_slots", "weighted_slot_utilization",
            "no_functional_slot_cycle_fraction",
            "unique_masks", "mask_entropy_bits_per_cycle",
            "field_entropy_fraction_of_raw", "event_to_event_field_repeat_fraction",
            "adjacent_cycle_field_repeat_fraction",
            "structure_period", "structure_period_coverage", "structure_core_start",
            "structure_core_end", "structure_repetitions",
            "period_aligned_affine_fit", "period_aligned_affine_residual",
            "average_payload_bits_per_cycle", "peak_payload_bits_in_one_cycle",
            "constant_or_affine_coverage",
            "vertical_max_slot_height", "six_slot_vertical_logical_ratio",
            "six_slot_vertical_padded_total_ratio", "li_byte_vertical_ratio",
            "event_raw_ratio", "event_raw_reduction_vs_padded_vertical",
            "hybrid_ratio", "hybrid_reduction_vs_padded_vertical", "roundtrip_bit_exact",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for case_name, result in summary["workloads"].items():
            analysis = result["analysis"]
            compression = analysis["compression"]
            counts = analysis["slot_counts"]
            writer.writerow({
                "case": case_name,
                "function": result["function"],
                "x": result["shape"][0],
                "y": result["shape"][1],
                "selected_mode": result["selected_mode"],
                "cycles": analysis["cycles_including_eop"],
                "load_events": counts["load"],
                "store_events": counts["store"],
                "vector_events": counts["vector"],
                "scalar_events": counts["scalar"],
                "sfu_events": counts["sfu"],
                "average_active_slots": f"{analysis['average_active_slots']:.6f}",
                "weighted_slot_utilization": f"{analysis['mask_and_fields']['weighted_slot_utilization']:.6f}",
                "no_functional_slot_cycle_fraction": f"{analysis['no_functional_slot_cycle_fraction']:.6f}",
                "unique_masks": analysis["mask_and_fields"]["unique_masks"],
                "mask_entropy_bits_per_cycle": f"{analysis['mask_and_fields']['mask_entropy_bits_per_cycle']:.6f}",
                "field_entropy_fraction_of_raw": f"{analysis['mask_and_fields']['field_entropy_fraction_of_raw']:.6f}",
                "event_to_event_field_repeat_fraction": f"{analysis['mask_and_fields']['event_to_event_field_repeat_fraction']:.6f}",
                "adjacent_cycle_field_repeat_fraction": f"{analysis['mask_and_fields']['adjacent_cycle_field_repeat_fraction']:.6f}",
                "structure_period": analysis["structure_period"]["period"],
                "structure_period_coverage": f"{analysis['structure_period']['longest_coverage']:.6f}",
                "structure_core_start": analysis["structure_period"]["core_start"],
                "structure_core_end": analysis["structure_period"]["core_end"],
                "structure_repetitions": f"{analysis['structure_period']['repetitions']:.6f}",
                "period_aligned_affine_fit": f"{analysis['period_aligned_affine']['fit_success_fraction']:.6f}",
                "period_aligned_affine_residual": f"{analysis['period_aligned_affine']['residual_fraction']:.6f}",
                "average_payload_bits_per_cycle": f"{analysis['payload_bandwidth']['average_payload_bits_per_cycle']:.6f}",
                "peak_payload_bits_in_one_cycle": analysis["payload_bandwidth"]["peak_payload_bits_in_one_cycle"],
                "constant_or_affine_coverage": f"{analysis['affine_groups']['constant_or_affine_coverage']:.6f}",
                "vertical_max_slot_height": compression["vertical_storage"]["max_slot_height"],
                "six_slot_vertical_logical_ratio": f"{compression['ratio_to_original']['six_slot_vertical_logical']:.6f}",
                "six_slot_vertical_padded_total_ratio": f"{compression['ratio_to_original']['six_slot_vertical_padded_total']:.6f}",
                "li_byte_vertical_ratio": f"{compression['ratio_to_original']['li_byte_vertical']:.6f}",
                "event_raw_ratio": f"{compression['ratio_to_original']['per_slot_event_raw_gap_dictionary']:.6f}",
                "event_raw_reduction_vs_padded_vertical": f"{compression['reduction_vs_six_slot_vertical_padded']['per_slot_event_raw_gap_dictionary']:.6f}",
                "hybrid_ratio": f"{compression['ratio_to_original']['per_slot_event_field_hybrid_gap_dictionary']:.6f}",
                "hybrid_reduction_vs_padded_vertical": f"{compression['reduction_vs_six_slot_vertical_padded']['per_slot_event_field_hybrid_gap_dictionary']:.6f}",
                "roundtrip_bit_exact": analysis["hybrid_roundtrip"]["bit_exact"],
            })

    breakdown_specs = {
        "original_storage.csv": (
            ["case", "cycles", "word_width_bits", "total_bits", "total_bytes"],
            lambda case, result, compression: {
                "case": case,
                "cycles": result["analysis"]["cycles_including_eop"],
                "word_width_bits": WORD_WIDTH,
                "total_bits": compression["bits"]["original"],
                "total_bytes": f"{compression['bits']['original'] / 8:.3f}",
            },
        ),
        "li_vertical_padded_storage.csv": (
            [
                "case", "original_bits", "max_slot_height", "padded_payload_bits",
                "ifnull_bits", "profile_bits", "total_bits", "ratio_to_original",
            ],
            lambda case, result, compression: {
                "case": case,
                "original_bits": compression["bits"]["original"],
                **compression["vertical_storage"],
                "total_bits": compression["bits"]["six_slot_vertical_padded_total"],
                "ratio_to_original": f"{compression['ratio_to_original']['six_slot_vertical_padded_total']:.6f}",
            },
        ),
        "slot_event_gap_dictionary_storage.csv": (
            [
                "case", "original_bits", "global_header_bits", "slot_descriptor_bits",
                "initial_cycle_bits", "gap_dictionary_bits", "gap_index_stream_bits",
                "raw_payload_bits", "total_bits", "ratio_to_original",
                "reduction_vs_li_padded",
            ],
            lambda case, result, compression: {
                "case": case,
                "original_bits": compression["bits"]["original"],
                **compression["event_gap_storage"],
                "total_bits": compression["bits"]["per_slot_event_raw_gap_dictionary"],
                "ratio_to_original": f"{compression['ratio_to_original']['per_slot_event_raw_gap_dictionary']:.6f}",
                "reduction_vs_li_padded": f"{compression['reduction_vs_six_slot_vertical_padded']['per_slot_event_raw_gap_dictionary']:.6f}",
            },
        ),
        "field_hybrid_storage.csv": (
            [
                "case", "original_bits", "global_header_bits", "slot_descriptor_bits",
                "initial_cycle_bits", "gap_dictionary_bits", "gap_index_stream_bits",
                "field_descriptor_bits", "raw_field_stream_bits", "initial_field_value_bits",
                "field_dictionary_table_bits", "field_index_stream_bits", "total_bits",
                "ratio_to_original", "reduction_vs_li_padded",
            ],
            lambda case, result, compression: {
                "case": case,
                "original_bits": compression["bits"]["original"],
                **compression["field_hybrid_storage"],
                "total_bits": compression["bits"]["per_slot_event_field_hybrid_gap_dictionary"],
                "ratio_to_original": f"{compression['ratio_to_original']['per_slot_event_field_hybrid_gap_dictionary']:.6f}",
                "reduction_vs_li_padded": f"{compression['reduction_vs_six_slot_vertical_padded']['per_slot_event_field_hybrid_gap_dictionary']:.6f}",
            },
        ),
    }
    for filename, (fieldnames, make_row) in breakdown_specs.items():
        with (output_root / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for case_name, result in summary["workloads"].items():
                compression = result["analysis"]["compression"]
                writer.writerow(make_row(case_name, result, compression))

    trace_tables: dict[str, tuple[list[str], list[dict[str, Any]]]] = {
        "mask_distribution.csv": (
            ["case", "mask", "count", "fraction"],
            [
                {"case": case_name, **entry}
                for case_name, result in summary["workloads"].items()
                for entry in result["analysis"]["mask_and_fields"]["top_masks"]
            ],
        ),
        "field_statistics.csv": (
            [
                "case", "slot", "field", "width", "events", "unique_values",
                "entropy_bits_per_event", "most_common_value", "most_common_fraction",
                "event_to_event_repeat_pairs", "event_to_event_repeat_fraction",
                "adjacent_cycle_pairs", "adjacent_cycle_repeat_fraction",
            ],
            [
                {"case": case_name, **entry}
                for case_name, result in summary["workloads"].items()
                for entry in result["analysis"]["mask_and_fields"]["field_details"]
            ],
        ),
        "period_analysis.csv": (
            [
                "case", "signature", "period", "autocorrelation_match_ratio",
                "core_start", "core_end", "core_length", "core_coverage", "repetitions",
            ],
            [
                {
                    "case": case_name,
                    "signature": signature,
                    "period": period["period"],
                    "autocorrelation_match_ratio": period["match_ratio"],
                    "core_start": period["core_start"],
                    "core_end": period["core_end"],
                    "core_length": period["core_length"],
                    "core_coverage": period["longest_coverage"],
                    "repetitions": period["repetitions"],
                }
                for case_name, result in summary["workloads"].items()
                for signature, period in (
                    ("full_word", result["analysis"]["full_word_period"]),
                    ("structure_without_variable_fields", result["analysis"]["structure_period"]),
                )
            ],
        ),
        "period_aligned_affine_series.csv": (
            [
                "case", "phase", "slot", "field", "width", "iterations", "base",
                "stride", "matches", "residuals", "match_fraction",
            ],
            [
                {"case": case_name, **entry}
                for case_name, result in summary["workloads"].items()
                for entry in result["analysis"]["period_aligned_affine"]["series"]
            ],
        ),
        "payload_bandwidth_windows.csv": (
            [
                "case", "average_payload_bits_per_cycle", "window_cycles",
                "max_payload_bits", "max_average_bits_per_cycle", "window_start",
            ],
            [
                {
                    "case": case_name,
                    "average_payload_bits_per_cycle": result["analysis"]["payload_bandwidth"]["average_payload_bits_per_cycle"],
                    **entry,
                }
                for case_name, result in summary["workloads"].items()
                for entry in result["analysis"]["payload_bandwidth"]["windows"]
            ],
        ),
        "payload_bandwidth_prefill.csv": (
            [
                "case", "fetch_bits_per_cycle", "minimum_initial_prefill_bits",
                "worst_deadline_cycle",
            ],
            [
                {"case": case_name, **entry}
                for case_name, result in summary["workloads"].items()
                for entry in result["analysis"]["payload_bandwidth"]["fixed_bandwidth_prefill"]
            ],
        ),
    }
    for filename, (fieldnames, rows) in trace_tables.items():
        with (output_root / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    summary_path = output_root / "compression_analysis.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "analysis_output",
        help="Directory for scheduler outputs, traces, and the JSON summary.",
    )
    args = parser.parse_args()
    summary = run(args.output.resolve())
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
