"""Quick diagnostic to verify Patient.sample_esi produces the configured distribution."""

import sys
import random
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.config import Config
from simulator.patient import Patient


def main():
    c = Config()
    rng = random.Random(42)

    n_samples = 10_000
    samples = [Patient.sample_esi(c.esi_distribution, rng) for _ in range(n_samples)]
    counts = Counter(samples)

    print(f"Sampled {n_samples} ESI values from config distribution:")
    print()
    print(f"  {'ESI':<6} {'configured':>12} {'observed':>12} {'count':>8}")
    print(f"  {'-'*6} {'-'*12} {'-'*12} {'-'*8}")
    for esi in sorted(c.esi_distribution.keys()):
        configured_pct = c.esi_distribution[esi] * 100
        observed_pct = 100 * counts[esi] / n_samples
        print(f"  {esi:<6} {configured_pct:>11.1f}% {observed_pct:>11.1f}% {counts[esi]:>8}")


if __name__ == "__main__":
    main()