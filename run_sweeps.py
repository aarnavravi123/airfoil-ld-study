"""
run_sweeps.py  -  AeroLab Research Initiative
Runs every XFOIL sweep in the methodology and builds the dataset.

Written by Claude (AI assistant) for Aarnav's airfoil research project.
Uses only Python's standard library (works on Python 3.9+).

What it does:
  1. For each airfoil and Reynolds number, sends commands to XFOIL.
  2. Sweeps alpha 0 -> 15 deg, then resets and sweeps 0 -> -5 deg
     (split sweep = fewer convergence failures).
  3. Reads each polar file, removes duplicate rows, sorts by alpha,
     and reports any angles that failed to converge.
  4. Writes:
       data/raw/NACAxxxx_Re<re>.txt   raw XFOIL polar files
       data/all_polars.csv            every point, with L/D added
       data/summary.csv               max L/D and its alpha per run
       data/run_log.txt               settings + missing points
"""

import csv
import os
import subprocess
import sys
from datetime import datetime

# ---------------- Settings (controlled variables) ----------------
AIRFOILS = ["0012", "2412", "4412", "0015", "0018"]
REYNOLDS = [100_000, 200_000, 500_000, 1_000_000]
VALIDATION = [("2412", 3_100_000)]   # compare to NACA Report 824, p. 136

ALPHA_START, ALPHA_MAX, ALPHA_MIN, ALPHA_STEP = 0.0, 15.0, -5.0, 0.5
MACH = 0.0
NCRIT = 9
PANELS = 160
ITER = 100
VALIDATION_ALPHA_MAX = 20.0   # NACA 2412 stalls near 16 deg
TIMEOUT_S = 180   # stop XFOIL if one run hangs longer than this

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "data", "raw")
DATA_DIR = os.path.join(HERE, "data")


def expected_alphas(alpha_max=ALPHA_MAX):
    """All angles the sweep should produce (41 for -5..15 by 0.5)."""
    n = int(round((alpha_max - ALPHA_MIN) / ALPHA_STEP)) + 1
    return [round(ALPHA_MIN + i * ALPHA_STEP, 2) for i in range(n)]


def xfoil_commands(naca, re, polar_file, alpha_max=ALPHA_MAX):
    """The exact keystrokes we would type into XFOIL, one per line."""
    lines = [
        "PLOP", "G", "",                 # graphics off, back to main menu
        f"NACA {naca}",
        "PPAR", f"N {PANELS}", "", "",   # set panel count, exit PPAR
        "OPER",
        f"VISC {re}",
        f"MACH {MACH}",
        "VPAR", f"N {NCRIT}", "",        # set Ncrit, exit VPAR
        f"ITER {ITER}",
        "PACC", polar_file, "",          # save polar, no dump file
        f"ASEQ {ALPHA_START} {alpha_max} {ALPHA_STEP}",   # 0 -> 15 (or 20)
        "INIT",                          # reset boundary layer
        f"ASEQ {ALPHA_START} {ALPHA_MIN} {-ALPHA_STEP}",  # 0 -> -5
        "PACC",                          # stop saving
        "", "QUIT",
    ]
    return "\n".join(lines) + "\n"


def run_xfoil(naca, re, alpha_max=ALPHA_MAX):
    name = f"NACA{naca}_Re{re}.txt"
    path = os.path.join(RAW_DIR, name)
    # XFOIL APPENDS to an existing polar file -> delete old one first
    # (this is what caused the duplicate rows in sweep1.txt)
    if os.path.exists(path):
        os.remove(path)
    try:
        subprocess.run(
            ["xfoil"],
            input=xfoil_commands(naca, re, name, alpha_max),
            text=True,
            capture_output=True,
            cwd=RAW_DIR,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(f"  !! XFOIL timed out on NACA {naca}, Re {re}")
    return path


def read_polar(path):
    """Return {alpha: row_dict}. Duplicate alphas are removed."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        lines = f.read().splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("------"):
            start = i + 1
            break
    if start is None:
        return rows
    keys = ["alpha", "CL", "CD", "CDp", "CM", "Top_Xtr", "Bot_Xtr"]
    for line in lines[start:]:
        parts = line.split()
        if len(parts) < 7:
            continue
        try:
            vals = [float(p) for p in parts[:7]]
        except ValueError:
            continue
        row = dict(zip(keys, vals))
        rows[round(row["alpha"], 2)] = row
    return rows


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    # "python3 run_sweeps.py --validation-only" skips the 20 main runs
    if "--validation-only" in sys.argv:
        runs = []
    else:
        runs = [(a, r, False) for a in AIRFOILS for r in REYNOLDS]
    runs += [(a, r, True) for a, r in VALIDATION]

    all_rows, summary, log = [], [], []
    log.append(f"Run started {datetime.now():%Y-%m-%d %H:%M}")
    log.append(f"Settings: Mach={MACH}, Ncrit={NCRIT}, panels={PANELS}, "
               f"iter={ITER}, alpha {ALPHA_MIN}..{ALPHA_MAX} step {ALPHA_STEP}")
    log.append("")

    for i, (naca, re, is_val) in enumerate(runs, 1):
        label = f"NACA {naca}, Re = {re:,}" + ("  [validation]" if is_val else "")
        print(f"[{i}/{len(runs)}] {label} ...", flush=True)
        amax = VALIDATION_ALPHA_MAX if is_val else ALPHA_MAX
        want = expected_alphas(amax)
        polar = read_polar(run_xfoil(naca, re, amax))

        missing = [a for a in want if a not in polar]
        print(f"     {len(polar)}/{len(want)} points converged"
              + (f"; missing: {missing}" if missing else ""))
        log.append(f"{label}: {len(polar)}/{len(want)} converged"
                   + (f"; missing alphas {missing}" if missing else ""))

        best = None
        for alpha in sorted(polar):
            p = polar[alpha]
            ld = p["CL"] / p["CD"] if p["CD"] > 0 else None
            all_rows.append({"airfoil": f"NACA {naca}", "Re": re,
                             "validation": is_val, **p,
                             "L_D": round(ld, 3) if ld is not None else ""})
            if ld is not None and (best is None or ld > best[1]):
                best = (alpha, ld, p["CL"], p["CD"])

        if best:
            summary.append({"airfoil": f"NACA {naca}", "Re": re,
                            "validation": is_val,
                            "max_L_D": round(best[1], 2),
                            "alpha_at_max_L_D": best[0],
                            "CL_at_max": best[2], "CD_at_max": best[3],
                            "CL_max_in_sweep": max(p["CL"] for p in polar.values()),
                            "points_converged": len(polar),
                            "points_missing": len(missing)})

    prefix = "validation_" if "--validation-only" in sys.argv else ""
    with open(os.path.join(DATA_DIR, prefix + "all_polars.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    with open(os.path.join(DATA_DIR, prefix + "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    with open(os.path.join(DATA_DIR, prefix + "run_log.txt"), "w") as f:
        f.write("\n".join(log) + "\n")

    print("\nDone. Files written to the 'data' folder:")
    print(f"  {prefix}all_polars.csv, {prefix}summary.csv, {prefix}run_log.txt, raw/")


if __name__ == "__main__":
    main()
