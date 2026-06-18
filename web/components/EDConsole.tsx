"use client";

import { useMemo, useState } from "react";
import gridData from "@/data/grid.json";

// ---- Types matching the grid JSON shape ----
type Metric = { abs: number; delta: number; ci_low: number; ci_high: number };
type Metrics = Record<string, Metric>;
type Cell = {
  load: number;
  n_physicians: number;
  n_ed_beds: number;
  n_triage_nurses: number;
  is_baseline: boolean;
  metrics: Metrics;
};
type Grid = {
  meta: {
    generated: string;
    replications: number;
    levers: Record<string, number[]>;
    loads: number[];
    metric_labels: Record<string, string>;
  };
  baselines: Record<string, { config: Record<string, number>; metrics: Record<string, number> }>;
  cells: Cell[];
};

const GRID = gridData as unknown as Grid;
const LEVERS = GRID.meta.levers;
const LOADS = GRID.meta.loads;
const LOAD_NAMES: Record<number, string> = { 12: "Heavy", 15: "Moderate", 18: "Light" };

const fmtDelta = (d: number) =>
  Math.abs(d) < 0.05 ? "0" : (d > 0 ? "+" : "") + d.toFixed(0);

// Display floor: a real ED can't have a sub-15-min median LOS; clamp so no
// edge-case grid cell ever shows a physically implausible number.
const safeLOS = (v: number) => Math.max(v, 15);

