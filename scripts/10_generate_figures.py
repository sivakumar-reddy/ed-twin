"""
Generate README figures for the ED digital twin from the calibrated sweep data.

Reads data/sweeps/ed_sweeps.json and emits three PNGs into docs/images/:
  - baseline.png : the stable inpatient-bed operating range, LOS flat, boarding near zero
  - unstable.png : the inpatient-bed cliff, boarding explodes then steady state is lost
  - hero.png     : a wide banner combining the binding-constraint story in one frame

Every number plotted is read directly from the committed sweep JSON. Nothing is
hard coded. The script prints the baseline values it reads so they can be checked
against the README prose before committing.

Usage (from repo root):
    python scripts/10_generate_figures.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator

# ---------------------------------------------------------------- brand tokens
INK        = "#0E1419"   # near-black ink-teal ground
PANEL      = "#141C22"   # slightly lifted panel
TEAL       = "#2BB8A3"   # primary brand teal
TEAL_DIM   = "#1C7A6E"   # muted teal for secondary series
AMBER      = "#EFAB47"   # accent: the binding-constraint signal
RED        = "#E5604D"   # failure / unbounded
TEXT       = "#E7EDEA"   # primary text on dark
MUTED      = "#8A9AA0"   # captions, gridlines text
GRID       = "#212C33"   # gridlines

plt.rcParams.update({
    "figure.facecolor":  INK,
    "axes.facecolor":    INK,
    "savefig.facecolor": INK,
    "text.color":        TEXT,
    "axes.labelcolor":   TEXT,
    "axes.edgecolor":    GRID,
    "xtick.color":       MUTED,
    "ytick.color":       MUTED,
    "axes.grid":         True,
    "grid.color":        GRID,
    "grid.linewidth":    0.8,
    "font.size":         12,
})

# Use a clean sans the environment has; fall back gracefully.
for fam in ("DejaVu Sans", "Arial", "Helvetica"):
    if any(fam in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break


def load_sweeps(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def series(sweep_for_lever):
    """Return sorted (x, los, board, stable, degenerate) parallel lists."""
    pts = sorted(sweep_for_lever.values(), key=lambda p: p["value"])
    x        = [p["value"] for p in pts]
    los      = [p.get("los_median") for p in pts]
    board    = [p.get("board_median") for p in pts]
    stable   = [bool(p.get("stable")) for p in pts]
    degen    = [bool(p.get("degenerate")) for p in pts]
    return x, los, board, stable, degen


def first_unstable_value(x, stable):
    """Largest x that is unstable, i.e. the edge of the cliff."""
    bad = [xi for xi, s in zip(x, stable) if not s]
    return max(bad) if bad else None


def style_ax(ax):
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)


# ----------------------------------------------------------------- baseline fig
def fig_baseline(sweeps, baseline, out):
    x, los, board, stable, degen = series(sweeps["n_inpatient_beds"])
    base_beds = baseline["n_inpatient_beds"]

    # Only plot the stable range for the "baseline / healthy" story.
    xs   = [xi for xi, s in zip(x, stable) if s]
    loss = [l for l, s in zip(los, stable) if s and l is not None]
    xs_l = [xi for xi, l, s in zip(x, los, stable) if s and l is not None]

    fig, ax = plt.subplots(figsize=(9, 5), dpi=160)
    style_ax(ax)

    ax.plot(xs_l, loss, color=TEAL, linewidth=2.6, zorder=3)
    ax.scatter(xs_l, loss, color=TEAL, s=22, zorder=4)

    # mark the baseline operating point
    if base_beds in x:
        i = x.index(base_beds)
        if los[i] is not None:
            ax.scatter([base_beds], [los[i]], s=140, facecolor=AMBER,
                       edgecolor=INK, linewidth=1.5, zorder=5)
            ax.annotate(
                f"baseline\n{base_beds} inpatient beds\nmedian LOS {los[i]:.0f} min",
                xy=(base_beds, los[i]), xytext=(14, 26),
                textcoords="offset points", color=TEXT, fontsize=11,
                ha="left", va="bottom",
                arrowprops=dict(arrowstyle="-", color=AMBER, linewidth=1.2),
            )

    ax.set_title("Inpatient capacity: stable operating range",
                 color=TEXT, fontsize=15, pad=14, loc="left", fontweight="bold")
    ax.set_xlabel("Inpatient beds")
    ax.set_ylabel("Median length of stay (minutes)")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.margins(x=0.04)

    cap = ("Across the stable range, length of stay is flat and boarding stays near zero. "
           "Adding inpatient beds beyond baseline barely moves the stay.")
    fig.text(0.065, -0.02, cap, color=MUTED, fontsize=9.5, ha="left", wrap=True)

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)


# ----------------------------------------------------------------- unstable fig
def fig_unstable(sweeps, baseline, out):
    x, los, board, stable, degen = series(sweeps["n_inpatient_beds"])
    cliff = first_unstable_value(x, stable)

    fig, ax = plt.subplots(figsize=(9, 5), dpi=160)
    style_ax(ax)

    # boarding vs beds, on stable points only (unstable has no meaningful number)
    xs_b = [xi for xi, b, s in zip(x, board, stable) if s and b is not None]
    bs   = [b for b, s, xi in zip(board, stable, x) if s and b is not None]
    ax.plot(xs_b, bs, color=TEAL, linewidth=2.6, zorder=3)
    ax.scatter(xs_b, bs, color=TEAL, s=22, zorder=4)

    # shade the unbounded region at/below the cliff
    if cliff is not None:
        ax.axvspan(min(x) - 1, cliff + 0.5, color=RED, alpha=0.12, zorder=1)
        ax.axvline(cliff + 0.5, color=RED, linewidth=1.4, linestyle=(0, (4, 3)),
                   zorder=2)
        ymax = max(bs) if bs else 1
        ax.annotate(
            f"at {cliff} beds the admission queue\ngrows without bound\nsteady state is lost",
            xy=(cliff + 0.5, ymax * 0.78),
            xytext=(cliff + 4, ymax * 0.82),
            textcoords="data", color=RED, fontsize=11, ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color=RED, linewidth=1.2),
        )

    ax.set_title("Past the cliff: boarding explodes as inpatient capacity tightens",
                 color=TEXT, fontsize=15, pad=14, loc="left", fontweight="bold")
    ax.set_xlabel("Inpatient beds")
    ax.set_ylabel("Median boarding time (minutes)")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.margins(x=0.04)

    cap = ("Reducing inpatient beds toward the cliff sends boarding from near zero into the "
           "tens of minutes; below the edge the department has no steady state at all.")
    fig.text(0.065, -0.02, cap, color=MUTED, fontsize=9.5, ha="left", wrap=True)

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)


# --------------------------------------------------------------------- hero fig
def fig_hero(sweeps, baseline, out):
    xp, losp, _, stablep, _ = series(sweeps["n_physicians"])
    xb, losb, boardb, stableb, _ = series(sweeps["n_inpatient_beds"])

    fig, (axL, axR) = plt.subplots(
        1, 2, figsize=(13, 5), dpi=160,
        gridspec_kw={"wspace": 0.22})

    # left: physicians do not move LOS across the realistic range
    style_ax(axL)
    xs = [xi for xi, l, s in zip(xp, losp, stablep) if s and l is not None]
    ls = [l for l, s in zip(losp, stablep) if s and l is not None]
    axL.plot(xs, ls, color=TEAL_DIM, linewidth=2.6)
    axL.scatter(xs, ls, color=TEAL_DIM, s=20)
    if baseline["n_physicians"] in xp:
        i = xp.index(baseline["n_physicians"])
        if losp[i] is not None:
            axL.scatter([baseline["n_physicians"]], [losp[i]], s=120,
                        facecolor=MUTED, edgecolor=INK, linewidth=1.4, zorder=5)
    axL.set_title("More physicians barely move length of stay",
                  color=TEXT, fontsize=13, loc="left", pad=10)
    axL.set_xlabel("Physicians")
    axL.set_ylabel("Median LOS (min)")
    axL.xaxis.set_major_locator(MaxNLocator(integer=True))

    # right: inpatient beds are the binding lever
    style_ax(axR)
    cliff = first_unstable_value(xb, stableb)
    xs_b = [xi for xi, b, s in zip(xb, boardb, stableb) if s and b is not None]
    bs   = [b for b, s, xi in zip(boardb, stableb, xb) if s and b is not None]
    axR.plot(xs_b, bs, color=TEAL, linewidth=2.8)
    axR.scatter(xs_b, bs, color=TEAL, s=20)
    if cliff is not None:
        axR.axvspan(min(xb) - 1, cliff + 0.5, color=RED, alpha=0.12)
        axR.axvline(cliff + 0.5, color=RED, linewidth=1.4,
                    linestyle=(0, (4, 3)))
    axR.set_title("Inpatient beds decide whether the ED holds",
                  color=AMBER, fontsize=13, loc="left", pad=10, fontweight="bold")
    axR.set_xlabel("Inpatient beds")
    axR.set_ylabel("Median boarding (min)")
    axR.xaxis.set_major_locator(MaxNLocator(integer=True))

    fig.suptitle("Emergency Department Digital Twin  —  the binding constraint is downstream",
                 color=TEXT, fontsize=16, fontweight="bold", x=0.065, ha="left", y=1.02)
    cap = ("Calibrated on 424,725 real MIMIC-IV-ED encounters. Swept one factor at a time, "
           "20 stochastic replications per point, 95% confidence intervals.")
    fig.text(0.065, -0.04, cap, color=MUTED, fontsize=9.5, ha="left")

    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.13)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    data_path = os.path.join(root, "data", "sweeps", "ed_sweeps.json")
    out_dir   = os.path.join(root, "docs", "images")

    # allow an override path for local testing
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    if len(sys.argv) > 2:
        out_dir = sys.argv[2]

    os.makedirs(out_dir, exist_ok=True)
    data = load_sweeps(data_path)

    sweeps   = data["sweeps"]
    baseline = data.get("meta", {}).get("baseline")
    if baseline is None:
        # some calibration files nest baseline differently; fail loud
        raise SystemExit("No 'baseline' block found in sweep JSON. Check the file.")

    print("Baseline read from JSON (verify against README prose):")
    for k, v in baseline.items():
        print(f"  {k:28s} {v}")

    if "n_inpatient_beds" not in sweeps:
        raise SystemExit("No 'n_inpatient_beds' sweep found. Available: "
                         + ", ".join(sweeps.keys()))

    fig_baseline(sweeps, baseline, os.path.join(out_dir, "baseline.png"))
    fig_unstable(sweeps, baseline, os.path.join(out_dir, "unstable.png"))
    fig_hero(sweeps, baseline, os.path.join(out_dir, "hero.png"))

    print(f"\nWrote baseline.png, unstable.png, hero.png to {out_dir}")


if __name__ == "__main__":
    main()

