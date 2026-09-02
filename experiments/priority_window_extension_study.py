#!/usr/bin/env python3
"""Evaluate bounded-reordering and pair-window priority heuristics."""

from __future__ import annotations

import contextlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = ROOT / "schedule_v19_issue2_priority_174.py"
OUTPUT_ROOT = ROOT / "analysis_output_priority_window_174"

STRATEGIES = (
    "window8_latency",
    "window16_latency",
    "window8_critical",
    "window16_critical",
    "pair_window8",
    "pair_window16",
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
    results = []

    for issue_width in (2, 5):
        for function, spec in WORKLOAD_SPECS.items():
            for x in (32, 64):
                case = f"{function}_x{x}"
                for mode in spec["modes"]:
                    for strategy in STRATEGIES:
                        out_dir = (
                            OUTPUT_ROOT
                            / f"issue{issue_width}"
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
                                    MAX_ISSUE_SLOTS=issue_width,
                                    PRIORITY_STRATEGY=strategy,
                                    out_dir=str(out_dir),
                                )
                        result = {
                            "case": case,
                            "mode": mode,
                            "priority_strategy": strategy,
                            "issue_width": issue_width,
                            "cycles": len(schedule),
                        }
                        results.append(result)
                        print(
                            f"issue{issue_width} {case} mode={mode} "
                            f"{strategy}: {len(schedule)} cycles"
                        )

    report = {
        "strategies": list(STRATEGIES),
        "results": results,
    }
    (OUTPUT_ROOT / "priority_window_extension.json").write_text(
        json.dumps(report, indent=2)
    )


if __name__ == "__main__":
    main()
