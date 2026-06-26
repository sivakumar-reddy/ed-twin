// ed-twin model: all simulation-derived presentation logic, ported verbatim from the
// validated standalone explorer and typed. Pure and DOM-free so it can be unit/parity tested.
import rawData from "../data/ed_sweeps.json";

export type SweepPoint = {
  value: number;
  stable: boolean;
  congested?: boolean;
  los_median?: number | null;
  los_ci?: number | null;
  board_median?: number | null;
  doc_median?: number | null;
  util_phys?: number | null;
  util_bed?: number | null;
  util_inpatient?: number | null;
  saturated_resource?: string;
  pressure_resource?: string;
  [k: string]: number | boolean | string | null | undefined;
};

export type Meta = {
  baseline: Record<string, number>;
  reps: number;
  measured_weeks: number;
  warmup_weeks: number;
  [k: string]: unknown;
};

type Raw = { sweeps: Record<string, SweepPoint[]>; meta: Meta };

export const RAW = rawData as unknown as Raw;
export const SW = RAW.sweeps;
export const BASE = RAW.meta.baseline;
export const META = RAW.meta;
export const TOTAL_WEEKS = META.measured_weeks + META.warmup_weeks;
export const REPS = META.reps;

// global baseline reference point (the calibrated operating point, same across levers)
export const BREF = SW.n_inpatient_beds.find((p) => p.value === BASE.n_inpatient_beds)!;

export type LeverKey =
  | "n_inpatient_beds"
  | "n_physicians"
  | "mean_interarrival_minutes"
  | "n_ed_beds"
  | "n_triage_nurses"
  | "acuity_surge_pct";
export type MetricKey = "los" | "board" | "doc";

export type Lever = {
  key: LeverKey;
  label: string;
  short: string;
  step: number;
  defMetric: MetricKey;
  invert?: boolean;
};

export const LEVERS: Lever[] = [
  { key: "n_inpatient_beds", label: "Inpatient beds", short: "Inpatient beds", step: 1, defMetric: "board" },
  { key: "n_physicians", label: "Physicians", short: "Physicians", step: 1, defMetric: "doc" },
  { key: "mean_interarrival_minutes", label: "Patient load", short: "Patient load", step: 1, defMetric: "los", invert: true },
  { key: "n_ed_beds", label: "ED beds", short: "ED beds", step: 1, defMetric: "los" },
  { key: "n_triage_nurses", label: "Triage nurses", short: "Triage", step: 1, defMetric: "los" },
  { key: "acuity_surge_pct", label: "Acuity surge", short: "Acuity surge", step: 5, defMetric: "los" },
];

export const METRICS: Record<MetricKey, { label: string; field: string; unit: string; short: string; ci: string | null }> = {
  los: { label: "Length of stay", field: "los_median", unit: "min", short: "LOS", ci: "los_ci" },
  board: { label: "Boarding", field: "board_median", unit: "min", short: "Boarding", ci: null },
  doc: { label: "Door to doctor", field: "doc_median", unit: "min", short: "Door to doc", ci: null },
};

export const RES: Record<string, string> = {
  physicians: "physicians",
  ed_beds: "ED beds",
  inpatient_beds: "inpatient ward",
  unknown: "system",
};
export const STAGES = ["Arrival", "Triage", "ED bed", "Physician", "Diagnostics", "Disposition", "Boarding", "Inpatient"];

export const leverByKey = (k: LeverKey): Lever => LEVERS.find((l) => l.key === k)!;
export const pts = (k: LeverKey): SweepPoint[] => SW[k];
export const pointAt = (k: LeverKey, v: number): SweepPoint | undefined => pts(k).find((p) => p.value === v);
export const num = (x: number | boolean | string | null | undefined): number | null =>
  x === null || x === undefined || typeof x !== "number" ? null : x;

export function interarrivalFor(k: LeverKey, p: SweepPoint): number {
  return k === "mean_interarrival_minutes" ? p.value : BASE.mean_interarrival_minutes;
}
export function fmt(x: number | null | undefined, d = 0): string {
  return x === null || x === undefined ? "n/a" : Number(x).toFixed(d);
}
export function snapVal(k: LeverKey, raw: number): number {
  const vals = SW[k].map((p) => p.value);
  let b = vals[0];
  for (const v of vals) if (Math.abs(v - raw) < Math.abs(b - raw)) b = v;
  return b;
}
export function nearestValue(k: LeverKey, v: number): number {
  if (pointAt(k, v)) return v;
  let best = pts(k)[0];
  for (const p of pts(k)) if (Math.abs(p.value - v) < Math.abs(best.value - v)) best = p;
  return best.value;
}
export function baselineValue(k: LeverKey): number {
  const base = BASE[k];
  return base !== undefined && pointAt(k, base) ? base : pts(k)[Math.floor(pts(k).length / 2)].value;
}

