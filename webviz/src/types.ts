export interface Metrics {
  iou?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  pred_water_px?: number;
  true_water_px?: number;
  threshold_method: string;
  threshold_db?: number;
  area_km2?: number | null;
  area_pct?: number | null;
  surface_water_km2?: number;
  new_inundation_km2?: number;
}

export interface LegendItem {
  color: string;
  label: string;
}

export interface Present {
  before: string;
  before_mask?: string;
  after: string;
  mask: string;
  mask2?: string;
  before_label: string;
  after_label: string;
  mask_label: string;
  mask2_label?: string;
  legend?: LegendItem[];
}

export interface ChipEntry {
  chip: string;
  note: string;
  live?: boolean;
  acquired?: { pre: string; post: string } | string;
  pixel_m?: number;
  bounds: [[number, number], [number, number]]; // [[S,W],[N,E]]
  view?: [[number, number], [number, number]]; // optional focused fit region
  center: [number, number];
  size: [number, number];
  tiles: { sar: string; optical?: string; baseline: string; agent: string; truth?: string; permanent?: string };
  present?: Present;
  trajectory: string;
  metrics: { baseline: Metrics; agent: Metrics };
  delta_iou: number | null;
}

export interface TrajEvent {
  seq: number;
  ts: number;
  iso: string;
  workflow_id: string;
  agent: string;
  case: string;
  phase: string | null;
  event_type: string;
  [k: string]: unknown;
}

// before↔after (imagery vs prediction) | baseline↔agent | agent↔ground-truth
export type Mode = "present" | "ba" | "gt";
