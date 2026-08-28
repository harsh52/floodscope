"""Evaluation harness: baseline vs. agent pipeline on the Sen1Floods11 chips.

Produces the headline results table + a per-chip CSV tying every number to a
chip (evidence for the 'connect claims to evidence' rule). This measures the
deterministic *science* (the tools the LLM agent orchestrates); the LLM
baseline/agent wrappers reuse these same configs so numbers stay comparable.

Usage:
    python -m floodscope.eval.run_eval                # both, table + CSV
    python -m floodscope.eval.run_eval --mode baseline
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from tabulate import tabulate

from floodscope import data
from floodscope.config import REPORTS_DIR
from floodscope.pipeline import FloodConfig, map_flood
from floodscope.eval.iou import evaluate

CHIPS_CSV = Path(__file__).resolve().parent / "chips.csv"

MODES = {
    "baseline": FloodConfig.baseline,          # naive global Otsu on VH
    "agent": FloodConfig.full_benchmark,       # speckle + gated-Otsu + cleanup
}


def load_chips() -> list[tuple[str, str]]:
    with open(CHIPS_CSV) as f:
        return [(r["chip"], r.get("note", "")) for r in csv.DictReader(f)]


def run_mode(mode: str, chips: list[tuple[str, str]]) -> list[dict]:
    cfg = MODES[mode]()
    rows = []
    for chip, note in chips:
        data.download_chip(chip)
        vv, vh = data.read_s1(chip)
        label = data.read_label(chip)
        jrc = data.read_jrc_permanent(chip)
        res = map_flood(vv, vh, cfg, jrc=jrc,
                        ref_tif=data.chip_path(chip, "S1Hand"),
                        bounds=data.chip_bounds(chip))
        m = evaluate(res.water, label)
        rows.append({"chip": chip, "note": note, "mode": mode,
                     "iou": m.iou, "precision": m.precision, "recall": m.recall,
                     "pred_water_px": m.pred_water_px, "true_water_px": m.true_water_px,
                     "threshold_method": res.threshold_method})
    return rows


def summarize(rows: list[dict]) -> dict:
    iou = np.array([r["iou"] for r in rows], float)
    p = np.array([r["precision"] for r in rows], float)
    r_ = np.array([r["recall"] for r in rows], float)
    return {"mean_iou": np.nanmean(iou), "median_iou": np.nanmedian(iou),
            "min_iou": np.nanmin(iou), "catastrophic(<0.1)": int((iou < 0.1).sum()),
            "mean_precision": np.nanmean(p), "mean_recall": np.nanmean(r_)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "agent", "both"], default="both")
    args = ap.parse_args()
    chips = load_chips()
    modes = ["baseline", "agent"] if args.mode == "both" else [args.mode]

    all_rows, summaries = [], {}
    for mode in modes:
        rows = run_mode(mode, chips)
        all_rows += rows
        summaries[mode] = summarize(rows)

    # Per-chip table (agent vs baseline side by side when both)
    print("\n=== Per-chip IoU ===")
    if len(modes) == 2:
        by = {(r["chip"]): {} for r in all_rows}
        for r in all_rows:
            by[r["chip"]][r["mode"]] = r
        tbl = [[c, by[c]["baseline"]["note"],
                f"{by[c]['baseline']['iou']:.3f}", f"{by[c]['agent']['iou']:.3f}",
                f"{by[c]['agent']['iou'] - by[c]['baseline']['iou']:+.3f}"]
               for c in by]
        print(tabulate(tbl, headers=["chip", "note", "baseline IoU", "agent IoU", "Δ"], tablefmt="github"))
    else:
        tbl = [[r["chip"], f"{r['iou']:.3f}", f"{r['precision']:.3f}", f"{r['recall']:.3f}"] for r in all_rows]
        print(tabulate(tbl, headers=["chip", "IoU", "P", "R"], tablefmt="github"))

    # Summary table
    print("\n=== Summary ===")
    keys = list(next(iter(summaries.values())).keys())
    header = ["metric"] + modes + (["Δ"] if len(modes) == 2 else [])
    srows = []
    for k in keys:
        row = [k] + [(f"{summaries[m][k]:.3f}" if isinstance(summaries[m][k], float) else str(summaries[m][k])) for m in modes]
        if len(modes) == 2:
            a, b = summaries["agent"][k], summaries["baseline"][k]
            row.append(f"{a-b:+.3f}" if isinstance(a, float) else f"{a-b:+d}")
        srows.append(row)
    print(tabulate(srows, headers=header, tablefmt="github"))

    # Persist evidence CSV
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "eval_results.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader(); w.writerows(all_rows)
    print(f"\nPer-chip evidence written to {out}")


if __name__ == "__main__":
    main()
