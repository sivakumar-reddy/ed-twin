"""
Generate one-factor-at-a-time (OFAT) sweeps for the ED digital twin.

For each operational lever, this varies that lever across its range while
holding every other lever at the calibrated stable baseline, and records the
steady-state response. Runs are long (6 measured weeks + 2 warm-up weeks
discarded) so each number is a trustworthy steady-state estimate, not a
transient snapshot.

Crucially, every swept point is checked for STABILITY. A configuration is
unstable when its queue grows without bound (the system cannot keep up with
demand). For those points we do NOT report a length-of-stay number, because a
runaway queue's "LOS" is meaningless and depends only on how long you ran it.
Instead we record which resource saturated, diagnosed by watching which
component of the wait grows over the run:

    door-to-doctor grows  -> physicians saturating
    boarding grows        -> inpatient beds saturating
    bed-wait grows        -> ED beds saturating

Output: data/sweeps/ed_sweeps.json, written incrementally with per-value
checkpoint/resume so the sweep can be stopped and restarted safely.

Run from the repo root:
    python -m scripts.09_generate_sweeps
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from simulator.config import Config
from simulator.ed_sim import EDSimulation

# -----------------------------------------------------------------------------
# Run parameters
# -----------------------------------------------------------------------------
WEEK = 10080                      # minutes in a week
WARMUP_WEEKS = 2
MEASURED_WEEKS = 6
SIM_MINUTES = (WARMUP_WEEKS + MEASURED_WEEKS) * WEEK
WARMUP_MINUTES = WARMUP_WEEKS * WEEK
WINDOW_MINUTES = MEASURED_WEEKS * WEEK
N_REPS = 20                       # common random numbers, paired across configs

# Bounded but in crisis: a stay this long is a severe access-block regime, real
# but not a normal operating point. Flagged distinctly so the UI can shade it.
CONGESTION_THRESHOLD_MIN = 720    # 12 hours

OUT_PATH = Path("data/sweeps/ed_sweeps.json")

# -----------------------------------------------------------------------------
# Sweep ranges, centered on the calibrated baseline
# -----------------------------------------------------------------------------
def sweep_ranges(baseline: Config) -> dict:
    return {
        "n_physicians":     list(range(4, 21)),        # baseline 9
        "n_ed_beds":        list(range(25, 76)),        # baseline 45
        "n_inpatient_beds": list(range(70, 151)),       # baseline 110
        "n_triage_nurses":  list(range(1, 11)),         # baseline 3
        "mean_interarrival_minutes": list(range(9, 29)),# baseline 18 (load)
        "acuity_surge_pct": list(range(0, 51, 5)),      # shift mix toward ESI 1-2
    }


# -----------------------------------------------------------------------------
# Acuity surge: shift probability mass from low acuity (4,5) to high (1,2)
# -----------------------------------------------------------------------------
def apply_acuity_surge(base_esi: dict, surge_pct: int) -> dict:
    if surge_pct <= 0:
        return dict(base_esi)
    frac = surge_pct / 100.0
    esi = dict(base_esi)
    moved = (esi[4] + esi[5]) * frac
    esi[4] *= (1 - frac)
    esi[5] *= (1 - frac)
    # add moved mass to ESI 1 and 2 in proportion to their existing share
    hi = esi[1] + esi[2]
    if hi > 0:
        esi[1] += moved * (esi[1] / hi)
        esi[2] += moved * (esi[2] / hi)
    total = sum(esi.values())
    return {k: v / total for k, v in esi.items()}


# -----------------------------------------------------------------------------
# Analyze one simulation run on its post-warmup patients
# -----------------------------------------------------------------------------
def analyze_run(df, n_beds: int) -> dict:
    d = df[df["departure_time"].notna()].copy()
    d = d[d["arrival_time"] > WARMUP_MINUTES]
    if len(d) < 50:
        return {"n": len(d), "degenerate": True}

    d["los"] = d["departure_time"] - d["arrival_time"]
    d["doc"] = d["treatment_start_time"] - d["arrival_time"]
    d["bedwait"] = d["bed_assigned_time"] - d["arrival_time"]
    adm = d[d["admitted_to_inpatient"]].copy()
    adm["board"] = adm["inpatient_bed_time"] - adm["disposition_decision_time"]

    # ED-bed occupancy fraction over the measured window. (Physician and
    # inpatient utilization are computed analytically in analytical_loads;
    # ED-bed occupancy is congestion-dependent, so it's measured here.)
    bed_busy = (d["departure_time"] - d["bed_assigned_time"]).sum()
    util_bed = bed_busy / (n_beds * WINDOW_MINUTES)

    return {
        "n": len(d),
        "degenerate": False,
        "los_median": float(d["los"].median()),
        "doc_median": float(d["doc"].median()),
        "bedwait_median": float(d["bedwait"].median()),
        "board_median": float(adm["board"].median()) if len(adm) else 0.0,
        "util_bed": float(util_bed),
    }


# -----------------------------------------------------------------------------
# Diagnose which resource is the dominant pressure in a congested config
# -----------------------------------------------------------------------------
def diagnose_pressure(doc_median, bedwait_median, board_median) -> str:
    """For a bounded-but-congested config, name the resource contributing the
    most waiting time (by magnitude, since at equilibrium nothing is growing)."""
    comps = [
        ("inpatient_beds", board_median),
        ("physicians", doc_median),
        ("ed_beds", bedwait_median),
    ]
    return max(comps, key=lambda c: c[1])[0]


# -----------------------------------------------------------------------------
# Run all reps for one config and aggregate
# -----------------------------------------------------------------------------
def _tri_mean(lmh) -> float:
    return sum(lmh) / 3.0


def analytical_loads(cfg: Config, esi: dict, overrides: dict) -> dict:
    """Offered load (utilization) of physicians and the inpatient ward, computed
    from rates, not from a finite queue measurement. A resource with offered
    load >= 1.0 cannot keep up: its queue grows without bound regardless of what
    any single run shows. These are exact because treatment time and inpatient
    stay do not depend on congestion."""
    n_phys = overrides.get("n_physicians", cfg.n_physicians)
    n_inpatient = overrides.get("n_inpatient_beds", cfg.n_inpatient_beds)
    interarrival = overrides.get("mean_interarrival_minutes", cfg.mean_interarrival_minutes)

    arr = 1.0 / interarrival  # arrivals per minute
    p_admit = sum(esi[e] * cfg.admit_probability[e] for e in range(1, 6))
    mean_treat = sum(esi[e] * _tri_mean(cfg.treatment_time_minutes[e]) for e in range(1, 6))
    mean_iplos = _tri_mean(cfg.inpatient_los_minutes)

    phys_util = arr * mean_treat / n_phys
    inpatient_util = arr * p_admit * mean_iplos / n_inpatient
    return {"phys_util": phys_util, "inpatient_util": inpatient_util}


def evaluate_config(cfg_base: Config, overrides: dict, esi: dict) -> dict:
    n_phys = overrides.get("n_physicians", cfg_base.n_physicians)
    n_beds = overrides.get("n_ed_beds", cfg_base.n_ed_beds)

    loads = analytical_loads(cfg_base, esi, overrides)
    phys_load = loads["phys_util"]
    inpatient_load = loads["inpatient_util"]

    # ---- Analytical stability gate (monotonic, run-independent) -------------
    if inpatient_load >= 1.0:
        return _unstable("inpatient_beds", phys_load, inpatient_load)
    if phys_load >= 0.98:
        return _unstable("physicians", phys_load, inpatient_load)

    # ---- Simulate to get steady-state numbers for a bounded system ----------
    per_rep = []
    for rep in range(N_REPS):
        cfg = replace(
            cfg_base, esi_distribution=esi, simulation_minutes=SIM_MINUTES,
            random_seed=1000 + rep, **overrides,
        )
        df = EDSimulation(cfg).run().to_dataframe()
        per_rep.append(analyze_run(df, n_beds))

    good = [r for r in per_rep if not r.get("degenerate")]
    if len(good) < max(3, N_REPS // 2):
        return _unstable("unknown", phys_load, inpatient_load, degenerate=True)

    def mean(key):
        return float(np.mean([r[key] for r in good]))

    util_bed = mean("util_bed")
    # Genuine ED-bed saturation: beds full but NOT merely from boarders backing
    # up (which would show as high inpatient load). Only then is it unstable.
    if util_bed >= 0.97 and inpatient_load < 0.90:
        return _unstable("ed_beds", phys_load, inpatient_load, util_bed=util_bed)

    los = [r["los_median"] for r in good]
    los_mean = float(np.mean(los))
    los_sd = float(np.std(los, ddof=1)) if len(los) > 1 else 0.0
    ci = 1.96 * los_sd / math.sqrt(len(los)) if len(los) > 1 else 0.0

    doc_med, bedwait_med, board_med = mean("doc_median"), mean("bedwait_median"), mean("board_median")
    congested = los_mean > CONGESTION_THRESHOLD_MIN

    return {
        "stable": True,
        "congested": congested,
        "saturated_resource": None,
        "pressure_resource": diagnose_pressure(doc_med, bedwait_med, board_med) if congested else None,
        "degenerate": False,
        "los_median": round(los_mean, 1),
        "los_ci": round(ci, 1),
        "doc_median": round(doc_med, 1),
        "board_median": round(board_med, 1),
        "util_phys": round(phys_load, 3),
        "util_bed": round(util_bed, 3),
        "util_inpatient": round(inpatient_load, 3),
    }


def _unstable(cause: str, phys_load: float, inpatient_load: float,
              util_bed=None, degenerate=False) -> dict:
    return {
        "stable": False,
        "congested": False,
        "saturated_resource": cause,
        "pressure_resource": None,
        "degenerate": degenerate,
        "los_median": None,
        "los_ci": None,
        "doc_median": None,
        "board_median": None,
        "util_phys": round(phys_load, 3),
        "util_bed": round(util_bed, 3) if util_bed is not None else None,
        "util_inpatient": round(inpatient_load, 3),
    }


# -----------------------------------------------------------------------------
# Checkpoint helpers (atomic write)
# -----------------------------------------------------------------------------
def load_checkpoint() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def atomic_write(obj: dict):
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(OUT_PATH.parent), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, str(OUT_PATH))


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    baseline = Config.from_data()
    base_esi = dict(baseline.esi_distribution)
    ranges = sweep_ranges(baseline)

    out = load_checkpoint()
    out.setdefault("meta", {
        "calibration": "MIMIC-IV-ED v2.2",
        "measured_weeks": MEASURED_WEEKS,
        "warmup_weeks": WARMUP_WEEKS,
        "reps": N_REPS,
        "baseline": {
            "n_physicians": baseline.n_physicians,
            "n_ed_beds": baseline.n_ed_beds,
            "n_inpatient_beds": baseline.n_inpatient_beds,
            "n_triage_nurses": baseline.n_triage_nurses,
            "mean_interarrival_minutes": baseline.mean_interarrival_minutes,
        },
    })
    out.setdefault("sweeps", {})

    total_points = sum(len(v) for v in ranges.values())
    done_points = sum(len(out["sweeps"].get(k, {})) for k in ranges)
    print(f"Sweep plan: {total_points} points x {N_REPS} reps "
          f"({MEASURED_WEEKS}+{WARMUP_WEEKS} wk runs). Resuming from {done_points} done.")

    t_start = time.time()
    for lever, values in ranges.items():
        out["sweeps"].setdefault(lever, {})
        for v in values:
            key = str(v)
            if key in out["sweeps"][lever]:
                continue

            if lever == "acuity_surge_pct":
                esi = apply_acuity_surge(base_esi, v)
                overrides = {}
            else:
                esi = base_esi
                overrides = {lever: v}

            t0 = time.time()
            result = evaluate_config(baseline, overrides, esi)
            result["value"] = v
            out["sweeps"][lever][key] = result
            atomic_write(out)

            tag = "stable" if result["stable"] else f"UNSTABLE/{result['saturated_resource']}"
            los = result["los_median"]
            los_s = f"{los:.0f}m" if los is not None else "  -  "
            print(f"  {lever:>26} = {v:<4} {tag:<22} LOS {los_s} "
                  f"util_phys {result['util_phys']} util_bed {result['util_bed']} "
                  f"({time.time()-t0:.1f}s)")

    print(f"\nDone. {total_points} points in {(time.time()-t_start)/60:.1f} min "
          f"-> {OUT_PATH}")


if __name__ == "__main__":
    main()