// ---------- geometry ----------
export type Geom = {
  W: number; H: number; L: number; R: number; T: number; B: number; iw: number; ih: number;
  field: string; ymax: number; boundaries: number[];
  X: (v: number) => number; Y: (v: number) => number;
};

const estW = (t: string, sz: number) => t.length * sz * 0.6;
const regimeOf = (p: SweepPoint) => {
  if (!p.stable) return "unstable";
  const ui = (num(p.util_inpatient) || 0);
  return ui >= 0.95 && ui < 1.0 ? "approaching" : "stable";
};
function makePlacer() {
  const boxes: { x0: number; x1: number; y0: number; y1: number }[] = [];
  return {
    fits(x0: number, x1: number, y0: number, y1: number) {
      for (const b of boxes) if (x0 < b.x1 + 6 && x1 > b.x0 - 6 && y0 < b.y1 + 4 && y1 > b.y0 - 4) return false;
      return true;
    },
    add(x0: number, x1: number, y0: number, y1: number) {
      boxes.push({ x0, x1, y0, y1 });
    },
  };
}

export function geometry(leverKey: LeverKey, metric: MetricKey, Wraw: number, Hraw: number): Geom {
  const W = Math.max(360, Math.round(Wraw || 880)), H = Math.max(260, Math.round(Hraw || 560));
  const L = 74, R = 36, T = 58, B = 58, iw = W - L - R, ih = H - T - B;
  const arr = pts(leverKey), field = METRICS[metric].field;
  const xs = arr.map((p) => p.value), xmin = Math.min(...xs), xmax = Math.max(...xs);
  const X = (v: number) => L + (xmax === xmin ? 0.5 : (v - xmin) / (xmax - xmin)) * iw;
  const vals = arr.filter((p) => p.stable && p[field] != null).map((p) => p[field] as number);
  const ymax = Math.max(1, ...vals) * 1.26;
  const Y = (v: number) => T + ih - v / ymax * ih;
  const runX0 = (i: number) => X(arr[i].value) - (i > 0 ? (X(arr[i].value) - X(arr[i - 1].value)) / 2 : 8);
  const runX1 = (j: number) => X(arr[j].value) + (j < arr.length - 1 ? (X(arr[j + 1].value) - X(arr[j].value)) / 2 : 8);
  const bnds: number[] = [];
  for (let i = 0; i < arr.length; ) {
    if (!arr[i].stable) { let j = i; while (j + 1 < arr.length && !arr[j + 1].stable) j++; bnds.push(i > 0 ? runX0(i) : runX1(j)); i = j + 1; }
    else i++;
  }
  return { W, H, L, R, T, B, iw, ih, field, ymax, boundaries: bnds, X, Y };
}

