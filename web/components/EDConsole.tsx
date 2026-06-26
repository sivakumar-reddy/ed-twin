"use client";

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  LEVERS, METRICS, RES, BASE, TOUR, type LeverKey, type MetricKey,
  leverByKey, pts, pointAt, nearestValue, baselineValue, snapVal,
  geometry, buildStaticSvg, opState, annoHandoff, interpret, explainText,
  thresholdState, chartContext, cmpRows, meterModel, simPatients, flowModel,
  type SweepPoint,
} from "../lib/edModel";
import { ED_STYLES } from "./edStyles";

/** Animated integer that tweens from its previous target, like the original count-up. */
function CountUp({ value }: { value: number | null | undefined }) {
  const [disp, setDisp] = useState<number>(typeof value === "number" ? value : 0);
  const fromRef = useRef<number>(typeof value === "number" ? value : 0);
  const rafRef = useRef<number | null>(null);
  useEffect(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (value == null) { fromRef.current = 0; return; }
    const from = fromRef.current; fromRef.current = value;
    const to = value, t0 = performance.now(), dur = 420;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      setDisp(from + (to - from) * e);
      if (k < 1) rafRef.current = requestAnimationFrame(step);
      else { setDisp(to); rafRef.current = null; }
    };
    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [value]);
  if (value == null) return <>n/a</>;
  return <>{Math.round(disp)}</>;
}

