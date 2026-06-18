"""
Run an ED simulation with default config and print the summary.

Entry point for Phase 3. Later we'll extend this with CLI args
to override config values for scenario testing.
"""

import sys
from pathlib import Path

# Make `simulator` package importable when running from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.config import Config
from simulator.ed_sim import EDSimulation


def main():
    config = Config()
    print(f"Running ED simulation for {config.simulation_minutes} minutes "
          f"({config.simulation_minutes / 60 / 24:.1f} days)")
    print(f"Config: {config.n_triage_nurses} triage nurses, "
          f"{config.n_ed_beds} ED beds, {config.n_physicians} physicians, "
          f"{config.n_inpatient_beds} inpatient beds")
    print(f"Mean inter-arrival: {config.mean_interarrival_minutes} min")
    print()

    sim = EDSimulation(config)
    metrics = sim.run()
    metrics.print_summary()


if __name__ == "__main__":
    main()