// ---------- static chart layer (string injected once per lever/metric/size) ----------
export function buildStaticSvg(g: Geom, leverKey: LeverKey, metric: MetricKey, animateDraw: boolean): string {
  const { L, T, iw, ih, ymax, X, Y, field } = g;
  const arr = pts(leverKey), cif = METRICS[metric].ci, lever = leverByKey(leverKey);
  const runX0 = (i: number) => X(arr[i].value) - (i > 0 ? (X(arr[i].value) - X(arr[i - 1].value)) / 2 : 8);
  const runX1 = (j: number) => X(arr[j].value) + (j < arr.length - 1 ? (X(arr[j + 1].value) - X(arr[j].value)) / 2 : 8);
  const bnds = g.boundaries;
  let s = "";

  // shaded regions
  for (let i = 0; i < arr.length; ) {
    if (regimeOf(arr[i]) === "approaching") { let j = i; while (j + 1 < arr.length && regimeOf(arr[j + 1]) === "approaching") j++;
      s += `<rect x="${runX0(i).toFixed(1)}" y="${T}" width="${(runX1(j) - runX0(i)).toFixed(1)}" height="${ih}" fill="#F5B945" opacity="0.06"/>`; i = j + 1; }
    else i++;
  }
  for (let i = 0; i < arr.length; ) {
    if (!arr[i].stable) { let j = i; while (j + 1 < arr.length && !arr[j + 1].stable) j++;
      const x0 = runX0(i), x1 = runX1(j), bx = i > 0 ? x0 : x1;
      s += `<rect x="${x0.toFixed(1)}" y="${T}" width="${(x1 - x0).toFixed(1)}" height="${ih}" fill="#F26D6D" opacity="0.07"/>`;
      s += `<line x1="${bx.toFixed(1)}" y1="${T}" x2="${bx.toFixed(1)}" y2="${T + ih}" stroke="#F26D6D" stroke-width="1.2" stroke-dasharray="4 4" opacity="0.5"/>`;
      i = j + 1; }
    else i++;
  }

  // grid + ticks
  for (let k = 0; k <= 4; k++) { const yv = ymax * k / 4, yy = Y(yv);
    s += `<line x1="${L}" y1="${yy.toFixed(1)}" x2="${L + iw}" y2="${yy.toFixed(1)}" stroke="#15252A" stroke-width="1" opacity="0.4"/>`;
    s += `<text class="ax" x="${L - 10}" y="${(yy + 3.5).toFixed(1)}" text-anchor="end">${yv.toFixed(0)}</text>`; }
  const nx = Math.min(8, arr.length);
  for (let k = 0; k < nx; k++) { const idx = Math.round(k / (nx - 1) * (arr.length - 1)), v = arr[idx].value;
    s += `<text class="ax" x="${X(v).toFixed(1)}" y="${T + ih + 18}" text-anchor="middle">${v}</text>`; }

  // segments, CI band, area, line, dots
  const segs: SweepPoint[][] = []; let seg: SweepPoint[] = [];
  for (const p of arr) { if (p.stable && p[field] != null) seg.push(p); else { if (seg.length) { segs.push(seg); seg = []; } } }
  if (seg.length) segs.push(seg);
  const stressed = arr.some((p) => !p.stable || (num(p.util_inpatient) || 0) >= 0.95);
  if (stressed && segs.length) { let lg = segs[0]; for (const sg of segs) if (sg.length > lg.length) lg = sg;
    if (lg.length >= 4) { const wx = X(lg[Math.floor(lg.length / 2)].value);
      s += `<g class="anno" data-kind="stable"><text x="${wx.toFixed(1)}" y="${(T + ih * 0.5).toFixed(1)}" text-anchor="middle" fill="#34D399" style="font-size:12.5px;letter-spacing:.24em;font-weight:400">STABLE REGION</text></g>`; } }
  if (cif) { for (const sg of segs) {
    const upArr = sg.map((p) => `${X(p.value).toFixed(1)},${Y((p[field] as number) + ((p[cif] as number) || 0)).toFixed(1)}`);
    const dn = sg.slice().reverse().map((p) => `${X(p.value).toFixed(1)},${Y((p[field] as number) - ((p[cif] as number) || 0)).toFixed(1)}`);
    s += `<polygon points="${upArr.concat(dn).join(" ")}" fill="#34D399" opacity="0.11"/>`; } }
  for (const sg of segs) {
    const dpath = sg.map((p, idx) => `${idx ? "L" : "M"}${X(p.value).toFixed(1)},${Y(p[field] as number).toFixed(1)}`).join(" ");
    const area = `M${X(sg[0].value).toFixed(1)},${(T + ih).toFixed(1)} ` + sg.map((p) => `L${X(p.value).toFixed(1)},${Y(p[field] as number).toFixed(1)}`).join(" ") + ` L${X(sg[sg.length - 1].value).toFixed(1)},${(T + ih).toFixed(1)} Z`;
    s += `<path d="${area}" fill="#34D399" opacity="0.05"/>`;
    s += `<path class="${animateDraw ? "draw" : ""}" pathLength="1" d="${dpath}" fill="none" stroke="#34D399" stroke-width="2.6"/>`;
  }
  for (const p of arr) if (p.stable && p[field] != null) s += `<circle cx="${X(p.value).toFixed(1)}" cy="${Y(p[field] as number).toFixed(1)}" r="2.6" fill="${p.congested ? "#F5B945" : "#34D399"}"/>`;

  // collision-aware, context-tagged annotations (revealed one at a time)
  const placer = makePlacer();
  const opLane = T - 16;
  placer.add(L - 30, L + iw + 30, opLane - 13, opLane + 9);
  const anno: string[] = [];
  function label(x: number, text: string, sub: string | null, sz: number, color: string, weight: number, kind: string, anchorY: number | null) {
    const w = Math.max(estW(text, sz), sub ? estW(sub, 9) : 0) + 10;
    const cx = Math.max(L + w / 2 + 4, Math.min(L + iw - w / 2 - 4, x));
    const lanes = [T + ih - 26, T + ih - 58];
    for (const y of lanes) {
      const x0 = cx - w / 2 - 6, x1 = cx + w / 2 + 6, y0 = y - sz - 4, y1 = y + (sub ? 17 : 6);
      if (placer.fits(x0, x1, y0, y1)) {
        placer.add(x0, x1, y0, y1);
        let ldr = "";
        if (anchorY != null || Math.abs(cx - x) > 18) { const ay = anchorY != null ? anchorY : T + ih;
          ldr = `<line x1="${cx.toFixed(1)}" y1="${(y - sz - 2).toFixed(1)}" x2="${x.toFixed(1)}" y2="${ay.toFixed(1)}" stroke="${color}" stroke-width="1" opacity="0.4"/>`; }
        const subSvg = sub ? `<text x="${cx.toFixed(1)}" y="${(y + 12).toFixed(1)}" text-anchor="middle" fill="${color}" opacity="0.62" style="font-size:9px;font-weight:400;letter-spacing:.01em">${sub}</text>` : "";
        anno.push(`<g class="anno" data-kind="${kind}">${ldr}<text class="zonelabel" x="${cx.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle" fill="${color}" font-weight="${weight}" style="font-size:${sz}px">${text}</text>${subSvg}</g>`);
        return true;
      }
    }
    return false;
  }
  for (const bx of bnds) label(bx, "Critical threshold", "ward cannot clear admissions", 13, "#F26D6D", 600, "critical", null);
  let bb: SweepPoint | null = null;
  for (const p of arr) { if (p.stable && p.board_median != null && p.board_median >= 1) { bb = p; break; } }
  if (bb) { const bx = X(bb.value), by = field === "board_median" ? Y(bb.board_median as number) : T + ih * 0.55;
    anno.push(`<g class="anno" data-kind="boarding"><circle cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="3.4" fill="none" stroke="#F5B945" stroke-width="1.4"/></g>`);
    label(bx, "Boarding begins", "length of stay starts to climb", 12.5, "#F5B945", 600, "boarding", by); }
  s += anno.join("");

  // axis labels
  const xlab = lever.label + (lever.invert ? "  (lower = busier)" : "") + (lever.key === "acuity_surge_pct" ? "  (%)" : "");
  s += `<text class="axlabel" x="${(L + iw / 2).toFixed(1)}" y="${g.H - 6}" text-anchor="middle">${xlab}</text>`;
  s += `<text class="axlabel" x="${(-(T + ih / 2)).toFixed(1)}" y="16" text-anchor="middle" transform="rotate(-90)">${METRICS[metric].label} (${METRICS[metric].unit})</text>`;
  return s;
}

