"""Ablation: measure the IoU contribution of each pipeline correction.

Runs a sequence of configs (baseline -> full) over a set of Sen1Floods11 test
chips and prints a mean-IoU table. This produces the numbers for the
Improvement Changelog. Slope masking (DEM fetch) is optional via --slope.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from tabulate import tabulate

from floodscope import data
from floodscope.pipeline import FloodConfig, map_flood
from floodscope.eval.iou import evaluate, mean_iou

CHIPS_CSV = Path(__file__).resolve().parent.parent / "floodscope" / "eval" / "chips.csv"


def load_chip_set() -> list[str]:
    with open(CHIPS_CSV) as f:
        return [row["chip"] for row in csv.DictReader(f)]


def variants(with_slope: bool) -> dict[str, FloodConfig]:
    v = {
        "baseline (global Otsu, VH)": FloodConfig.baseline(),
        "+ speckle filter": FloodConfig(speckle=True, threshold_method="otsu"),
        "+ bimodality-gated tile-Otsu": FloodConfig(speckle=True, threshold_method="tile"),
        "+ cleanup small blobs": FloodConfig(speckle=True, threshold_method="tile",
                                             cleanup_min_size=10),
    }
    if with_slope:
        v["+ slope mask (FULL benchmark)"] = FloodConfig.full_benchmark()
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slope", action="store_true", help="include DEM slope masking (slower)")
    args = ap.parse_args()

    chips = load_chip_set()
    print(f"Downloading/using {len(chips)} diverse chips...")
    for c in chips:
        data.download_chip(c)

    configs = variants(args.slope)
    per_chip_iou: dict[str, list[float]] = {name: [] for name in configs}

    for c in chips:
        vv, vh = data.read_s1(c)
        label = data.read_label(c)
        jrc = data.read_jrc_permanent(c)
        ref = data.chip_path(c, "S1Hand")
        bounds = data.chip_bounds(c)
        for name, cfg in configs.items():
            res = map_flood(vv, vh, cfg, jrc=jrc, ref_tif=ref, bounds=bounds)
            m = evaluate(res.water, label)
            per_chip_iou[name].append(m.iou)

    rows = []
    prev = None
    for name in configs:
        mi = mean_iou([type("M", (), {"iou": x})() for x in per_chip_iou[name]])
        delta = "" if prev is None else f"{mi - prev:+.3f}"
        rows.append([name, f"{mi:.3f}", delta])
        prev = mi
    print("\n" + tabulate(rows, headers=["Variant", "mean IoU", "Δ"], tablefmt="github"))
    print(f"\nChips: {', '.join(chips)}")


if __name__ == "__main__":
    main()
