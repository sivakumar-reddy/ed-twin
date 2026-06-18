# Bottleneck Analysis: What Actually Constrains ED Throughput

## Question

When an emergency department is crowded, the instinct is to add beds. This
analysis tests that instinct directly. Using the ED digital twin, it asks a
narrower and more useful question: of the capacity levers a hospital could
pull, which one actually moves throughput, and by how much?

## Method

The analysis runs the simulation as a controlled experiment rather than a
single observation.

**Replications.** A single simulated week is one random draw. It cannot
distinguish a real effect from a lucky arrival pattern. Each scenario is
therefore run across 30 replications, each seeded differently, and the
distribution of outcomes is compared rather than any one run.

**Common random numbers.** Every scenario is run on the same set of 30 seeds,
so replication i of the baseline and replication i of an intervention see the
identical arrival stream. The comparison is then a paired difference, which
removes seed-to-seed variation from the estimate and isolates the effect of the
intervention itself. This is a standard variance reduction technique in
discrete event simulation and it tightens the confidence intervals materially
for the same number of runs.

**Confidence intervals.** For each metric, the paired per-replication
differences are summarized as a mean delta with a 95% confidence interval based
on the t-distribution. An interval that excludes zero indicates an effect that
is unlikely to be noise. An interval that straddles zero indicates no
detectable effect.

**Levers tested.** Each lever is a single change to one resource, holding all
else fixed:

| Lever | Change |
|-------|--------|
| ED beds | +5 |
| Physicians | +1 |
| Triage nurses | +1 |
| Inpatient beds | +10 |

**Load.** The baseline arrival rate leaves the department with slack, where no
resource is binding and nothing changes throughput. To find the constraint, the
sweep is run under load: mean interarrival reduced from the baseline to 12
minutes, then repeated at 15 minutes as a sensitivity check.

## Finding

Physician capacity is the binding constraint. Adding beds does effectively
nothing.

At a 12 minute interarrival load (30 replications, ranked by effect on median
length of stay):

| Lever | Median LOS change | 95% CI | Meaningful |
|-------|------------------:|:------:|:----------:|
| +1 physician | -296.5 min | [-366.2, -226.8] | yes |
| +10 inpatient beds | -107.8 min | [-164.0, -51.7] | yes |
| +5 ED beds | -13.9 min | [-83.7, +56.0] | no |
| +1 triage nurse | +63.7 min | [-59.7, +187.1] | no |

A single additional physician cuts median length of stay by roughly five hours.
Ten additional inpatient beds help, at about a third of that effect. Five
additional ED beds produce no detectable change: the confidence interval
straddles zero. Triage nurses are not constraining either.

## Sensitivity check

The result is not an artifact of one load setting. Re-running the sweep at a
lighter 15 minute interarrival load preserves the same ranking:

| Lever | Median LOS change | 95% CI | Meaningful |
|-------|------------------:|:------:|:----------:|
| +1 physician | -66.5 min | [-80.8, -52.2] | yes |
| +10 inpatient beds | -18.7 min | [-29.0, -8.5] | yes |
| +1 triage nurse | -1.8 min | [-19.9, +16.2] | no |
| +5 ED beds | -1.1 min | [-9.2, +6.9] | no |

Physician remains the top lever at both loads, and the effect scales with load
in the direction queueing theory predicts: as utilization rises toward
capacity, relieving the binding resource pays off progressively more. Beds and
triage stay flat at both loads, which is the expected behavior of a non
constraining resource.

## Interpretation

The crowded ED problem is commonly framed as a space problem and answered with
more beds. Under this model, beds are not the constraint at either load tested.
Patients are not waiting on a place to be; they are waiting on a physician to be
seen and treated. Capacity added anywhere other than the binding resource sits
idle and changes nothing downstream.

The practical implication is that a throughput investment should be directed at
physician staffing first, with inpatient bed capacity as a secondary lever, and
that ED bed expansion should not be expected to improve length of stay on its
own. The value of the digital twin is that this conclusion is reached, and
quantified with a confidence interval, before any change is made to a real
department.

## Reproduce

From the project root with the virtual environment active:

```
python -m scripts.07_run_scenarios --sweep --load 12
python -m scripts.07_run_scenarios --sweep --load 15
```

Each run writes a tidy CSV of the results to `data/scenarios/`.
