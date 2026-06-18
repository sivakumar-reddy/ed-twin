"""
Core ED simulation engine using SimPy.

Models patient flow through 5 stages: arrival -> triage -> bed wait
-> treatment -> disposition. Uses 4 resource pools (triage nurses,
ED beds, physicians, inpatient beds) with priority-based queueing.

Higher ESI patients (sicker, lower ESI number) take priority for beds
and physicians. The simulation is fully deterministic given the
random_seed in Config.
"""

from __future__ import annotations
import random
from typing import Optional

import simpy

from simulator.config import Config
from simulator.patient import Patient
from simulator.metrics import MetricsCollector


class EDSimulation:
    """Runs a full ED simulation against a Config and returns a MetricsCollector."""

    def __init__(self, config: Config):
        self.config = config
        self.rng = random.Random(config.random_seed)
        self.metrics = MetricsCollector()

        # SimPy environment and resources (constructed in run())
        self.env: Optional[simpy.Environment] = None
        self.triage_nurses: Optional[simpy.PriorityResource] = None
        self.ed_beds: Optional[simpy.PriorityResource] = None
        self.physicians: Optional[simpy.PriorityResource] = None
        self.inpatient_beds: Optional[simpy.Resource] = None

        self._next_patient_id = 1

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _triangular(self, low_mode_high: tuple) -> float:
        low, mode, high = low_mode_high
        return self.rng.triangular(low, mode, high)

    # -------------------------------------------------------------------------
    # The arrival process (Poisson via exponential inter-arrival times)
    # -------------------------------------------------------------------------
    def arrival_process(self):
        """Generates patients at exponentially distributed intervals."""
        while True:
            interarrival = self.rng.expovariate(
                1.0 / self.config.mean_interarrival_minutes
            )
            yield self.env.timeout(interarrival)

            esi = Patient.sample_esi(self.config.esi_distribution, self.rng)
            patient = Patient(
                patient_id=self._next_patient_id,
                arrival_time=self.env.now,
                esi=esi,
            )
            self._next_patient_id += 1
            self.env.process(self.patient_flow(patient))

    # -------------------------------------------------------------------------
    # Per-patient flow through the 5 stages
    # -------------------------------------------------------------------------
    def patient_flow(self, patient: Patient):
        # ESI 1 = highest priority (lowest priority number in SimPy)
        priority = patient.esi

        # ---- Stage 1: Triage ----
        with self.triage_nurses.request(priority=priority) as req:
            yield req
            patient.triage_start_time = self.env.now
            triage_duration = self._triangular(
                self.config.triage_time_minutes[patient.esi]
            )
            yield self.env.timeout(triage_duration)
            patient.triage_end_time = self.env.now

        # ---- Stage 2: Wait for ED bed ----
        with self.ed_beds.request(priority=priority) as bed_req:
            yield bed_req
            patient.bed_assigned_time = self.env.now

            # ---- Stage 3: Treatment (requires physician + bed) ----
            with self.physicians.request(priority=priority) as doc_req:
                yield doc_req
                patient.treatment_start_time = self.env.now
                treatment_duration = self._triangular(
                    self.config.treatment_time_minutes[patient.esi]
                )
                yield self.env.timeout(treatment_duration)
                patient.treatment_end_time = self.env.now

            # ---- Stage 4: Disposition decision ----
            disposition_duration = self._triangular(
                self.config.disposition_decision_minutes
            )
            yield self.env.timeout(disposition_duration)
            patient.disposition_decision_time = self.env.now

            # Probabilistic admit decision based on ESI
            admit_prob = self.config.admit_probability[patient.esi]
            if self.rng.random() < admit_prob:
                patient.admitted_to_inpatient = True

                # ---- Stage 5a: Wait for inpatient bed (boarding) ----
                # During this wait, the patient still occupies the ED bed.
                # That IS the boarding bottleneck mechanic.
                ip_req = self.inpatient_beds.request()
                yield ip_req
                patient.inpatient_bed_time = self.env.now
                patient.departure_time = self.env.now

                # Hold the inpatient bed for the patient's stay in the
                # background, then release. Decouples ED throughput from
                # inpatient throughput.
                inpatient_los = self._triangular(self.config.inpatient_los_minutes)
                self.env.process(self._hold_inpatient_bed(ip_req, inpatient_los))
            else:
                # ---- Stage 5b: Discharge home ----
                patient.departure_time = self.env.now

        # Record finished patient
        self.metrics.record_patient(patient)

    # -------------------------------------------------------------------------
    # Monitoring processes for time-series resource utilization
    # -------------------------------------------------------------------------
    def monitor(self, sample_every_minutes: int = 15):
        """Periodically snapshot bed occupancy and queue length."""
        while True:
            yield self.env.timeout(sample_every_minutes)
            self.metrics.record_bed_occupancy(
                self.env.now,
                self.ed_beds.count,
            )
            self.metrics.record_queue_length(
                self.env.now,
                len(self.ed_beds.queue),
            )

    # -------------------------------------------------------------------------
    # Inpatient bed turnover (background process)
    # -------------------------------------------------------------------------
    def _hold_inpatient_bed(self, request, duration: float):
        """
        Holds an inpatient bed for the duration of the inpatient stay,
        then releases. Runs as a fire-and-forget background process
        per admitted patient.
        """
        yield self.env.timeout(duration)
        self.inpatient_beds.release(request)

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------
    def run(self) -> MetricsCollector:
        """Run the simulation for the configured duration and return metrics."""
        self.env = simpy.Environment()

        # Priority resources for triage, ED beds, physicians.
        # Inpatient beds are FIFO (by then, priority is "who decided first").
        self.triage_nurses = simpy.PriorityResource(
            self.env, capacity=self.config.n_triage_nurses
        )
        self.ed_beds = simpy.PriorityResource(
            self.env, capacity=self.config.n_ed_beds
        )
        self.physicians = simpy.PriorityResource(
            self.env, capacity=self.config.n_physicians
        )
        self.inpatient_beds = simpy.Resource(
            self.env, capacity=self.config.n_inpatient_beds
        )

        # Kick off the arrival generator and the monitor
        self.env.process(self.arrival_process())
        self.env.process(self.monitor(sample_every_minutes=15))

        # Run
        self.env.run(until=self.config.simulation_minutes)

        return self.metrics