// operating-point marker state
export function opState(g: Geom, p: SweepPoint | undefined, metric: MetricKey) {
  const collapse = !(p && p.stable && p[g.field] != null);
  const cy = collapse ? g.T + g.ih / 2 : g.Y(p![g.field] as number);
  const col = collapse ? "#F26D6D" : "#5EEAD4";
  const txt = collapse ? "collapse" : `${(p![g.field] as number).toFixed(0)} ${METRICS[metric].unit}`;
  const ty = g.T - 10;
  const w = estW(txt, 12) + 18;
  return { collapse, cy, col, txt, ty, bgX: -w / 2, bgW: w, bgY: ty - 14 };
}

// annotation opacity/transform handoff, applied imperatively per operating point
export function annoHandoff(g: Geom, p: SweepPoint | undefined, xop: number): Record<string, { opacity: number; ty: number }> {
  let dist = 1;
  (g.boundaries || []).forEach((bx) => { dist = Math.min(dist, Math.abs(xop - bx) / g.iw); });
  const stable = !!(p && p.stable);
  const prox = !stable ? 1 : Math.max(0, 1 - dist / 0.3);
  const bump = (x: number, lo: number, hi: number) => { const t = (x - lo) / (hi - lo); return t <= 0 || t >= 1 ? 0 : Math.sin(Math.PI * t); };
  const oStable = stable ? Math.max(0, 1 - prox / 0.55) * 0.2 : 0;
  const oBoard = stable ? bump(prox, 0.4, 0.9) * 0.92 : 0;
  const oCrit = !stable ? 1 : Math.max(0, (prox - 0.88) / 0.12);
  const tyOf = (o: number) => 5 * (1 - Math.min(1, o * 1.5));
  return {
    stable: { opacity: oStable, ty: 0 },
    boarding: { opacity: oBoard, ty: tyOf(oBoard) },
    critical: { opacity: oCrit, ty: tyOf(oCrit) },
  };
}

