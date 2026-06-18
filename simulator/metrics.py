"""
Metrics collection for the ED simulation.

The MetricsCollector receives finished Patient objects and stores them
for downstream analysis. At the end of a simulation run, it produces
both a per-patient DataFrame and a summary statistics dict.

The summary metrics are the headline numbers used to compare scenarios
(default vs intervention). They match the metrics real EDs report to
CMS and AHRQ.
"""

from __future__ import annotations
from typing import Dict, List
import pandas as pd

from simulator.patient import Patient


class MetricsCollector:
    """Collects finished patients and produces aggregate metrics."""

    def __init__(self):
        self._patients: List[Patient] = []
        # Snapshots of resource utilization over time, populated by engine
        self.bed_occupancy_log: List[tuple] = []  # (time, beds_occupied)
        self.queue_length_log: List[tuple] = []   # (time, patients_waiting)

    # -------------------------------------------------------------------------
    # Recording
    # -------------------------------------------------------------------------
    def record_patient(self, patient: Patient) -> None:
        """Called by the engine when a patient departs the ED."""
        self._patients.append(patient)

    def record_bed_occupancy(self, time: float, occupied: int) -> None:
        self.bed_occupancy_log.append((time, occupied))

    def record_queue_length(self, time: float, length: int) -> None:
        self.queue_length_log.append((time, length))

    # -------------------------------------------------------------------------
    # Exports
    # -------------------------------------------------------------------------
    def to_dataframe(self) -> pd.DataFrame:
        """Per-patient DataFrame with one row per departed patient."""
        if not self._patients:
            return pd.DataFrame()
        return pd.DataFrame([p.to_dict() for p in self._patients])

    def bed_occupancy_df(self) -> pd.DataFrame:
        """Time series of ED bed occupancy."""
        return pd.DataFrame(
            self.bed_occupancy_log,
            columns=["time_minutes", "beds_occupied"]
        )

    def queue_length_df(self) -> pd.DataFrame:
        """Time series of patients waiting for an ED bed."""
        return pd.DataFrame(
            self.queue_length_log,
            columns=["time_minutes", "patients_waiting"]
        )

    # -------------------------------------------------------------------------
    # Summary statistics (the headline numbers)
    # -------------------------------------------------------------------------
    def summary(self) -> Dict[str, float]:
        """
        Headline metrics for scenario comparison.

        These are the numbers a real ED operations team would look at:
        - Throughput (total patients seen)
        - Door-to-doc (key quality metric)
        - LOS (key throughput metric)
        - Boarding time (key bottleneck metric)
        - Admit rate
        """
        df = self.to_dataframe()
        if df.empty:
            return {"n_patients": 0}

        # Filter to patients who completed at least the door-to-doc stage
        completed = df[df["treatment_start_time"].notna()]
        departed = df[df["departure_time"].notna()]

        summary = {
            "n_patients_arrived":      len(df),
            "n_patients_completed":    len(departed),
            "n_admitted":              int(df["admitted_to_inpatient"].sum()),
        }

        if len(departed) > 0:
            summary["admit_rate_pct"] = round(
                100.0 * df["admitted_to_inpatient"].sum() / len(departed), 2
            )

        # Quality / throughput metrics, conditional on stage reached
        for col, label in [
            ("door_to_triage_minutes", "door_to_triage_min"),
            ("door_to_bed_minutes",    "door_to_bed_min"),
            ("door_to_doc_minutes",    "door_to_doc_min"),
            ("total_los_minutes",      "total_los_min"),
        ]:
            if col in df.columns and df[col].notna().any():
                summary[f"{label}_mean"]   = round(df[col].mean(), 1)
                summary[f"{label}_median"] = round(df[col].median(), 1)
                summary[f"{label}_p95"]    = round(df[col].quantile(0.95), 1)

        # Boarding metric — admitted patients only
        admitted = df[df["admitted_to_inpatient"] & df["boarding_time_minutes"].notna()]
        if len(admitted) > 0:
            summary["boarding_min_mean"]   = round(admitted["boarding_time_minutes"].mean(), 1)
            summary["boarding_min_median"] = round(admitted["boarding_time_minutes"].median(), 1)
            summary["boarding_min_p95"]    = round(admitted["boarding_time_minutes"].quantile(0.95), 1)

        # ESI mix actually seen
        if "esi" in df.columns:
            esi_counts = df["esi"].value_counts().to_dict()
            for esi_level in range(1, 6):
                summary[f"esi_{esi_level}_count"] = int(esi_counts.get(esi_level, 0))

        return summary

    # -------------------------------------------------------------------------
    # Pretty print for terminal output
    # -------------------------------------------------------------------------
    def print_summary(self) -> None:
        """Formatted terminal output of summary metrics."""
        s = self.summary()
        if s.get("n_patients_arrived", 0) == 0:
            print("No patients recorded.")
            return

        print("=" * 60)
        print("ED SIMULATION SUMMARY")
        print("=" * 60)
        print(f"  Patients arrived:    {s['n_patients_arrived']}")
        print(f"  Patients completed:  {s['n_patients_completed']}")
        print(f"  Patients admitted:   {s['n_admitted']}")
        if "admit_rate_pct" in s:
            print(f"  Admit rate:          {s['admit_rate_pct']}%")
        print()

        print("  ESI mix actually seen:")
        for esi_level in range(1, 6):
            n = s.get(f"esi_{esi_level}_count", 0)
            print(f"    ESI {esi_level}: {n}")
        print()

        print("  Quality metrics (minutes):")
        for label in ["door_to_triage_min", "door_to_bed_min",
                      "door_to_doc_min", "total_los_min"]:
            if f"{label}_mean" in s:
                print(
                    f"    {label:25s} "
                    f"mean={s[f'{label}_mean']:>7.1f}  "
                    f"median={s[f'{label}_median']:>7.1f}  "
                    f"p95={s[f'{label}_p95']:>7.1f}"
                )

        if "boarding_min_mean" in s:
            print()
            print("  Boarding (minutes, admitted only):")
            print(
                f"    {'boarding':25s} "
                f"mean={s['boarding_min_mean']:>7.1f}  "
                f"median={s['boarding_min_median']:>7.1f}  "
                f"p95={s['boarding_min_p95']:>7.1f}"
            )
        print("=" * 60)