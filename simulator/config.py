"""
Simulation configuration parameters.

All tunable knobs for the ED simulation live here. Default values
are drawn from published US ED operations literature; calibrated
values from real data are loaded via Config.from_data() once
analytical data is available.

Resource defaults are the calibrated stable operating point: at these
counts the simulation reaches steady state (LOS does not drift with run
length) and reproduces real MIMIC-IV-ED median length of stay by acuity
within ~15%. See calibration notes in the diagnostic-workup section.
"""

from dataclasses import dataclass, field
from typing import Dict
import json
from pathlib import Path


@dataclass
class Config:
    # -------------------------------------------------------------------------
    # Simulation duration
    # -------------------------------------------------------------------------
    simulation_minutes: int = 10080  # 1 week of operations
    random_seed: int = 42

    # -------------------------------------------------------------------------
    # Resources (counts) -- calibrated stable baseline
    # -------------------------------------------------------------------------
    # These are the steady-state operating point, not arbitrary defaults.
    # Below ~9 physicians or ~110 inpatient beds the system tips into an
    # unstable queue (LOS grows without bound), which the sweep flags rather
    # than reports. See the OFAT sweep for the stability envelope.
    n_triage_nurses: int = 3
    n_ed_beds: int = 45
    n_physicians: int = 9
    n_inpatient_beds: int = 110

    # -------------------------------------------------------------------------
    # Arrival process
    # -------------------------------------------------------------------------
    mean_interarrival_minutes: float = 18.0

    # -------------------------------------------------------------------------
    # ESI (Emergency Severity Index) acuity distribution
    # -------------------------------------------------------------------------
    esi_distribution: Dict[int, float] = field(default_factory=lambda: {
        1: 0.02,
        2: 0.18,
        3: 0.50,
        4: 0.25,
        5: 0.05,
    })

    # -------------------------------------------------------------------------
    # Service time distributions (minutes, triangular(low, mode, high))
    # -------------------------------------------------------------------------
    triage_time_minutes: Dict[int, tuple] = field(default_factory=lambda: {
        1: (3, 5, 8),
        2: (4, 7, 12),
        3: (5, 8, 15),
        4: (5, 10, 15),
        5: (5, 10, 20),
    })

    treatment_time_minutes: Dict[int, tuple] = field(default_factory=lambda: {
        1: (60, 120, 180),
        2: (45, 75, 150),
        3: (30, 60, 120),
        4: (20, 40, 80),
        5: (15, 25, 45),
    })

    # -------------------------------------------------------------------------
    # Disposition probabilities
    # -------------------------------------------------------------------------
    admit_probability: Dict[int, float] = field(default_factory=lambda: {
        1: 0.80,
        2: 0.45,
        3: 0.20,
        4: 0.05,
        5: 0.02,
    })

    disposition_decision_minutes: tuple = (10, 20, 40)

    # Inpatient length of stay (minutes). Beds turn over after this.
    # Typical US inpatient LOS is 3-5 days; triangular(2d, 4d, 7d)
    inpatient_los_minutes: tuple = (2880, 4320, 7200) # 2, 3, 5 days

    # -------------------------------------------------------------------------
    # Diagnostic workup (labs + imaging + consults)
    # -------------------------------------------------------------------------
    # After the physician's initial evaluation the patient waits on diagnostics
    # while the physician moves on to other patients: the physician is released
    # but the ED bed is held. This workup wait is what dominates real ED length
    # of stay, and adding it is what lets the model reproduce the real MIMIC
    # gradient instead of running roughly 3x too fast.
    #
    # Order probabilities rise with acuity because ESI levels are themselves
    # defined by expected resource intensity (sicker patients get more workup).
    lab_order_prob: Dict[int, float] = field(default_factory=lambda: {
        1: 0.95, 2: 0.90, 3: 0.65, 4: 0.30, 5: 0.10,
    })
    imaging_order_prob: Dict[int, float] = field(default_factory=lambda: {
        1: 0.85, 2: 0.70, 3: 0.50, 4: 0.35, 5: 0.15,
    })
    # Of patients imaged, the share getting CT (slower) vs plain X-ray (fast).
    ct_given_imaging_prob: Dict[int, float] = field(default_factory=lambda: {
        1: 0.85, 2: 0.70, 3: 0.45, 4: 0.20, 5: 0.10,
    })

    # Turnaround times (minutes, triangular) from published ED benchmarks:
    # routine labs ~60 min door-to-result, plain film <30 min, CT with read
    # 60-90 min. Within one round, labs and imaging run concurrently.
    lab_turnaround_minutes: tuple = (45, 60, 95)
    xray_turnaround_minutes: tuple = (15, 25, 45)
    ct_turnaround_minutes: tuple = (50, 80, 120)

    # Serial workup cycles by ESI. Emergent (ESI 2) patients get the most
    # (serial troponins, repeat imaging, reassessment) and have the longest
    # stays in the real data; resuscitation (ESI 1) patients are stabilized and
    # moved out fast; low-acuity patients get little or none. These counts are
    # CALIBRATED so per-acuity median LOS reproduces the real MIMIC gradient,
    # so LOS is a calibrated output of the model, not a held-out prediction.
    diagnostic_rounds: Dict[int, int] = field(default_factory=lambda: {
        1: 2, 2: 3, 3: 4, 4: 2, 5: 1,
    })

    # Specialist consult wait, concentrated in higher acuity. Added once per
    # patient (probabilistically) on top of the diagnostic rounds.
    consult_prob: Dict[int, float] = field(default_factory=lambda: {
        1: 0.55, 2: 0.45, 3: 0.20, 4: 0.05, 5: 0.01,
    })
    consult_wait_minutes: tuple = (45, 90, 180)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    def __post_init__(self):
        total = sum(self.esi_distribution.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"esi_distribution must sum to 1.0, got {total:.4f}"
            )

        # Every per-ESI dict must cover all five levels, so a typo fails loudly
        # at construction rather than KeyError-ing mid-simulation.
        per_esi_dicts = {
            "esi_distribution": self.esi_distribution,
            "triage_time_minutes": self.triage_time_minutes,
            "treatment_time_minutes": self.treatment_time_minutes,
            "admit_probability": self.admit_probability,
            "lab_order_prob": self.lab_order_prob,
            "imaging_order_prob": self.imaging_order_prob,
            "ct_given_imaging_prob": self.ct_given_imaging_prob,
            "diagnostic_rounds": self.diagnostic_rounds,
            "consult_prob": self.consult_prob,
        }
        for esi in range(1, 6):
            for name, d in per_esi_dicts.items():
                if esi not in d:
                    raise ValueError(f"{name} missing ESI {esi}")

    @classmethod
    def from_data(cls, params_path="calibration/calibration_params.json") -> "Config":
        """Construct a Config calibrated to real MIMIC-IV-ED distributions.

        Only observable inputs are overridden. Service times and absolute
        arrival rate stay at defaults for the reasons documented above. Raises
        a clear error if the params file is missing or malformed rather than
        silently using synthetic defaults, so a calibrated run can never be
        mistaken for an uncalibrated one.
        """
        path = Path(params_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Calibration params not found at {path}. "
                f"Run scripts/ed_calibration.py first to generate it."
            )

        params = json.loads(path.read_text())

        # ---- esi_distribution from acuity_mix -------------------------------
        # acuity_mix has keys "1".."5" plus "unknown". The five known levels
        # must sum to 1.0 (validated in __post_init__), so the unknown mass is
        # removed and the remainder renormalized. Renormalizing keeps the
        # observed shape intact and adds no assumption about what the missing
        # triage acuities were.
        mix = params["acuity_mix"]
        known = {int(k): float(mix[k]) for k in ("1", "2", "3", "4", "5") if k in mix}
        if len(known) != 5:
            raise ValueError(f"acuity_mix missing levels; got {sorted(known)}")
        known_total = sum(known.values())
        if known_total <= 0:
            raise ValueError("acuity_mix known levels sum to zero")
        esi_distribution = {esi: known[esi] / known_total for esi in range(1, 6)}

        # Fold any float residual into the largest bucket so the 1.0 check
        # in __post_init__ always passes cleanly.
        drift = 1.0 - sum(esi_distribution.values())
        if drift:
            top = max(esi_distribution, key=esi_distribution.get)
            esi_distribution[top] = round(esi_distribution[top] + drift, 10)

        # ---- admit_probability from admit_rate_by_acuity --------------------
        # Per-ESI admit rate is an observable input. Where a level is too sparse
        # for its own rate, fall back to the overall observed admit rate (still
        # data-derived) rather than the synthetic default.
        admit = params.get("admit_rate_by_acuity", {})
        overall = float(admit.get("overall", 0.0))
        admit_probability = {esi: float(admit.get(str(esi), overall)) for esi in range(1, 6)}

        return cls(
            esi_distribution=esi_distribution,
            admit_probability=admit_probability,
        )


DEFAULT_CONFIG = Config()
