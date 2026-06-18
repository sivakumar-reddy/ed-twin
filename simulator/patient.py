"""
Patient entity for the ED simulation.

Each patient flows through the ED tracked stage-by-stage. The class
captures all timestamps needed for downstream metric computation.

ESI (Emergency Severity Index) is sampled at creation time based on
the config's national distribution. All downstream service times
condition on ESI level.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class Patient:
    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    patient_id: int
    arrival_time: float

    # ESI sampled at creation time; remains fixed for the visit
    esi: int = field(default=3)  # default ESI 3 if not explicitly assigned

    # -------------------------------------------------------------------------
    # Timestamps (in simulation minutes from t=0)
    # -------------------------------------------------------------------------
    # All Optional[float], filled in as the patient progresses
    triage_start_time:       Optional[float] = None
    triage_end_time:         Optional[float] = None
    bed_assigned_time:       Optional[float] = None
    treatment_start_time:    Optional[float] = None
    treatment_end_time:      Optional[float] = None
    disposition_decision_time: Optional[float] = None
    departure_time:          Optional[float] = None

    # -------------------------------------------------------------------------
    # Disposition
    # -------------------------------------------------------------------------
    admitted_to_inpatient:   bool = False
    inpatient_bed_time:      Optional[float] = None  # only set if admitted

    # -------------------------------------------------------------------------
    # Class methods for ESI sampling
    # -------------------------------------------------------------------------
    @classmethod
    def sample_esi(cls, esi_distribution: Dict[int, float], rng: random.Random) -> int:
        """
        Sample an ESI level from the configured distribution.

        Uses weighted random choice; the distribution must sum to 1.0
        (validated in Config.__post_init__).
        """
        levels = list(esi_distribution.keys())
        weights = list(esi_distribution.values())
        return rng.choices(levels, weights=weights, k=1)[0]

    # -------------------------------------------------------------------------
    # Derived metrics (computed only after departure)
    # -------------------------------------------------------------------------
    @property
    def door_to_triage_minutes(self) -> Optional[float]:
        """Time from arrival to triage start. Wait time before triage."""
        if self.triage_start_time is None:
            return None
        return self.triage_start_time - self.arrival_time

    @property
    def door_to_bed_minutes(self) -> Optional[float]:
        """Time from arrival to ED bed assignment."""
        if self.bed_assigned_time is None:
            return None
        return self.bed_assigned_time - self.arrival_time

    @property
    def door_to_doc_minutes(self) -> Optional[float]:
        """Time from arrival to physician contact. Key ED quality metric."""
        if self.treatment_start_time is None:
            return None
        return self.treatment_start_time - self.arrival_time

    @property
    def total_los_minutes(self) -> Optional[float]:
        """Total length of stay in the ED."""
        if self.departure_time is None:
            return None
        return self.departure_time - self.arrival_time

    @property
    def boarding_time_minutes(self) -> Optional[float]:
        """
        Boarding time: from disposition decision (admit) to inpatient
        bed assignment. Only meaningful for admitted patients.

        This is the #1 ED throughput bottleneck. Returns None if patient
        was discharged or hasn't been admitted yet.
        """
        if not self.admitted_to_inpatient:
            return None
        if self.disposition_decision_time is None or self.inpatient_bed_time is None:
            return None
        return self.inpatient_bed_time - self.disposition_decision_time

    # -------------------------------------------------------------------------
    # Export to dict for metric collection
    # -------------------------------------------------------------------------
    def to_dict(self) -> dict:
        """Flatten to dict for pandas DataFrame collection."""
        return {
            "patient_id":               self.patient_id,
            "esi":                      self.esi,
            "arrival_time":             self.arrival_time,
            "triage_start_time":        self.triage_start_time,
            "triage_end_time":          self.triage_end_time,
            "bed_assigned_time":        self.bed_assigned_time,
            "treatment_start_time":     self.treatment_start_time,
            "treatment_end_time":       self.treatment_end_time,
            "disposition_decision_time": self.disposition_decision_time,
            "departure_time":           self.departure_time,
            "admitted_to_inpatient":    self.admitted_to_inpatient,
            "inpatient_bed_time":       self.inpatient_bed_time,
            "door_to_triage_minutes":   self.door_to_triage_minutes,
            "door_to_bed_minutes":      self.door_to_bed_minutes,
            "door_to_doc_minutes":      self.door_to_doc_minutes,
            "total_los_minutes":        self.total_los_minutes,
            "boarding_time_minutes":    self.boarding_time_minutes,
        }