export default function EDConsole() {
  const [leverKey, setLeverKey] = useState<LeverKey>("n_inpatient_beds");
  const [metric, setMetric] = useState<MetricKey>("board");
  const [value, setValue] = useState<number>(BASE.n_inpatient_beds);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 880, h: 560 });
  const [tour, setTour] = useState<{ active: boolean; step: number }>({ active: false, step: 0 });

  const chartRef = useRef<SVGSVGElement | null>(null);
  const gstaticRef = useRef<SVGGElement | null>(null);
  const stagesRef = useRef<HTMLDivElement | null>(null);
  const spineRef = useRef<HTMLDivElement | null>(null);
  const drawRef = useRef<boolean>(true);          // animate the curve draw on lever/metric switch
  const rafRef = useRef<number | null>(null);     // value-tween loop (reset + tour)
  const tourSaved = useRef<{ leverKey: LeverKey; metric: MetricKey; value: number } | null>(null);
  const tourTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const lever = leverByKey(leverKey);
  const arr = pts(leverKey);
  const p: SweepPoint = pointAt(leverKey, value) || arr[0];
  const geom = useMemo(() => geometry(leverKey, metric, size.w, size.h), [leverKey, metric, size.w, size.h]);

  const cancelRaf = useCallback(() => { if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; } }, []);
  const animateValueTo = useCallback((key: LeverKey, from: number, to: number, dur: number) => {
    cancelRaf();
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      const v = snapVal(key, from + (to - from) * e);
      setValue((prev) => (v !== prev ? v : prev));
      if (k < 1) rafRef.current = requestAnimationFrame(step);
      else rafRef.current = null;
    };
    rafRef.current = requestAnimationFrame(step);
  }, [cancelRaf]);

  // measure the chart container; drive size state
  useLayoutEffect(() => {
    const el = chartRef.current; if (!el) return;
    const measure = () => { const r = el.getBoundingClientRect(); setSize({ w: Math.round(r.width || 880), h: Math.round(r.height || 560) }); };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // static chart layer: rebuilt only on lever / metric / size change (not on value)
  useLayoutEffect(() => {
    if (!gstaticRef.current) return;
    gstaticRef.current.innerHTML = buildStaticSvg(geom, leverKey, metric, drawRef.current);
    drawRef.current = false;
  }, [geom, leverKey, metric]);

  // operating-point marker + context-aware annotation handoff (per value)
  const op = opState(geom, p, metric);
  const xop = geom.X(value);
  useLayoutEffect(() => {
    const g = gstaticRef.current; if (!g) return;
    const h = annoHandoff(geom, p, xop);
    g.querySelectorAll<SVGGElement>(".anno").forEach((el) => {
      const k = el.getAttribute("data-kind") || "";
      const st = (h as Record<string, { opacity: number; ty: number }>)[k];
      if (!st) return;
      el.style.opacity = st.opacity.toFixed(2);
      if (k === "boarding" || k === "critical") el.style.transform = `translateY(${st.ty.toFixed(1)}px)`;
    });
  }, [geom, p, xop]);

  // patient flow + spine-pulse anchoring
  const flow = useMemo(() => flowModel(p), [p]);
  useLayoutEffect(() => {
    if (!flow.propagate || !stagesRef.current || !spineRef.current) return;
    const sEl = stagesRef.current;
    const bEl = sEl.querySelector<HTMLElement>('[data-stage="Boarding"]');
    const eEl = sEl.querySelector<HTMLElement>('[data-stage="ED bed"]');
    if (bEl && eEl) {
      spineRef.current.style.setProperty("--p-from", bEl.offsetTop + "px");
      spineRef.current.style.setProperty("--p-to", eEl.offsetTop + "px");
    }
  }, [flow, size.h]);

  // ----- control handlers -----
  const pickLever = useCallback((k: LeverKey) => {
    cancelRaf();
    drawRef.current = true;
    setLeverKey(k);
    setMetric(leverByKey(k).defMetric);
    setValue(baselineValue(k));
  }, [cancelRaf]);

  const pickMetric = useCallback((m: MetricKey) => { drawRef.current = true; setMetric(m); }, []);

  const onSlider = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    cancelRaf();
    setValue(nearestValue(leverKey, parseInt(e.target.value, 10)));
  }, [leverKey, cancelRaf]);

  const resetTarget = BASE[leverKey] !== undefined ? BASE[leverKey] : pts(leverKey)[0].value;
  const onReset = useCallback(() => {
    if (value !== resetTarget) animateValueTo(leverKey, value, resetTarget, 650);
  }, [value, resetTarget, leverKey, animateValueTo]);

  // ----- guided tour -----
  const applyStep = useCallback((i: number) => {
    const st = TOUR[i];
    cancelRaf();
    if (tourTimer.current) clearTimeout(tourTimer.current);
    drawRef.current = true;
    setLeverKey(st.lever);
    setMetric(st.metric);
    setValue(snapVal(st.lever, st.from));
    if (st.to !== st.from) {
      tourTimer.current = setTimeout(() => {
        animateValueTo(st.lever, snapVal(st.lever, st.from), snapVal(st.lever, st.to), 1300);
      }, 440);
    }
  }, [animateValueTo, cancelRaf]);

  const startTour = useCallback(() => {
    tourSaved.current = { leverKey, metric, value };
    setTour({ active: true, step: 0 });
    applyStep(0);
  }, [leverKey, metric, value, applyStep]);

  const goStep = useCallback((i: number) => { setTour((t) => ({ ...t, step: i })); applyStep(i); }, [applyStep]);

  const endTour = useCallback(() => {
    cancelRaf();
    if (tourTimer.current) clearTimeout(tourTimer.current);
    setTour({ active: false, step: 0 });
    const s = tourSaved.current;
    if (s) { drawRef.current = true; setLeverKey(s.leverKey); setMetric(s.metric); setValue(s.value); }
  }, [cancelRaf]);

  // keyboard navigation while touring
  useEffect(() => {
    if (!tour.active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") endTour();
      else if (e.key === "ArrowRight") { tour.step < TOUR.length - 1 ? goStep(tour.step + 1) : endTour(); }
      else if (e.key === "ArrowLeft") { if (tour.step > 0) goStep(tour.step - 1); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [tour.active, tour.step, goStep, endTour]);

  useEffect(() => () => { cancelRaf(); if (tourTimer.current) clearTimeout(tourTimer.current); }, [cancelRaf]);

  // ----- derived display values -----
  const th = thresholdState(p);
  const I = interpret(p);
  const losNull = p.los_median === null || p.los_median === undefined;
  const rows = cmpRows(p);
  const mPhys = meterModel(p.util_phys), mBed = meterModel(p.util_bed), mInpat = meterModel(p.util_inpatient);
  const status = !p.stable
    ? { txt: "Unstable", col: "var(--unstable)", dot: "var(--unstable)", cause: `${RES[p.saturated_resource || "unknown"] || ""}\nsaturated`, html: true }
    : p.congested
    ? { txt: "Congested", col: "var(--congested)", dot: "var(--congested)", cause: `pressure: ${RES[p.pressure_resource || "unknown"] || ""}`, html: false }
    : { txt: "Stable", col: "var(--stable)", dot: "var(--stable)", cause: "", html: false };
  const tourStep = TOUR[tour.step];

  return (
    <div className={`edtwin${tour.active ? " touring" : ""}`}>
      <style dangerouslySetInnerHTML={{ __html: ED_STYLES }} />
      <div className="wrap">
        <header>
          <div className="title-block">
            <div className="title">Emergency Department Digital Twin<b>.</b></div>
            <div className="thesis">A discrete event simulation calibrated on 424,725 real visits. The binding constraint is <em>inpatient capacity</em>, not doctors, not ED beds.</div>
          </div>
          <div className="header-right">
            <button className="tour-launch" onClick={startTour}>Guided tour</button>
            <div className="chips">
              <div className="chip"><span className="pulse" />Stochastic DES</div>
              <div className="chip"><b>MIMIC-IV-ED</b> v2.2</div>
              <div className="chip">6 wk horizon · 2 wk warmup</div>
              <div className="chip"><b>20</b> replications</div>
              <div className="chip">95% CI</div>
            </div>
          </div>
        </header>

        {/* guided tour overlay */}
        <div className="tour-scrim" onClick={endTour} />
        <div className="tour-panel" role="dialog" aria-label="Guided tour">
          <div className="tour-step">Step {tour.step + 1} of {TOUR.length}</div>
          <div className="tour-title">{tourStep.title}</div>
          <div className="tour-body" key={tour.step} style={{ animation: "fade .3s ease" }} dangerouslySetInnerHTML={{ __html: tourStep.html() }} />
          <div className="tour-foot">
            <div className="tour-dots">
              {TOUR.map((_, i) => <div key={i} className={`tour-dot${i === tour.step ? " on" : i < tour.step ? " done" : ""}`} />)}
            </div>
            <div className="tour-btns">
              <button className="tbtn" disabled={tour.step === 0} onClick={() => goStep(tour.step - 1)}>Back</button>
              <button className="tbtn primary" onClick={() => (tour.step < TOUR.length - 1 ? goStep(tour.step + 1) : endTour())}>{tour.step === TOUR.length - 1 ? "Finish" : "Next"}</button>
              <button className="tbtn ghost" onClick={endTour}>Exit</button>
            </div>
          </div>
        </div>

        <main>
          {/* LEFT */}
          <div className="col">
            <div className="levers">
              {LEVERS.map((L) => (
                <button key={L.key} className={`lever${L.key === leverKey ? " on" : ""}`} onClick={() => pickLever(L.key)}>{L.short}</button>
              ))}
            </div>
            <div className="card ctl">
              <div className="row"><span className="ctl-label">{lever.label}</span><span className="ctl-val">{value}{lever.key === "acuity_surge_pct" ? "%" : ""}</span></div>
              <input type="range" min={arr[0].value} max={arr[arr.length - 1].value} step={lever.step} value={value} onChange={onSlider} />
              <div className="ctl-foot"><span>{arr[0].value}</span><span>{arr[arr.length - 1].value}</span></div>
              <button className="reset-btn" disabled={value === resetTarget} onClick={onReset}>Reset to baseline</button>
            </div>
            <div className={`card flow${flow.focusing ? " focusing" : ""}`}>
              <div className="flow-title">Patient flow · live bottleneck</div>
              <div ref={stagesRef} className={`stages${flow.propagate ? " propagate" : ""}${flow.severe ? " severe" : ""}`}>
                {flow.stages.map((st) => (
                  <div key={st.name} className={st.cls} data-stage={st.name}>
                    <span className="node" />
                    <span className="lbl">{st.name}</span>
                    <span className={`qdots${st.dotsRed ? " red" : ""}`}>
                      {Array.from({ length: st.dots }).map((_, i) => <i key={i} style={{ animationDelay: `${(i * 0.11).toFixed(2)}s` }} />)}
                    </span>
                    <span className="q">{st.qtext}</span>
                  </div>
                ))}
                <div ref={spineRef} className="spine-pulse" />
              </div>
            </div>
          </div>

          {/* CENTER */}
          <div className="col">
            <div className="chart-card">
              <div className="chart-head">
                <div className="chart-titles">
                  <div className="chart-title">{METRICS[metric].label + " vs " + lever.label.toLowerCase()}</div>
                  <div className="chart-sub">{chartContext(leverKey)}</div>
                </div>
                <div className="head-right">
                  <span className="threshold-pill" style={{ color: th.c, background: th.bg, borderColor: th.bg === "transparent" ? "var(--line)" : th.c }}>{th.t}</span>
                  <div className="metric-toggle">
                    {(["los", "board", "doc"] as MetricKey[]).map((m) => (
                      <button key={m} className={`mbtn${m === metric ? " on" : ""}`} onClick={() => pickMetric(m)}>{METRICS[m].short}</button>
                    ))}
                  </div>
                </div>
              </div>
              <svg ref={chartRef} id="chart" viewBox={`0 0 ${geom.W} ${geom.H}`} preserveAspectRatio="none">
                <g ref={gstaticRef} />
                <g id="opgroup" transform={`translate(${xop.toFixed(1)},0)`}>
                  <line id="opline" x1={0} x2={0} y1={geom.T} y2={geom.T + geom.ih} stroke={op.col} strokeWidth={1.3} opacity={0.5} />
                  <g id="opvert" transform={`translate(0,${op.cy.toFixed(1)})`}>
                    <circle id="ophalo" r={13} fill="none" stroke={op.col} strokeWidth={1} opacity={0.4} />
                    <circle id="opdot" r={7} fill={op.col} />
                  </g>
                  <g id="opcallout">
                    <rect id="opbg" x={op.bgX.toFixed(1)} y={op.bgY.toFixed(1)} width={op.bgW.toFixed(1)} height={20} rx={5} ry={5} fill="#0C171A" stroke="#1C2F35" strokeWidth={1} />
                    <text id="opval" className="opval" x={0} y={op.ty} textAnchor="middle" fill={op.col}>{op.txt}</text>
                  </g>
                </g>
              </svg>
              <div className="explain"><span className="tag">Why this matters</span><span dangerouslySetInnerHTML={{ __html: explainText(p, leverKey, value) }} /></div>
            </div>
          </div>

          {/* RIGHT */}
          <div className="col">
            <div className="card" id="rightCard" style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
              <div className="status">
                <span className="dot" style={{ background: status.dot }} />
                <span className="status-txt" style={{ color: status.col }}>{status.txt}</span>
                <span className="cause">{status.html ? status.cause.split("\n").map((line, i) => <React.Fragment key={i}>{i > 0 && <br />}{line}</React.Fragment>) : status.cause}</span>
              </div>
              <div className="bignum">
                <span className="v" style={{ color: losNull ? "var(--unstable)" : "var(--ink)" }}>{losNull ? "n/a" : <CountUp value={p.los_median as number} />}</span>
                <span className="u">min</span>
                <span className="ci">{losNull ? "unbounded" : p.los_ci ? `± ${(p.los_ci as number).toFixed(1)}` : ""}</span>
              </div>
              <div className="bignum-label">Median length of stay</div>
              <div className="verdict" style={{ color: I.vcol }}>{I.verdict}</div>
              <div className="subs">
                <div className="sub"><div className="sv"><CountUp value={p.doc_median as number | null} /></div><div className="sl">Door to doc (min)</div></div>
                <div className="sub"><div className="sv"><CountUp value={p.board_median as number | null} /></div><div className="sl">Boarding (min)</div></div>
              </div>
              <div className="util-title">Resource utilization</div>
              <Meter name="Physicians" m={mPhys} />
              <Meter name="ED beds" m={mBed} />
              <Meter name="Inpatient ward" m={mInpat} />
              <div className="util-title" style={{ marginTop: 14 }}>Operational read</div>
              <div className="read" dangerouslySetInnerHTML={{ __html: I.read }} />
              <div className="cmp-title" style={{ marginTop: 13 }}>Baseline → this scenario</div>
              <div className="cmp">
                {rows.map((r) => (
                  <div className="cmp-row" key={r.name}>
                    <span className="cmp-name">{r.name}</span>
                    <span className="cmp-vals">
                      <span className="cmp-base">{r.base === null ? "n/a" : r.base.toFixed(r.d)}{r.unit}</span>
                      <span className="cmp-arrow">→</span>
                      <span className="cmp-cur" style={{ color: r.col }}>{r.cur === null ? "n/a" : r.cur.toFixed(r.d)}{r.unit}</span>
                    </span>
                  </div>
                ))}
              </div>
              <div className="sim-stat">
                <div className="ssv">{simPatients(p, leverKey)}</div>
                <div className="ssl">patient visits simulated<br />at this configuration</div>
              </div>
            </div>
          </div>
        </main>
        <footer className="appfoot">Calibrated on <b>MIMIC-IV-ED v2.2</b> · <b>424,725</b> encounters · <b>20</b> stochastic replications · Discrete event simulation</footer>
      </div>
    </div>
  );
}

function Meter({ name, m }: { name: string; m: { pct: number; col: string; valPct: number } }) {
  return (
    <div className="meter">
      <div className="mrow"><span className="mname">{name}</span><span className="mval">{m.valPct}%</span></div>
      <div className="track"><div className="fill" style={{ width: `${m.pct}%`, background: m.col }} /><div className="redline" style={{ left: `${(1 / 1.2) * 100}%` }} /></div>
    </div>
  );
}