// ---------- interpretation ----------
export function interpret(p: SweepPoint): { verdict: string; vcol: string; read: string } {
  const ui = num(p.util_inpatient), up = num(p.util_phys), board = (num(p.board_median) || 0);
  const uiP = ui == null ? null : Math.round(ui * 100), upP = up == null ? null : Math.round(up * 100);
  const losBase = BREF.los_median as number;
  let verdict = "", vcol = "", read = "";
  if (!p.stable) {
    verdict = "No steady state: the queue grows without bound"; vcol = "var(--unstable)";
    if (p.saturated_resource === "physicians")
      read = `Demand for physicians exceeds supply at this load. The front end is saturated, so the decision here is staffing or smoothing arrivals, not beds.`;
    else
      read = `The inpatient ward cannot clear admissions as fast as they arrive${uiP != null ? ` (<b>${uiP}%</b> utilization)` : ""}, so admitted patients board in the ED and block it for everyone. Adding ED staff or ED beds cannot fix this. The decision is <b>inpatient capacity or faster discharge</b>.`;
  } else if (board >= 20 || (ui != null && ui >= 0.985)) {
    verdict = "Elevated, driven by downstream boarding"; vcol = "var(--congested)";
    read = `Inpatient capacity is nearly exhausted (<b>${uiP}%</b>) while physicians sit at ${upP}%. Boarding has begun and accelerates sharply from here. The lever that matters is <b>ward capacity or discharge throughput</b>, not more clinicians.`;
  } else if (up != null && up >= 0.82) {
    const hot = (p.los_median as number) > losBase * 1.04;
    verdict = hot ? "Elevated by limited physician staffing" : "Sensitive to physician staffing"; vcol = hot ? "var(--congested)" : "var(--ink2)";
    read = `Physicians are running hot at <b>${upP}%</b>. In this range staffing <b>is</b> the binding resource: adding physicians shortens door to doctor and trims length of stay, and cutting further would degrade access to a provider.`;
  } else if (ui != null && ui >= 0.93) {
    verdict = "Rising as inpatient headroom thins"; vcol = "var(--congested)";
    read = `The inpatient ward (<b>${uiP}%</b>) is the resource with the least headroom; physicians (${upP}%) and ED beds have slack. Protect inpatient capacity first: it is what keeps this department stable.`;
  } else {
    verdict = "Within the expected operating range"; vcol = "var(--stable)";
    read = `No single resource is constraining flow: physicians run at ${upP}% and the ward at <b>${uiP}%</b>, both with headroom. Note where the slack sits: <b>adding physicians would change little</b>, because they are not the bottleneck.`;
  }
  return { verdict, vcol, read };
}