export default function EDConsole() {
  const [physicians, setPhysicians] = useState(LEVERS.n_physicians[0]);
  const [beds, setBeds] = useState(LEVERS.n_ed_beds[0]);
  const [triage, setTriage] = useState(LEVERS.n_triage_nurses[0]);
  const [load, setLoad] = useState(LOADS[0]);

  const baseLOS = GRID.baselines[String(load)].metrics.total_los_min_median;

  const cell = useMemo(
    () =>
      GRID.cells.find(
        (c) =>
          c.load === load &&
          c.n_physicians === physicians &&
          c.n_ed_beds === beds &&
          c.n_triage_nurses === triage
      ),
    [physicians, beds, triage, load]
  );

  const reset = () => {
    setPhysicians(LEVERS.n_physicians[0]);
    setBeds(LEVERS.n_ed_beds[0]);
    setTriage(LEVERS.n_triage_nurses[0]);
  };

  if (!cell) return null;

  const los = cell.metrics.total_los_min_median;
  const losAbs = safeLOS(los.abs);
  const isBetter = los.delta < -5;
  const addedPhys = physicians - LEVERS.n_physicians[0];
  const addedBeds = beds - LEVERS.n_ed_beds[0];

  const maxV = baseLOS * 1.05;

  // Verdict copy
  let verdictClass = "verdict";
  let verdict: React.ReactNode = "";
  if (cell.is_baseline) {
    verdict = "This is the crowded department. Start adding capacity and see what moves the needle.";
  } else if (isBetter) {
    verdictClass = "verdict binding";
    verdict = (
      <>
        Length of stay dropped <strong>{Math.abs(los.delta).toFixed(0)} minutes</strong>.{" "}
        {addedPhys > 0
          ? "Adding physicians is doing the work here."
          : "That came from relieving the binding resource."}
      </>
    );
  } else if (addedBeds > 0 && addedPhys === 0) {
    verdict = (
      <>
        You added {addedBeds} ED bed{addedBeds > 1 ? "s" : ""} and almost nothing changed. Beds are
        not the constraint. Try physicians.
      </>
    );
  } else {
    verdict = "No meaningful change. This lever is not the bottleneck.";
  }

  const Lever = ({
    id,
    name,
    tag,
    tagClass,
    hot,
    value,
    onChange,
  }: {
    id: string;
    name: string;
    tag: string;
    tagClass: string;
    hot?: boolean;
    value: number;
    onChange: (v: number) => void;
  }) => {
    const values = LEVERS[id];
    const idx = values.indexOf(value);
    const diff = value - values[0];
    return (
      <div className="lever">
        <div className="lever-top">
          <span className="lever-name">
            {name}
            <span className={`tag ${tagClass}`}>{tag}</span>
          </span>
          <span className="lever-val">
            {value}
            {diff > 0 && <span className="base"> (+{diff})</span>}
          </span>
        </div>
        <input
          type="range"
          className={hot ? "hot" : ""}
          min={0}
          max={values.length - 1}
          step={1}
          value={idx}
          onChange={(e) => onChange(values[+e.target.value])}
          aria-label={name}
        />
      </div>
    );
  };

  const Mini = ({ label, m, pct }: { label: string; m: Metric; pct?: boolean }) => {
    let cls = "mini-delta none";
    let text = "no change";
    if (!pct && Math.abs(m.delta) >= 0.5) {
      cls = "mini-delta " + (m.delta < 0 ? "better" : "worse");
      text = fmtDelta(m.delta);
    } else if (pct) {
      text = "—";
    }
    return (
      <div className="mini">
        <div className="mini-label">{label}</div>
        <div className="mini-value">
          {m.abs.toFixed(0)}
          {pct ? "%" : ""}
        </div>
        <div className={cls}>{text}</div>
      </div>
    );
  };

  return (
    <>
      <div className="console">
        <div className="controls">
          <div className="section-label">Capacity levers</div>
          <Lever id="n_physicians" name="Physicians" tag="binding" tagClass="binding" hot value={physicians} onChange={setPhysicians} />
          <Lever id="n_ed_beds" name="ED beds" tag="little effect" tagClass="inert" value={beds} onChange={setBeds} />
          <Lever id="n_triage_nurses" name="Triage nurses" tag="little effect" tagClass="inert" value={triage} onChange={setTriage} />

          <div className="section-label" style={{ marginTop: 30 }}>
            Patient arrival rate
          </div>
          <div className="load-row">
            {LOADS.map((l) => (
              <button
                key={l}
                className={"load-btn" + (l === load ? " active" : "")}
                onClick={() => setLoad(l)}
              >
                {(LOAD_NAMES[l] || l) + " · " + l + "m"}
              </button>
            ))}
          </div>

          <button className="reset" onClick={reset}>
            Reset to crowded baseline
          </button>
        </div>

        <div className="readout">
          <div className="section-label">Median length of stay</div>
          <div className="hero-metric">
            <div className="hero-value" style={{ color: isBetter ? "var(--signal)" : "var(--ink)" }}>
              {losAbs.toFixed(0)}
              <span className="unit"> min</span>
            </div>
            <div className={"hero-delta " + (isBetter ? "better" : "none")}>
              {isBetter
                ? `${fmtDelta(los.delta)} min vs baseline   ·   95% CI [${los.ci_low.toFixed(0)}, ${los.ci_high.toFixed(0)}]`
                : cell.is_baseline
                ? "crowded baseline"
                : `${fmtDelta(los.delta)} min vs baseline   ·   no meaningful change`}
            </div>
          </div>

          <div className="bar-block">
            <div className="bar-row">
              <span className="bar-key">Baseline</span>
              <div className="bar-track">
                <div className="bar-fill base" style={{ width: (baseLOS / maxV) * 100 + "%" }} />
              </div>
              <span className="bar-num">{baseLOS.toFixed(0)}</span>
            </div>
            <div className="bar-row">
              <span className="bar-key">Now</span>
              <div className="bar-track">
                <div className="bar-fill now" style={{ width: (losAbs / maxV) * 100 + "%" }} />
              </div>
              <span className="bar-num">{losAbs.toFixed(0)}</span>
            </div>
          </div>

          <div className="mini-grid">
            <Mini label="Door to doctor" m={cell.metrics.door_to_doc_min_median} />
            <Mini label="Boarding time" m={cell.metrics.boarding_min_median} />
            <Mini label="Admit rate" m={cell.metrics.admit_rate_pct} pct />
          </div>

          <div className={verdictClass}>{verdict}</div>
        </div>
      </div>

      <div className="foot">
        {GRID.meta.replications} replications per configuration · common random numbers · 95%
        confidence intervals · generated {GRID.meta.generated}
      </div>
    </>
  );
}
