#!/usr/bin/env python3
"""
ed_calibration.py

Calibrate the ed-twin discrete-event simulation against MIMIC-IV-ED v2.2.

Reads the raw gzipped ED tables, derives empirical distributions, and writes a
single calibration_params.json that both the SimPy grid and the Next.js front
end consume. Only aggregate distributions leave this script. No patient-level
rows are written, printed in full, or committed to version control.

Usage (PowerShell, from the ed-twin repo root):
    python calibration/ed_calibration.py ^
        --data-dir "C:\\Users\\reddy\\mimic-iv-ed-data\\physionet.org\\files\\mimic-iv-ed\\2.2\\ed" ^
        --out calibration/calibration_params.json

Dependencies: pandas, numpy.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


# Length-of-stay sanity bounds in hours. Stays outside this window are treated
# as data artifacts (clock errors, broken transfer timestamps) and excluded from
# distribution fitting. The excluded count is reported for transparency.
LOS_MIN_HOURS = 0.0
LOS_MAX_HOURS = 72.0

# ESI acuity levels. 1 is resuscitation, 5 is non-urgent.
ACUITY_LEVELS = [1, 2, 3, 4, 5]

# Minimum sample size before a sub-population gets its own fitted distribution.
MIN_FIT_N = 50


def load_tables(data_dir: Path):
    edstays_path = data_dir / "edstays.csv.gz"
    triage_path = data_dir / "triage.csv.gz"
    for p in (edstays_path, triage_path):
        if not p.exists():
            sys.exit(f"Missing required table: {p}")

    edstays = pd.read_csv(
        edstays_path,
        compression="gzip",
        parse_dates=["intime", "outtime"],
        usecols=["subject_id", "stay_id", "intime", "outtime", "disposition"],
    )
    triage = pd.read_csv(
        triage_path,
        compression="gzip",
        usecols=["stay_id", "acuity"],
    )
    return edstays, triage


def build_dataset(edstays: pd.DataFrame, triage: pd.DataFrame):
    df = edstays.merge(triage, on="stay_id", how="left")
    df["acuity"] = pd.to_numeric(df["acuity"], errors="coerce")
    df["los_hours"] = (df["outtime"] - df["intime"]).dt.total_seconds() / 3600.0

    total = len(df)
    valid = df["los_hours"].between(LOS_MIN_HOURS, LOS_MAX_HOURS, inclusive="neither")
    excluded = int((~valid).sum())
    df = df[valid].copy()
    return df, total, excluded


def arrival_profile(df: pd.DataFrame):
    df = df.copy()
    df["hour"] = df["intime"].dt.hour
    df["dow"] = df["intime"].dt.dayofweek  # 0 = Monday
    span_days = (df["intime"].max() - df["intime"].min()).total_seconds() / 86400.0
    span_days = max(span_days, 1.0)

    # Mean arrivals during each clock-hour window, averaged across the full
    # observation span. This is the time-varying Poisson rate the sim samples.
    by_hour = df.groupby("hour").size()
    hourly_rate = (by_hour / span_days).reindex(range(24), fill_value=0.0)

    by_dow = df.groupby("dow").size()
    dow_weight = (by_dow / by_dow.sum()).reindex(range(7), fill_value=0.0)

    return {
        "observation_span_days": round(span_days, 1),
        "mean_arrivals_per_hour": round(float(len(df) / (span_days * 24)), 3),
        "hourly_arrival_rate": [round(float(x), 3) for x in hourly_rate.values],
        "day_of_week_weight": [round(float(x), 4) for x in dow_weight.values],
    }


def acuity_mix(df: pd.DataFrame):
    total = len(df)
    mix = {}
    known = 0
    for lvl in ACUITY_LEVELS:
        c = int((df["acuity"] == lvl).sum())
        known += c
        mix[str(lvl)] = round(c / total, 4)
    mix["unknown"] = round((total - known) / total, 4)
    return mix


def lognormal_params(series: pd.Series):
    # Fit a lognormal by computing mu and sigma of the natural log of LOS.
    # Lognormal is the standard shape for ED length-of-stay: strictly positive,
    # right-skewed, with a long tail driven by boarding and admitted patients.
    x = series[series > 0].values
    logs = np.log(x)
    return {
        "n": int(len(x)),
        "median_hours": round(float(np.median(x)), 2),
        "mean_hours": round(float(np.mean(x)), 2),
        "p90_hours": round(float(np.percentile(x, 90)), 2),
        "lognormal_mu": round(float(np.mean(logs)), 4),
        "lognormal_sigma": round(float(np.std(logs, ddof=1)), 4),
    }


def los_by_acuity(df: pd.DataFrame):
    out = {}
    for lvl in ACUITY_LEVELS:
        sub = df.loc[df["acuity"] == lvl, "los_hours"]
        if len(sub) >= MIN_FIT_N:
            out[str(lvl)] = lognormal_params(sub)
    return out


def los_by_disposition(df: pd.DataFrame):
    df = df.copy()
    disp = df["disposition"].fillna("").str.upper()
    df["admitted"] = disp.str.contains("ADMITTED")
    out = {}
    for label, flag in (("admitted", True), ("discharged", False)):
        sub = df.loc[df["admitted"] == flag, "los_hours"]
        if len(sub) >= MIN_FIT_N:
            out[label] = lognormal_params(sub)
    return out


def admit_rate_by_acuity(df: pd.DataFrame):
    # Real admission probability per ESI level. This is an observable input
    # (the model's admit_probability dict keys on ESI), so the loader uses
    # it directly rather than holding it out for validation. The overall
    # admit rate is reported too, as a fallback when a level is sparse.
    df = df.copy()
    admitted = df["disposition"].fillna("").str.upper().str.contains("ADMITTED")
    out = {}
    for lvl in ACUITY_LEVELS:
        sub = admitted[df["acuity"] == lvl]
        if len(sub) >= MIN_FIT_N:
            out[str(lvl)] = round(float(sub.mean()), 4)
    out["overall"] = round(float(admitted.mean()), 4)
    return out


def disposition_mix(df: pd.DataFrame):
    counts = df["disposition"].fillna("UNKNOWN").str.upper().value_counts()
    total = int(counts.sum())
    return {str(k): round(int(v) / total, 4) for k, v in counts.items()}


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate ed-twin against MIMIC-IV-ED v2.2."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Path to the MIMIC-IV-ED 'ed' folder with edstays.csv.gz and triage.csv.gz.",
    )
    parser.add_argument(
        "--out",
        default="calibration_params.json",
        help="Output path for the calibration JSON.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"Reading MIMIC-IV-ED tables from: {data_dir}")
    edstays, triage = load_tables(data_dir)
    df, total, excluded = build_dataset(edstays, triage)
    print(f"Loaded {total:,} ED stays. Excluded {excluded:,} out-of-range LOS. Using {len(df):,}.")

    params = {
        "source": "MIMIC-IV-ED v2.2",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_stays_used": int(len(df)),
        "n_stays_excluded": excluded,
        "date_range": {
            "start": df["intime"].min().date().isoformat(),
            "end": df["intime"].max().date().isoformat(),
        },
        "arrivals": arrival_profile(df),
        "acuity_mix": acuity_mix(df),
        "admit_rate_by_acuity": admit_rate_by_acuity(df),
        "los_overall_hours": lognormal_params(df["los_hours"]),
        "los_by_acuity_hours": los_by_acuity(df),
        "los_by_disposition_hours": los_by_disposition(df),
        "disposition_mix": disposition_mix(df),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(params, indent=2))
    print(f"\nWrote calibration parameters to: {out_path.resolve()}")

    # Console summary. Aggregates only, safe to share.
    p = params
    print("\n--- CALIBRATION SUMMARY ---")
    print(f"Stays used:         {p['n_stays_used']:,}  (excluded {p['n_stays_excluded']:,})")
    print(f"Date range:         {p['date_range']['start']} to {p['date_range']['end']}")
    print(f"Mean arrivals/hr:   {p['arrivals']['mean_arrivals_per_hour']}")
    o = p["los_overall_hours"]
    print(f"Overall LOS:        {o['median_hours']} h median, {o['mean_hours']} h mean, {o['p90_hours']} h p90")
    print("Acuity mix:         " + ", ".join(
        f"L{k}={v:.1%}" for k, v in p["acuity_mix"].items() if k != "unknown"))
    print("LOS by acuity (median / p90):")
    for lvl, s in p["los_by_acuity_hours"].items():
        print(f"   acuity {lvl}:  {s['median_hours']} h / {s['p90_hours']} h   (n={s['n']:,})")
    d = p["los_by_disposition_hours"]
    if "admitted" in d and "discharged" in d:
        print(f"LOS admitted vs discharged (median): "
              f"{d['admitted']['median_hours']} h  vs  {d['discharged']['median_hours']} h")
    print("--- END SUMMARY ---")


if __name__ == "__main__":
    main()