export function explainText(p: SweepPoint, leverKey: LeverKey, v: number): string {
  const ui = Math.round((num(p.util_inpatient) || 0) * 100), up = Math.round((num(p.util_phys) || 0) * 100), ub = Math.round((num(p.util_bed) || 0) * 100);
  if (!p.stable) {
    if (p.saturated_resource === "physicians") return `<b>Unstable.</b> Physician utilization reaches ${up}%, above sustainable capacity. Patients arrive faster than they can be seen, so the waiting queue grows without bound. This is not a steady state, so length of stay has no finite value.`;
    return `<b>Unstable.</b> Inpatient utilization is ${ui}%. The ward cannot clear admissions as fast as they arrive, so admitted patients board in the ED indefinitely, blocking beds for everyone, and the department collapses. Doctors still sit at ${up}% utilization. The failure is entirely upstream.`;
  }
  switch (leverKey) {
    case "n_inpatient_beds":
      if (ui >= 96) return `<b>${v} inpatient beds.</b> Ward utilization is ${ui}%, at the edge. Boarding has begun (${(p.board_median as number).toFixed(0)} min) and is climbing steeply. A few beds fewer and the system tips into unbounded boarding. This is the critical threshold.`;
      if (ui >= 88) return `<b>${v} inpatient beds.</b> Ward utilization is ${ui}%, with thinning headroom. Boarding is still near zero, but the curve to the left shows how fast it accelerates as beds are removed.`;
      return `<b>${v} inpatient beds.</b> Ward utilization is ${ui}%, comfortable headroom. Boarding is negligible and length of stay holds at ${(p.los_median as number).toFixed(0)} min. Removing the downstream bottleneck is what keeps the ED stable.`;
    case "n_physicians":
      if (up >= 85) return `<b>${v} physicians.</b> Utilization is ${up}%, near the staffing floor. Door to doctor is sensitive here (${(p.doc_median as number).toFixed(1)} min), and cutting further would destabilize access to a provider.`;
      return `<b>${v} physicians.</b> Utilization is only ${up}%, well below saturation. Adding physicians trims door to doctor marginally (${(p.doc_median as number).toFixed(1)} min) but cannot move total length of stay. The constraint lives downstream, in inpatient capacity.`;
    case "n_ed_beds":
      return `<b>${v} ED beds.</b> Bed utilization is ${ub}%. ED beds are not the constraint. Length of stay holds near ${(p.los_median as number).toFixed(0)} min across the entire range. Admitted patients cannot leave the ED until an inpatient bed opens, so adding treatment space cannot resolve congestion.`;
    case "n_triage_nurses":
      return `<b>${v} triage nurse${v > 1 ? "s" : ""}.</b> Triage is never the bottleneck. Length of stay is ${(p.los_median as number).toFixed(0)} min whether one nurse works the front door or ten. Time is lost downstream, not at intake.`;
    case "mean_interarrival_minutes":
      if (ui >= 95) return `<b>${v} min between arrivals.</b> At this volume, inpatient utilization is ${ui}%. The ward is near saturation. Push arrivals any higher and the system fails, while physicians remain at ${up}%.`;
      return `<b>${v} min between arrivals.</b> Inpatient utilization is ${ui}%, with headroom. The department is stable at this load. The first resource to saturate as volume rises is always the inpatient ward.`;
    case "acuity_surge_pct":
      return `<b>plus ${v}% high acuity surge.</b> Even with a sicker mix, inpatient utilization is ${ui}% and length of stay drifts only to ${(p.los_median as number).toFixed(0)} min. The department is resilient to acuity, but fragile to bed supply.`;
  }
  return "";
}

export function thresholdState(p: SweepPoint): { t: string; c: string; bg: string } {
  if (!p.stable) return { t: "Critical threshold exceeded", c: "var(--unstable)", bg: "rgba(242,109,109,.12)" };
  const ui = num(p.util_inpatient) || 0;
  if (ui >= 0.96) return { t: "Approaching critical threshold", c: "var(--congested)", bg: "rgba(245,185,69,.12)" };
  if (ui >= 0.88) return { t: "Limited headroom", c: "var(--ink2)", bg: "transparent" };
  return { t: "Stable operating region", c: "var(--stable)", bg: "rgba(52,211,153,.10)" };
}

export function chartContext(leverKey: LeverKey): string {
  switch (leverKey) {
    case "n_inpatient_beds": return "Exploring the binding constraint: inpatient capacity";
    case "n_physicians": return "Testing whether adding physicians shortens the stay";
    case "n_ed_beds": return "Testing whether more ED treatment space shortens the stay";
    case "n_triage_nurses": return "Testing whether the front door is ever the bottleneck";
    case "mean_interarrival_minutes": return "Which resource saturates first as patient volume rises";
    case "acuity_surge_pct": return "How a sicker patient mix shifts the system";
  }
  return "Interactive parameter sweep";
}

export type CmpRow = { name: string; base: number | null; cur: number | null; unit: string; d: number; col: string };
function cmpRow(name: string, base: number | null, cur: number | null | undefined, unit: string, d = 0, inverse = false): CmpRow {
  const cvNull = cur === null || cur === undefined;
  let col = "var(--ink2)";
  if (!cvNull && base !== null) { const better = inverse ? (cur as number) > base : (cur as number) < base; const same = Math.abs((cur as number) - base) < (d ? 0.05 : 0.5); col = same ? "var(--ink2)" : better ? "var(--stable)" : "var(--unstable)"; }
  if (cvNull) col = "var(--unstable)";
  return { name, base, cur: cvNull ? null : (cur as number), unit, d, col };
}
export function cmpRows(p: SweepPoint): CmpRow[] {
  return [
    cmpRow("Length of stay", BREF.los_median as number, num(p.los_median), "", 0),
    cmpRow("Boarding", BREF.board_median as number, num(p.board_median), "", 0),
    cmpRow("Inpatient util", (BREF.util_inpatient as number) * 100, num(p.util_inpatient) != null ? (num(p.util_inpatient) as number) * 100 : null, "%", 0, false),
    cmpRow("Physician util", (BREF.util_phys as number) * 100, num(p.util_phys) != null ? (num(p.util_phys) as number) * 100 : null, "%", 0, false),
  ];
}

