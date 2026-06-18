"""
Generate the precomputed scenario grid for the interactive web app.

The web app needs to respond instantly to slider changes, but a full-fidelity
run (replications over a week of simulated time) takes minutes. The resolution
is to do the expensive computation once, offline, across a grid of
configurations, and ship the results as a single JSON the frontend reads.

For each load level, the baseline is the minimum-capacity corner (the crowded
ED). Every other grid cell is compared against that baseline using common
random numbers, so each cell carries both its absolute metrics and its
improvement-over-baseline with a 95% confidence interval. The frontend then
needs no backend: dragging a slider is a lookup, not a simulation.

Usage (from project root, venv active):
    python -m scripts.08_generate_grid
    python -m scripts.08_generate_grid --reps 30          # full fidelity
    python -m scripts.08_generate_grid --reps 10 --quick  # fast preview grid

Output: data/grid/ed_throughput_grid.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from itertools import product
from pathlib import Path

from simulator.config import Config
from simulator.scenarios import (
    TRACKED_METRICS,
    Scenario,
    ScenarioRunner,
)

OUTPUT_PATH = Path("data/grid/ed_throughput_grid.json")

# ---------------------------------------------------------------------------
# Grid definition: the lever values the sliders can take.
# Index 0 of each list is the baseline (floor) value.
# ---------------------------------------------------------------------------
GRID = {
    "n_physicians": [4, 5, 6, 7],
    "n_ed_beds": [40, 45, 50, 55],
    "n_triage_nurses": [3, 4],
}
LOADS = [12, 15, 18]  # mean interarrival minutes; lower = busier

# Quick grid for fast iteration / preview (smaller, fewer cells).
QUICK_GRID = {
    "n_physicians": [4, 5, 6],
    "n_ed_beds": [40, 50],
    "n_triage_nurses": [3],
}
QUICK_LOADS = [12, 18]


def _baseline_overrides(grid: dict) -> dict:
    """The floor config: first (minimum) value of every lever."""
    return {lever: values[0] for lever, values in grid.items()}


def _cell_overrides(grid: dict, combo: tuple) -> dict:
    """Map a product() tuple back to a lever-name -> value dict."""
    return dict(zip(grid.keys(), combo))


def _absolute_metrics(result) -> dict:
    """Mean of each tracked metric across replications for one scenario."""
    out = {}
    for key in TRACKED_METRICS:
        if result.samples.get(key):
            out[key] = round(result.metric_mean(key), 1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the scenario grid JSON.")
    parser.add_argument("--reps", type=int, default=20,
                        help="Replications per cell (default 20; use 30 for full fidelity).")
    parser.add_argument("--quick", action="store_true",
                        help="Use the small preview grid for fast iteration.")
    args = parser.parse_args()

    grid = QUICK_GRID if args.quick else GRID
    loads = QUICK_LOADS if args.quick else LOADS

    cells_per_load = 1
    for values in grid.values():
        cells_per_load *= len(values)
    total_cells = cells_per_load * len(loads)
    total_sims = total_cells * args.reps

    # Time estimate (~2 sec per week-long sim is the observed rate).
    est_min = total_sims * 2 / 60.0

    print("=" * 70)
    print("ED THROUGHPUT GRID GENERATION")
    print("=" * 70)
    print(f"Levers:        {', '.join(f'{k} {v}' for k, v in grid.items())}")
    print(f"Loads:         {loads} min interarrival")
    print(f"Cells:         {total_cells}  ({cells_per_load} per load x {len(loads)} loads)")
    print(f"Replications:  {args.reps} per cell")
    print(f"Total sims:    {total_sims}")
    print(f"Est. runtime:  ~{est_min:.0f} min")
    print("=" * 70)
    print()

    base_template = Config()
    grid_keys = list(grid.keys())

    out = {
        "meta": {
            "generated": date.today().isoformat(),
            "replications": args.reps,
            "method": "common random numbers; baseline = minimum-capacity corner per load; "
                      "deltas are paired vs baseline with 95% t-interval",
            "levers": {k: v for k, v in grid.items()},
            "loads": loads,
            "metrics": list(TRACKED_METRICS.keys()),
            "metric_labels": dict(TRACKED_METRICS),
        },
        "baselines": {},
        "cells": [],
    }

    start = time.time()
    done = 0

    for load in loads:
        # Baseline config for this load = floor levers + this load.
        base = base_template.__class__(
            **{**base_template.__dict__, "mean_interarrival_minutes": float(load)}
        )
        runner = ScenarioRunner(base, n_replications=args.reps)

        # Run the baseline once; reuse for every cell's paired comparison.
        baseline_scn = Scenario(name="baseline", overrides=_baseline_overrides(grid))
        baseline_result = runner.run_scenario(baseline_scn)
        done += 1
        out["baselines"][str(load)] = {
            "config": _baseline_overrides(grid),
            "metrics": _absolute_metrics(baseline_result),
        }
        _tick(done, total_cells, start, load)

        # Sweep every cell.
        for combo in product(*grid.values()):
            overrides = _cell_overrides(grid, combo)
            # Skip the baseline cell itself (already have it).
            is_baseline = overrides == _baseline_overrides(grid)
            if is_baseline:
                cell = {
                    "load": load,
                    **overrides,
                    "is_baseline": True,
                    "metrics": {
                        k: {"abs": v, "delta": 0.0, "ci_low": 0.0, "ci_high": 0.0}
                        for k, v in out["baselines"][str(load)]["metrics"].items()
                    },
                }
                out["cells"].append(cell)
                continue

            scn = Scenario(name=str(overrides), overrides=overrides)
            result = runner.run_scenario(scn)
            comparison = runner.compare(baseline_result, result)
            abs_metrics = _absolute_metrics(result)

            metrics = {}
            for key in TRACKED_METRICS:
                if key in comparison:
                    c = comparison[key]
                    metrics[key] = {
                        "abs": abs_metrics.get(key, c["intervention_mean"]),
                        "delta": c["delta"],
                        "ci_low": c["ci_low"],
                        "ci_high": c["ci_high"],
                    }

            out["cells"].append({
                "load": load,
                **overrides,
                "is_baseline": False,
                "metrics": metrics,
            })

            done += 1
            _tick(done, total_cells, start, load)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w") as f:
        json.dump(out, f, indent=2)

    elapsed = (time.time() - start) / 60.0
    print()
    print(f"Done in {elapsed:.1f} min. {len(out['cells'])} cells written to {OUTPUT_PATH}")


def _tick(done: int, total: int, start: float, load: int) -> None:
    elapsed = time.time() - start
    rate = done / elapsed if elapsed > 0 else 0
    remaining = (total - done) / rate if rate > 0 else 0
    bar = ("#" * int(28 * done / total)).ljust(28, "-")
    sys.stdout.write(
        f"\r  [{bar}] {done}/{total} cells  "
        f"(load {load}, ~{remaining/60:.0f} min left)   "
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
