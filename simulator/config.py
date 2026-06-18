"""
Simulation configuration parameters.

All tunable knobs for the ED simulation live here. Default values
are drawn from published US ED operations literature; calibrated
values from real data are loaded via Config.from_data() once
analytical data is available.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Config:
    # -------------------------------------------------------------------------
    # Simulation duration
    # -------------------------------------------------------------------------
    simulation_minutes: int = 10080  # 1 week of operations
    random_seed: int = 42

    # -------------------------------------------------------------------------
    # Resources (counts)
    # -------------------------------------------------------------------------
    n_triage_nurses: int = 3
    n_ed_beds: int = 40
    n_physicians: int = 4
    n_inpatient_beds: int = 60

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
    # Validation
    # -------------------------------------------------------------------------
    def __post_init__(self):
        total = sum(self.esi_distribution.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"esi_distribution must sum to 1.0, got {total:.4f}"
            )

        for esi in range(1, 6):
            if esi not in self.esi_distribution:
                raise ValueError(f"esi_distribution missing ESI {esi}")
            if esi not in self.triage_time_minutes:
                raise ValueError(f"triage_time_minutes missing ESI {esi}")
            if esi not in self.treatment_time_minutes:
                raise ValueError(f"treatment_time_minutes missing ESI {esi}")
            if esi not in self.admit_probability:
                raise ValueError(f"admit_probability missing ESI {esi}")


DEFAULT_CONFIG = Config()