export function meterModel(val: number | null | undefined): { pct: number; col: string; valPct: number } {
  const v = val === null || val === undefined ? 0 : val;
  const pct = Math.min(v, 1.2) / 1.2 * 100;
  const col = v >= 1.0 ? "var(--unstable)" : v >= 0.9 ? "var(--congested)" : v >= 0.7 ? "var(--stable)" : "var(--faint)";
  return { pct, col, valPct: Math.round(v * 100) };
}

export function simPatients(p: SweepPoint, leverKey: LeverKey): string {
  const ia = interarrivalFor(leverKey, p);
  const patients = Math.round((TOTAL_WEEKS * 10080) / ia) * REPS;
  return patients.toLocaleString("en-US");
}

// ---------- patient-flow model ----------
export type FlowStage = { name: string; cls: string; dots: number; dotsRed: boolean; qtext: string };
export type FlowModel = { stages: FlowStage[]; propagate: boolean; severe: boolean; focusing: boolean };
export function flowModel(p: SweepPoint): FlowModel {
  const ui = num(p.util_inpatient) || 0, ub = num(p.util_bed) || 0, up = num(p.util_phys) || 0;
  const map: Record<string, string> = {
    "ED bed": ub >= 0.95 ? "hot" : ub >= 0.8 ? "warm" : "",
    Physician: up >= 0.95 ? "hot" : up >= 0.85 ? "warm" : "",
    Boarding: !p.stable ? "hot" : (p.board_median as number) > 30 ? "hot" : (p.board_median as number) > 2 ? "warm" : "",
    Inpatient: !p.stable ? "hot" : ui >= 0.95 ? "warm" : ui >= 1.0 ? "hot" : "",
  };
  const bottleneck =
    ui >= 0.9 || (!p.stable && p.saturated_resource === "inpatient_beds") ? "Inpatient" :
    !p.stable && p.saturated_resource === "physicians" ? "Physician" :
    !p.stable && p.saturated_resource === "ed_beds" ? "ED bed" : null;
  const boardMin = p.stable ? (num(p.board_median) || 0) : Infinity;
  const boardingActive = !p.stable || boardMin > 2;
  const propagating = !p.stable || boardMin > 10;
  const severe = !p.stable || boardMin > 30;
  const bDots = !boardingActive ? 0 : !p.stable ? 6 : Math.max(1, Math.min(6, Math.round(boardMin / 12)));
  const eDots = propagating ? (severe ? 4 : 2) : ub >= 0.85 ? 2 : 0;
  const stages: FlowStage[] = STAGES.map((s) => {
    let cls = "stage";
    if (map[s] === "hot") cls += " hot"; else if (map[s] === "warm") cls += " warm";
    let dots = 0, qtext = "";
    if (s === "Boarding") {
      if (boardingActive) { cls += " focal show-q"; qtext = p.stable ? `${(p.board_median as number).toFixed(0)}m wait` : "∞"; }
      if (bDots) dots = bDots;
    } else if (s === "ED bed") {
      if (propagating) cls += " backedup";
      if (eDots) dots = eDots;
    }
    if (s === bottleneck) cls += " bottleneck";
    return { name: s, cls, dots, dotsRed: severe, qtext };
  });
  return { stages, propagate: propagating, severe, focusing: propagating };
}

// ---------- guided tour ----------
const rnd = (x: number | null | undefined) => (x == null ? "n/a" : Math.round(x));
const pc = (u: number | null | undefined) => (u == null ? "n/a" : Math.round(u * 100) + "%");
function atVal(key: LeverKey, v: number, field: string): number | null {
  const a = SW[key]; if (!a) return null;
  let p = a.find((x) => x.value === v);
  if (!p) p = a.reduce((b, c) => (Math.abs(c.value - v) < Math.abs(b.value - v) ? c : b));
  return p ? (num(p[field])) : null;
}
export const PHYS_MAX = Math.max(...SW.n_physicians.map((p) => p.value));
export const ED_MAX = Math.max(...SW.n_ed_beds.map((p) => p.value));
export const INPAT_UNSTABLE = (() => {
  const desc = SW.n_inpatient_beds.slice().sort((a, b) => b.value - a.value);
  for (const p of desc) if (!p.stable) return p.value;
  return Math.min(...SW.n_inpatient_beds.map((p) => p.value));
})();

