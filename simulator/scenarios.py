"""
Scenario comparison engine for the ED digital twin.

A single simulation run is noisy: one random week of arrivals tells you little
about whether an intervention actually helps. This module runs each scenario
across many replications (different random seeds), collects the distribution of
each headline metric, and reports the difference between scenarios with a
confidence interval so the effect can be distinguished from random variation.

Variance reduction: scenarios are compared using *common random numbers*. Every
scenario is run on the same set of seeds, so replication i of the baseline and
replication i of the intervention see the same arrival stream. The paired
difference isolates the treatment effect rather than seed luck, which tightens
the confidence interval substantially for the same number of runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from statistics import mean, stdev
from typing import Callable, Dict, List

from simulator.config import Config
from simulator.ed_sim import EDSimulation


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    """A named simulation scenario defined as overrides on the base Config.

    overrides maps Config field names to values, e.g. {"n_ed_beds": 45}.
    An empty overrides dict is the baseline.
    """

    name: str
    overrides: Dict[str, object] = field(default_factory=dict)

    def build_config(self, base: Config, seed: int) -> Config:
        """Return a Config that is the base plus this scenario's overrides,
        pinned to the given replication seed."""
        return replace(base, random_seed=seed, **self.overrides)


# ---------------------------------------------------------------------------
# Replication results
# ---------------------------------------------------------------------------
# The headline metrics we track across replications. Each maps to a key
# returned by MetricsCollector.summary(). Lower is better for all of these.
TRACKED_METRICS: Dict[str, str] = {
    "door_to_doc_min_median": "Median door-to-doc (min)",
    "total_los_min_median": "Median length of stay (min)",
    "boarding_min_median": "Median boarding time (min)",
    "admit_rate_pct": "Admit rate (%)",
}


@dataclass
class ScenarioResult:
    """Holds the per-replication metric values for one scenario."""

    name: str
    # metric key -> list of values, one per replication
    samples: Dict[str, List[float]]

    def metric_mean(self, key: str) -> float:
        return mean(self.samples[key])

    def metric_stdev(self, key: str) -> float:
        vals = self.samples[key]
        return stdev(vals) if len(vals) > 1 else 0.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
class ScenarioRunner:
    """Runs scenarios across replications and computes comparisons."""

    def __init__(self, base_config: Config, n_replications: int = 30,
                 base_seed: int = 1000):
        self.base_config = base_config
        self.n_replications = n_replications
        # The shared seed list -> common random numbers across scenarios.
        self.seeds: List[int] = [base_seed + i for i in range(n_replications)]

    def run_scenario(self, scenario: Scenario,
                     progress: Callable[[str, int, int], None] | None = None
                     ) -> ScenarioResult:
        """Run one scenario across all replication seeds."""
        samples: Dict[str, List[float]] = {k: [] for k in TRACKED_METRICS}

        for i, seed in enumerate(self.seeds, start=1):
            config = scenario.build_config(self.base_config, seed)
            metrics = EDSimulation(config).run()
            summary = metrics.summary()

            for key in TRACKED_METRICS:
                # Some metrics can be absent if no patient reached that stage
                # in a given replication; treat missing as NaN-skip by using
                # the run's value only when present.
                value = summary.get(key)
                if value is not None:
                    samples[key].append(float(value))

            if progress:
                progress(scenario.name, i, self.n_replications)

        return ScenarioResult(name=scenario.name, samples=samples)

    def compare(self, baseline: ScenarioResult,
                intervention: ScenarioResult) -> Dict[str, Dict[str, float]]:
        """Paired comparison of intervention vs baseline for each metric.

        Returns metric key -> {baseline_mean, intervention_mean, delta,
        ci_low, ci_high, pct_change}. The confidence interval is on the
        paired difference (intervention - baseline) per replication, using
        the t-distribution at 95%.
        """
        results: Dict[str, Dict[str, float]] = {}

        for key in TRACKED_METRICS:
            b_vals = baseline.samples[key]
            i_vals = intervention.samples[key]
            # Pair only where both scenarios produced a value (common seeds
            # mean these line up replication-for-replication).
            n = min(len(b_vals), len(i_vals))
            if n == 0:
                continue

            diffs = [i_vals[j] - b_vals[j] for j in range(n)]
            delta = mean(diffs)
            b_mean = mean(b_vals[:n])
            i_mean = mean(i_vals[:n])

            if n > 1:
                sd = stdev(diffs)
                se = sd / (n ** 0.5)
                t = _t_critical_95(n - 1)
                margin = t * se
            else:
                margin = 0.0

            pct = (delta / b_mean * 100.0) if b_mean else 0.0

            results[key] = {
                "baseline_mean": round(b_mean, 1),
                "intervention_mean": round(i_mean, 1),
                "delta": round(delta, 1),
                "ci_low": round(delta - margin, 1),
                "ci_high": round(delta + margin, 1),
                "pct_change": round(pct, 1),
                "n": n,
            }

        return results


# ---------------------------------------------------------------------------
# t critical values (two-sided, 95%) for small samples
# ---------------------------------------------------------------------------
# Avoids a scipy dependency. Covers common replication counts; falls back to
# the normal approximation (1.96) for large df.
_T_TABLE_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    40: 2.021, 50: 2.009, 60: 2.000, 120: 1.980,
}


def _t_critical_95(df: int) -> float:
    """Two-sided 95% t critical value for the given degrees of freedom."""
    if df in _T_TABLE_95:
        return _T_TABLE_95[df]
    # Use nearest lower tabulated df for a slightly conservative interval.
    keys = sorted(_T_TABLE_95)
    for k in reversed(keys):
        if k <= df:
            return _T_TABLE_95[k]
    return 1.96
