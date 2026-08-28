"""Evaluation metrics for flood water segmentation.

Primary metric = IoU on the water class, ignoring no-data (-1) pixels — the
convention used by the Sen1Floods11 benchmark.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from floodscope.config import LABEL_NODATA, LABEL_WATER


@dataclass
class SegMetrics:
    iou: float          # intersection-over-union on water class
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    tn: int
    pred_water_px: int
    true_water_px: int

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate(pred_water: np.ndarray, label: np.ndarray) -> SegMetrics:
    """Compare a boolean predicted-water mask against a Sen1Floods11 label array.

    pred_water : bool array (True = predicted water)
    label      : int array with values in {-1 nodata, 0 land, 1 water}
    """
    pred = np.asarray(pred_water, dtype=bool)
    valid = label != LABEL_NODATA
    gt = (label == LABEL_WATER) & valid
    pr = pred & valid

    tp = int(np.count_nonzero(pr & gt))
    fp = int(np.count_nonzero(pr & ~gt))
    fn = int(np.count_nonzero(~pr & gt))
    tn = int(np.count_nonzero(~pr & ~gt & valid))

    union = tp + fp + fn
    iou = tp / union if union else float("nan")
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall and not np.isnan(precision) and not np.isnan(recall)
          else float("nan"))

    return SegMetrics(
        iou=iou, precision=precision, recall=recall, f1=f1,
        tp=tp, fp=fp, fn=fn, tn=tn,
        pred_water_px=int(np.count_nonzero(pr)),
        true_water_px=int(np.count_nonzero(gt)),
    )


def mean_iou(metrics_list: list[SegMetrics]) -> float:
    vals = [m.iou for m in metrics_list if not np.isnan(m.iou)]
    return float(np.mean(vals)) if vals else float("nan")
