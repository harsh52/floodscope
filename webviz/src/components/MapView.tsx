import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, ImageOverlay } from "react-leaflet";
import type { Map as LMap, LatLngBoundsExpression } from "leaflet";
import type { ChipEntry, Mode } from "../types";
import { asset } from "../asset";

const OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

interface Layer {
  base: string; // imagery url
  mask?: string; // overlay mask url
  mask2?: string; // secondary overlay (e.g. new-inundation highlight)
}

/** Resolve the two panes' imagery + overlays for the current mode. */
function layersFor(chip: ChipEntry, mode: Mode): { left: Layer; right: Layer } {
  const t = chip.tiles;
  const imagery = t.optical ?? t.sar;
  if (mode === "present" && chip.present) {
    const p = chip.present;
    return {
      left: { base: p.before, mask: p.before_mask },
      right: { base: p.after, mask: p.mask, mask2: p.mask2 },
    };
  }
  if (mode === "gt") {
    return { left: { base: imagery, mask: t.agent }, right: { base: imagery, mask: t.truth } };
  }
  // ba
  return { left: { base: imagery, mask: t.baseline }, right: { base: imagery, mask: t.agent } };
}

function SidePane({
  bounds,
  layer,
  onMap,
  zoomControl,
}: {
  bounds: LatLngBoundsExpression;
  layer: Layer;
  onMap: (m: LMap | null) => void;
  zoomControl: boolean;
}) {
  return (
    <MapContainer
      ref={onMap}
      bounds={bounds}
      className="map"
      scrollWheelZoom
      zoomControl={zoomControl}
      attributionControl={zoomControl}
    >
      <TileLayer attribution={OSM_ATTR} url={OSM_URL} />
      <ImageOverlay url={asset(layer.base)} bounds={bounds} opacity={1} zIndex={350} />
      {layer.mask && <ImageOverlay url={asset(layer.mask)} bounds={bounds} opacity={0.9} zIndex={400} />}
      {layer.mask2 && <ImageOverlay url={asset(layer.mask2)} bounds={bounds} opacity={0.95} zIndex={410} />}
    </MapContainer>
  );
}

export default function MapView({ chip, mode }: { chip: ChipEntry; mode: Mode }) {
  const bounds = chip.bounds as LatLngBoundsExpression;
  const { left, right } = layersFor(chip, mode);

  const [leftMap, setLeftMap] = useState<LMap | null>(null);
  const [rightMap, setRightMap] = useState<LMap | null>(null);
  const [split, setSplit] = useState(50);
  const wrapRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  useEffect(() => {
    if (!leftMap || !rightMap) return;
    const mirror = (src: LMap, dst: LMap) => () => {
      if (syncing.current) return;
      syncing.current = true;
      dst.setView(src.getCenter(), src.getZoom(), { animate: false });
      syncing.current = false;
    };
    const l2r = mirror(leftMap, rightMap);
    const r2l = mirror(rightMap, leftMap);
    leftMap.on("move zoom", l2r);
    rightMap.on("move zoom", r2l);
    return () => {
      leftMap.off("move zoom", l2r);
      rightMap.off("move zoom", r2l);
    };
  }, [leftMap, rightMap]);

  useEffect(() => {
    const fitTo = (chip.view ?? chip.bounds) as LatLngBoundsExpression;
    for (const m of [leftMap, rightMap]) {
      if (!m) continue;
      m.invalidateSize();
      m.fitBounds(fitTo, { padding: [10, 10], maxZoom: 16, animate: false });
    }
  }, [leftMap, rightMap, chip.chip, chip.view, chip.bounds]);

  useEffect(() => {
    const id = setTimeout(() => {
      leftMap?.invalidateSize();
      rightMap?.invalidateSize();
    }, 0);
    return () => clearTimeout(id);
  }, [split, leftMap, rightMap]);

  const startDrag = (e: React.MouseEvent) => {
    e.preventDefault();
    const onMove = (ev: MouseEvent) => {
      const r = wrapRef.current?.getBoundingClientRect();
      if (!r) return;
      setSplit(Math.min(85, Math.max(15, ((ev.clientX - r.left) / r.width) * 100)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div className="sbs" ref={wrapRef}>
      <div className="sbs-pane" style={{ width: `${split}%` }}>
        <SidePane bounds={bounds} layer={left} onMap={setLeftMap} zoomControl />
      </div>
      <div className="sbs-pane" style={{ width: `${100 - split}%` }}>
        <SidePane bounds={bounds} layer={right} onMap={setRightMap} zoomControl={false} />
      </div>
      <div className="divider" style={{ left: `${split}%` }} onMouseDown={startDrag}>
        <span className="divider-grip">⇔</span>
      </div>
    </div>
  );
}