export type TourStep = { lever: LeverKey; from: number; to: number; metric: MetricKey; title: string; html: () => string };
export const TOUR: TourStep[] = [
  { lever: "n_inpatient_beds", from: BASE.n_inpatient_beds, to: BASE.n_inpatient_beds, metric: "board",
    title: "The baseline department",
    html: () => `This is the current configuration: <b>${BASE.n_physicians} physicians</b>, <b>${BASE.n_ed_beds} ED beds</b>, <b>${BASE.n_inpatient_beds} inpatient beds</b>, one arrival every <b>${BASE.mean_interarrival_minutes} min</b>. The department is <span class="pos">stable</span>. Median length of stay is <b>${rnd(BREF.los_median as number)} min</b> and no admitted patient is waiting for a ward bed (boarding <span class="pos">${rnd(BREF.board_median as number)} min</span>). Every resource has headroom: physicians ${pc(BREF.util_phys as number)}, ED beds ${pc(BREF.util_bed as number)}, inpatient ward ${pc(BREF.util_inpatient as number)}. The question this tool answers: which resource actually limits performance?` },
  { lever: "n_physicians", from: BASE.n_physicians, to: PHYS_MAX, metric: "los",
    title: "More physicians barely move the needle",
    html: () => `Hold everything else fixed and raise staffing from <b>${BASE.n_physicians}</b> to <b>${PHYS_MAX} physicians</b>. Length of stay stays essentially flat at about <b>${rnd(atVal("n_physicians", BASE.n_physicians, "los_median"))} min</b>, moving by under a minute across the entire staffing range. <b>Why:</b> at baseline physicians already run at only <span class="warn">${pc(atVal("n_physicians", BASE.n_physicians, "util_phys"))}</span> utilization, far below saturation. They were never the bottleneck, so adding more cannot shorten a stay whose time is spent in diagnostic workup and waiting for an inpatient bed.` },
  { lever: "n_ed_beds", from: BASE.n_ed_beds, to: ED_MAX, metric: "los",
    title: "More ED beds do not help either",
    html: () => `Now widen the ED itself, <b>${BASE.n_ed_beds} to ${ED_MAX} beds</b>. Length of stay holds near <b>${rnd(atVal("n_ed_beds", ED_MAX, "los_median"))} min</b> across the whole range. ED bed occupancy is only <span class="warn">${pc(atVal("n_ed_beds", BASE.n_ed_beds, "util_bed"))}</span>: the beds are not full. Admitted patients keep occupying ED beds while they wait for a ward bed, so adding ED space adds waiting room, not throughput.` },
  { lever: "n_inpatient_beds", from: BASE.n_inpatient_beds, to: INPAT_UNSTABLE, metric: "board",
    title: "Inpatient capacity is the real constraint",
    html: () => `Hold staffing and ED beds fixed, and remove the one resource the others could not substitute for. As the ward shrinks <b>${BASE.n_inpatient_beds} to 100 to 99 beds</b>, boarding climbs <span class="pos">${rnd(atVal("n_inpatient_beds", 110, "board_median"))}</span> to <span class="warn">${rnd(atVal("n_inpatient_beds", 100, "board_median"))}</span> to <span class="neg">${rnd(atVal("n_inpatient_beds", 99, "board_median"))} min</span>. Around <b>${INPAT_UNSTABLE} beds</b> the admission queue grows without bound and the department goes <span class="neg">unstable</span>. This single lever moves boarding, length of stay, and stability together.` },
  { lever: "n_inpatient_beds", from: INPAT_UNSTABLE, to: BASE.n_inpatient_beds, metric: "board",
    title: "The operational takeaway",
    html: () => `<b>The binding constraint is downstream inpatient capacity, not physicians and not ED beds.</b> Across the realistic range, adding physicians or ED beds left length of stay essentially unchanged, while inpatient capacity alone decided whether the department stayed stable or collapsed. The highest leverage interventions are the ones that protect or expand effective ward capacity: inpatient beds, plus the discharge and placement processes that free those beds sooner.` },
];
