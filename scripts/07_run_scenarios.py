"""
Run ED scenario comparisons: stress-test under load and sweep capacity levers.

Usage (from project root, venv active):

    # Single intervention, default load
    python -m scripts.07_run_scenarios --beds 45

    # Stress the ED: shorter interarrival = busier department
    python -m scripts.07_run_scenarios --beds 45 --load 12

    # Find the binding constraint: test every lever under load, in one run
    python -m scripts.07_run_scenarios --sweep --load 12

    # More replications for tighter confidence intervals
    python -m scripts.07_run_scenarios --sweep --load 10 --reps 50

Each scenario runs across N replications using common random numbers (every
scenario sees the same arrival streams), then reports the paired difference vs
baseline with a 95% confidence interval. A '*' marks changes whose CI excludes
zero, i.e. statistically meaningful effects rather than simulation noise.

The point of --sweep is Theory of Constraints in practice: adding capacity to a
resource that is not the bottleneck does nothing. Sweeping every lever under
realistic load reveals which single resource actually constrains throughput.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from simulator.config import Config
from simulator.scenarios import (
    TRACKED_METRICS,
    Scenario,
    ScenarioResult,
    ScenarioRunner,
)

OUTPUT_DIR = Path("data/scenarios")

# The single-lever interventions tested in --sweep mode. Each adds a modest
# increment to one resource so the comparison isolates that resource's effect.
SWEEP_LEVERS = [
    ("n_ed_beds", 5, "+5 ED beds"),
    ("n_physicians", 1, "+1 physician"),
    ("n_triage_nurses", 1, "+1 triage nurse"),
    ("n_inpatient_beds", 10, "+10 inpatient beds"),
]


def _progress(name: str, i: int, total: int) -> None:
    bar_done = "#" * int(20 * i / total)
    bar = bar_done.ljust(20, "-")
    end = "\n" if i == total else "\r"
    sys.stdout.write(f"  {name:<22} [{bar}] {i}/{total}{end}")
    sys.stdout.flush()


def _print_comparison(intervention_name: str, comparison: dict) -> None:
    print()
    print("=" * 82)
    print(f"COMPARISON: {intervention_name} vs Baseline")
    print("=" * 82)
    print(
        f"{'Metric':<28}{'Baseline':>10}{'New':>10}"
        f"{'Delta':>9}{'95% CI':>20}{'% chg':>8}"
    )
    print("-" * 82)
    for key, label in TRACKED_METRICS.items():
        if key not in comparison:
            continue
        c = comparison[key]
        ci = f"[{c['ci_low']:+.1f}, {c['ci_high']:+.1f}]"
        sig = "" if (c["ci_low"] <= 0 <= c["ci_high"]) else " *"
        print(
            f"{label:<28}{c['baseline_mean']:>10.1f}{c['intervention_mean']:>10.1f}"
            f"{c['delta']:>+9.1f}{ci:>20}{c['pct_change']:>+7.1f}%{sig}"
        )
    print("-" * 82)


def _print_sweep_ranking(rankings: list) -> None:
    """Print levers ranked by their effect on median LOS (the headline KPI)."""
    print()
    print("=" * 82)
    print("BOTTLENECK RANKING  (effect on median length of stay)")
    print("=" * 82)
    print(f"{'Lever':<24}{'LOS delta':>12}{'95% CI':>22}{'Meaningful?':>16}")
    print("-" * 82)
    # Most negative delta (biggest LOS reduction) first.
    for name, delta, lo, hi, sig in rankings:
        ci = f"[{lo:+.1f}, {hi:+.1f}]"
        flag = "YES (binding)" if sig and delta < 0 else "no effect"
        print(f"{name:<24}{delta:>+12.1f}{ci:>22}{flag:>16}")
    print("-" * 82)
    binding = [r for r in rankings if r[4] and r[1] < 0]
    if binding:
        top = binding[0]
        print(f"  Binding constraint: {top[0]} "
              f"(cuts median LOS by {abs(top[1]):.1f} min, CI excludes zero)")
    else:
        print("  No single lever shows a statistically meaningful effect at this load.")
        print("  Try a heavier load (lower --load) to push the system to a constraint.")


def _save_csv(rows: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario", "metric", "baseline_mean", "intervention_mean",
        "delta", "ci_low", "ci_high", "pct_change", "n",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _collect_rows(scn_name: str, comparison: dict) -> list:
    return [
        {
            "scenario": scn_name,
            "metric": key,
            "baseline_mean": c["baseline_mean"],
            "intervention_mean": c["intervention_mean"],
            "delta": c["delta"],
            "ci_low": c["ci_low"],
            "ci_high": c["ci_high"],
            "pct_change": c["pct_change"],
            "n": c["n"],
        }
        for key, c in comparison.items()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ED scenario comparisons.")
    parser.add_argument(
        "--reps", type=int, default=30,
        help="Replications per scenario (default 30).",
    )
    parser.add_argument(
        "--load", type=float, default=None,
        help="Override mean interarrival minutes. Lower = busier ED. "
             "Baseline default comes from Config.",
    )
    parser.add_argument(
        "--beds", type=int, nargs="+", default=None,
        help="ED bed counts to test as interventions (e.g. --beds 45 50).",
    )
    parser.add_argument(
        "--sweep", action="store_true",
        help="Test every capacity lever (beds, physicians, triage, inpatient) "
             "against baseline to find the binding constraint.",
    )
    args = parser.parse_args()

    if not args.sweep and not args.beds:
        args.beds = [45]  # sensible default if neither flag given

    # Build the base config, applying the load override to the BASELINE too so
    # the comparison is apples-to-apples under the same arrival rate.
    base = Config()
    load_note = ""
    if args.load is not None:
        base = type(base)(**{**base.__dict__, "mean_interarrival_minutes": args.load})
        load_note = f"  [load: {args.load} min interarrival]"

    runner = ScenarioRunner(base, n_replications=args.reps)

    print("=" * 82)
    print(f"ED SCENARIO ANALYSIS  ({args.reps} reps, common random numbers){load_note}")
    print("=" * 82)
    print(f"Baseline: {base.n_ed_beds} ED beds, {base.n_physicians} physicians, "
          f"{base.n_triage_nurses} triage nurses, {base.n_inpatient_beds} inpatient beds")
    print(f"Mean interarrival: {base.mean_interarrival_minutes} min")
    print()

    print("Running scenarios:")
    baseline_result = runner.run_scenario(Scenario(name="Baseline"), progress=_progress)

    csv_rows: list = []

    if args.sweep:
        rankings: list = []
        for field_name, increment, label in SWEEP_LEVERS:
            current = getattr(base, field_name)
            scn = Scenario(name=label, overrides={field_name: current + increment})
            result = runner.run_scenario(scn, progress=_progress)
            comparison = runner.compare(baseline_result, result)
            csv_rows += _collect_rows(label, comparison)

            los = comparison.get("total_los_min_median")
            if los:
                sig = not (los["ci_low"] <= 0 <= los["ci_high"])
                rankings.append((label, los["delta"], los["ci_low"], los["ci_high"], sig))

        # Rank by LOS delta (most negative = biggest improvement first).
        rankings.sort(key=lambda r: r[1])
        _print_sweep_ranking(rankings)
        tag = "sweep"
    else:
        for beds in args.beds:
            if beds == base.n_ed_beds:
                print(f"  (skipping {beds} beds: same as baseline)")
                continue
            scn_name = f"+{beds - base.n_ed_beds} ED beds ({beds})"
            scn = Scenario(name=scn_name, overrides={"n_ed_beds": beds})
            result = runner.run_scenario(scn, progress=_progress)
            comparison = runner.compare(baseline_result, result)
            _print_comparison(scn_name, comparison)
            csv_rows += _collect_rows(scn_name, comparison)
        tag = "beds_" + "_".join(str(b) for b in args.beds)

    if csv_rows:
        load_tag = f"_load{int(args.load)}" if args.load is not None else ""
        out = OUTPUT_DIR / f"{date.today().isoformat()}_{tag}{load_tag}.csv"
        _save_csv(csv_rows, out)
        print()
        print(f"Saved results to {out}")


if __name__ == "__main__":
    main()
