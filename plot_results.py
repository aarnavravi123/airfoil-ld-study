"""
plot_results.py  -  AeroLab Research Initiative
Makes the four figures from data/all_polars.csv and data/summary.csv.

Written by Claude (AI assistant) for Aarnav's airfoil research project.
Needs matplotlib:  python3 -m pip install --user matplotlib

Figures (saved to figures/ as 300-dpi PNGs):
  fig1_cl_vs_alpha.png    lift curve, one panel per Reynolds number
  fig2_drag_polar.png     CD vs CL, one panel per Reynolds number
  fig3_ld_vs_alpha.png    L/D vs alpha, one panel per Reynolds number
  fig4_max_ld_vs_re.png   max L/D vs Re, one line per airfoil
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")            # draw to files, no window needed
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FIGS = os.path.join(HERE, "figures")

# Fixed color per airfoil (same in every figure).
# Line style is a second cue: solid = camber series, dashed = thickness series.
STYLE = {
    "NACA 0012": dict(color="#2a78d6", ls="-",  marker="o"),
    "NACA 2412": dict(color="#eb6834", ls="-",  marker="s"),
    "NACA 4412": dict(color="#1baf7a", ls="-",  marker="^"),
    "NACA 0015": dict(color="#c98500", ls="--", marker="D"),
    "NACA 0018": dict(color="#d55181", ls="--", marker="v"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 2, "lines.markersize": 4,
    "legend.frameon": False, "savefig.dpi": 300, "savefig.bbox": "tight",
})


def load_polars():
    """{(airfoil, Re): [rows sorted by alpha]} - main runs only."""
    runs = {}
    with open(os.path.join(DATA, "all_polars.csv")) as f:
        for r in csv.DictReader(f):
            if r["validation"] == "True":
                continue
            row = {k: float(r[k]) for k in ("alpha", "CL", "CD")}
            row["LD"] = float(r["L_D"]) if r["L_D"] else None
            runs.setdefault((r["airfoil"], int(r["Re"])), []).append(row)
    for rows in runs.values():
        rows.sort(key=lambda x: x["alpha"])
    return runs


def re_label(re):
    return f"Re = {re // 1000:,}k" if re < 1_000_000 else f"Re = {re / 1e6:g}M"


def panel_figure(runs, xkey, ykey, xlabel, ylabel, title, fname, xlim=None):
    res = sorted({re for _, re in runs})
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5), sharex=True, sharey=True)
    for ax, re in zip(axes.flat, res):
        for name, st in STYLE.items():
            rows = [r for r in runs.get((name, re), []) if r[ykey] is not None]
            if rows:
                ax.plot([r[xkey] for r in rows], [r[ykey] for r in rows],
                        label=name, markevery=4, **st)
        ax.set_title(re_label(re), color=INK, fontsize=10, loc="left")
        if xlim:
            ax.set_xlim(*xlim)
    for ax in axes[1]:
        ax.set_xlabel(xlabel)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5,
               bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(title, y=1.04, color=INK, fontsize=12)
    fig.savefig(os.path.join(FIGS, fname))
    plt.close(fig)
    print("  saved", fname)


def max_ld_figure():
    pts = {}
    with open(os.path.join(DATA, "summary.csv")) as f:
        for r in csv.DictReader(f):
            if r["validation"] == "True":
                continue
            pts.setdefault(r["airfoil"], []).append(
                (int(r["Re"]), float(r["max_L_D"])))
    fig, ax = plt.subplots(figsize=(7, 5))
    for name, st in STYLE.items():
        p = sorted(pts.get(name, []))
        if not p:
            continue
        ax.plot([x for x, _ in p], [y for _, y in p], label=name,
                markersize=6, **st)
    ax.set_xscale("log")
    ticks = sorted({x for v in pts.values() for x, _ in v})
    ax.set_xticks(ticks)
    ax.set_xticklabels([re_label(t).replace("Re = ", "") for t in ticks])
    ax.minorticks_off()
    ax.set_xlabel("Reynolds number (log scale)")
    ax.set_ylabel("Maximum lift-to-drag ratio, (L/D)max")
    ax.set_title("Maximum L/D vs Reynolds number (XFOIL, Ncrit = 9)",
                 color=INK, fontsize=12, loc="left")
    ax.legend(loc="upper left")
    fig.savefig(os.path.join(FIGS, "fig4_max_ld_vs_re.png"))
    plt.close(fig)
    print("  saved fig4_max_ld_vs_re.png")


def main():
    os.makedirs(FIGS, exist_ok=True)
    runs = load_polars()
    panel_figure(runs, "alpha", "CL", "Angle of attack, α (deg)",
                 "Lift coefficient, $C_l$",
                 "Lift curves (XFOIL, Ncrit = 9)", "fig1_cl_vs_alpha.png")
    panel_figure(runs, "CD", "CL", "Drag coefficient, $C_d$",
                 "Lift coefficient, $C_l$",
                 "Drag polars (XFOIL, Ncrit = 9; post-stall points beyond Cd = 0.05 not shown)",
                 "fig2_drag_polar.png", xlim=(0, 0.05))
    panel_figure(runs, "alpha", "LD", "Angle of attack, α (deg)",
                 "Lift-to-drag ratio, L/D",
                 "L/D vs angle of attack (XFOIL, Ncrit = 9)",
                 "fig3_ld_vs_alpha.png")
    max_ld_figure()
    print("Done. Figures are in the 'figures' folder.")


if __name__ == "__main__":
    main()
