import { useCallback, useEffect, useMemo, useState } from "react";
import { CesiumGlobe, type GridIndex, type GridPoint } from "../components/explorer/CesiumGlobe";
import { CubeInspector, type CubeLevelData } from "../components/explorer/CubeInspector";
import { api, ApiError } from "../lib/api";
import { API_BASE_URL, REGION_BBOX, REGION_CENTER, REGION_LABEL } from "../lib/config";
import { sstToColor } from "../lib/oceanColor";
import type { NowcastInfo, VolumetricCellSeries, VolumetricMeta, VolumetricSnapshot } from "../lib/types";

function nearestIndex(values: number[], target: number): number {
  let best = 0;
  let bestDist = Infinity;
  for (let i = 0; i < values.length; i++) {
    const d = Math.abs(values[i] - target);
    if (d < bestDist) {
      bestDist = d;
      best = i;
    }
  }
  return best;
}

export function Explorer() {
  const [meta, setMeta] = useState<VolumetricMeta | null>(null);
  const [snapshot, setSnapshot] = useState<VolumetricSnapshot | null>(null);
  const [nowcastInfo, setNowcastInfo] = useState<NowcastInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<GridIndex | null>(null);
  const [depthIdx, setDepthIdx] = useState(0);
  const [cubeOpen, setCubeOpen] = useState(false);
  const [cellSeries, setCellSeries] = useState<VolumetricCellSeries | null>(null);
  const [selectedDayIndex, setSelectedDayIndex] = useState(-1);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [m, s] = await Promise.all([api.volumetricMeta(), api.volumetricSnapshot()]);
        if (cancelled) return;
        setMeta(m);
        setSnapshot(s);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unexpected error reaching the backend.");
      }
      try {
        const info = await api.nowcastInfo();
        if (!cancelled) setNowcastInfo(info);
      } catch {
        // Nowcast badge is supplementary -- the explorer itself still works without it.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Start centered on the real grid cell nearest the region's midpoint.
  useEffect(() => {
    if (!meta || selected) return;
    setSelected({
      latIdx: nearestIndex(meta.lat, REGION_CENTER.lat),
      lonIdx: nearestIndex(meta.lon, REGION_CENTER.lon),
    });
  }, [meta, selected]);

  // Fetch the real full time series for whichever cell is open, so the
  // cube can be scrubbed through real days, not just the latest snapshot.
  useEffect(() => {
    if (!cubeOpen || !selected || !meta) return;
    let cancelled = false;
    setCellSeries(null);
    setSelectedDayIndex(-1);
    api
      .volumetricCell(meta.lat[selected.latIdx], meta.lon[selected.lonIdx])
      .then((series) => {
        if (cancelled) return;
        setCellSeries(series);
        setSelectedDayIndex(series.time.length - 1);
      })
      .catch(() => {
        // Falls back to the snapshot's single real day below -- still real
        // data, just without the time-scrub.
      });
    return () => {
      cancelled = true;
    };
  }, [cubeOpen, selected, meta]);

  // Global navigation: arrow keys pan the grid (Google-Maps-style, works
  // whether or not a cube is open), Page Up/Down step through real depth
  // levels (recoloring the whole-region view), Enter opens the currently
  // selected cell's cube.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!meta) return;
      if (e.key === "Enter" && selected) {
        setCubeOpen(true);
        return;
      }
      if (e.key === "PageUp") {
        e.preventDefault();
        setDepthIdx((d) => Math.max(d - 1, 0));
        return;
      }
      if (e.key === "PageDown") {
        e.preventDefault();
        setDepthIdx((d) => Math.min(d + 1, meta.depth_m.length - 1));
        return;
      }
      const isArrow = e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight";
      if (!isArrow) return;
      e.preventDefault();
      setSelected((prev) => {
        if (!prev) return prev;
        let { latIdx, lonIdx } = prev;
        if (e.key === "ArrowUp") latIdx = Math.min(latIdx + 1, meta.lat.length - 1);
        else if (e.key === "ArrowDown") latIdx = Math.max(latIdx - 1, 0);
        else if (e.key === "ArrowRight") lonIdx = Math.min(lonIdx + 1, meta.lon.length - 1);
        else if (e.key === "ArrowLeft") lonIdx = Math.max(lonIdx - 1, 0);
        return { latIdx, lonIdx };
      });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [meta, selected]);

  const points: GridPoint[] = useMemo(() => {
    if (!meta || !snapshot) return [];
    const out: GridPoint[] = [];
    for (let latIdx = 0; latIdx < meta.lat.length; latIdx++) {
      const row = snapshot.sst_c[depthIdx]?.[latIdx];
      if (!row) continue;
      for (let lonIdx = 0; lonIdx < meta.lon.length; lonIdx++) {
        // Real land-masked cells (~27% of this grid, per Person 3's README)
        // come back as null -- skip them rather than color them, so land
        // shows through as the real basemap instead of implying there's
        // ocean data where there isn't any.
        const sst = row[lonIdx];
        if (sst === null) continue;
        out.push({ latIdx, lonIdx, lat: meta.lat[latIdx], lon: meta.lon[lonIdx], color: sstToColor(sst) });
      }
    }
    return out;
  }, [meta, snapshot, depthIdx]);

  // Real land-masked cells carry null for every variable at every depth
  // (see the `points` filter above) -- there's no real ocean data to show
  // for those, so this deliberately returns [] rather than passing nulls
  // into components typed to expect real numbers. The empty-array check
  // below (`levels.length > 0`) then keeps the cube from opening at all
  // for a land cell.
  function isCompleteLevel(level: {
    sst_c: number | null;
    salinity_psu: number | null;
    current_u_ms: number | null;
    current_v_ms: number | null;
    wave_height_m: number | null;
    chlorophyll_mg_m3: number | null;
  }): level is CubeLevelData {
    return (
      level.sst_c !== null &&
      level.salinity_psu !== null &&
      level.current_u_ms !== null &&
      level.current_v_ms !== null &&
      level.wave_height_m !== null &&
      level.chlorophyll_mg_m3 !== null
    );
  }

  const levels: CubeLevelData[] = useMemo(() => {
    if (!meta || !snapshot || !selected) return [];
    const { latIdx, lonIdx } = selected;
    const raw =
      cellSeries && selectedDayIndex >= 0
        ? meta.depth_m.map((depth_m, d) => ({
            depth_m,
            sst_c: cellSeries.sst_c[selectedDayIndex][d],
            salinity_psu: cellSeries.salinity_psu[selectedDayIndex][d],
            current_u_ms: cellSeries.current_u_ms[selectedDayIndex][d],
            current_v_ms: cellSeries.current_v_ms[selectedDayIndex][d],
            wave_height_m: cellSeries.wave_height_m[selectedDayIndex][d],
            chlorophyll_mg_m3: cellSeries.chlorophyll_mg_m3[selectedDayIndex][d],
          }))
        : meta.depth_m.map((depth_m, d) => ({
            depth_m,
            sst_c: snapshot.sst_c[d][latIdx][lonIdx],
            salinity_psu: snapshot.salinity_psu[d][latIdx][lonIdx],
            current_u_ms: snapshot.current_u_ms[d][latIdx][lonIdx],
            current_v_ms: snapshot.current_v_ms[d][latIdx][lonIdx],
            wave_height_m: snapshot.wave_height_m[d][latIdx][lonIdx],
            chlorophyll_mg_m3: snapshot.chlorophyll_mg_m3[d][latIdx][lonIdx],
          }));
    return raw.every(isCompleteLevel) ? raw : [];
  }, [meta, snapshot, selected, cellSeries, selectedDayIndex]);

  const handlePointClick = useCallback((index: GridIndex) => {
    setSelected(index);
    setCubeOpen(true);
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-6 py-28">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="font-nav text-xs opacity-60">3D Cube Explorer · {REGION_LABEL}</p>
          <h1 className="font-display mt-2 text-4xl sm:text-5xl">Ocean Explorer</h1>
        </div>
        {meta && (
          <select
            value={depthIdx}
            onChange={(e) => setDepthIdx(Number(e.target.value))}
            className="font-nav rounded-full border bg-transparent px-4 py-1.5 text-xs"
            style={{ borderColor: "var(--color-border)" }}
          >
            {meta.depth_m.map((d, i) => (
              <option key={i} value={i}>
                Depth: {i === 0 ? "surface" : `${d.toFixed(0)}m`}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <div
          className="mt-8 rounded-xl border px-5 py-4 text-sm"
          style={{ borderColor: "var(--color-trust-red)", color: "var(--color-trust-red)" }}
        >
          Can't reach the Graph Fusion Engine at <code className="font-mono-data">{API_BASE_URL}</code>. {error}
        </div>
      )}

      <p className="mt-6 max-w-2xl text-sm opacity-60">
        Drag to fly anywhere across the Bay of Bengal, Google-Earth-style -- every point is a real Copernicus Marine
        grid cell. Arrow keys pan cell to cell, Page Up/Down step through real depth levels, Enter or a click opens
        the selected cell's cube: a fixed-dimension volumetric view with an animated real sea surface (real wave
        height), real current-direction arrows, and real temperature-colored depth layers.
      </p>

      {!meta && !error && <p className="mt-8 text-sm opacity-50">Loading the real volumetric grid…</p>}

      {meta && (
        <div className="mt-8 h-[640px] w-full overflow-hidden rounded-2xl" style={{ border: "1px solid var(--color-border)" }}>
          <CesiumGlobe points={points} regionBBox={REGION_BBOX} selected={selected} onPointClick={handlePointClick} />
        </div>
      )}

      {cubeOpen && selected && meta && levels.length > 0 && (
        <CubeInspector
          lat={meta.lat[selected.latIdx]}
          lon={meta.lon[selected.lonIdx]}
          source={snapshot?.time ? `Real Copernicus Marine data (GLORYS reanalysis) · ${REGION_LABEL}` : ""}
          levels={levels}
          timeLabel={cellSeries && selectedDayIndex >= 0 ? cellSeries.time[selectedDayIndex] : (snapshot?.time ?? "")}
          availableDays={cellSeries?.time ?? null}
          selectedDayIndex={selectedDayIndex}
          onDayIndexChange={setSelectedDayIndex}
          nowcastInfo={nowcastInfo}
          onClose={() => setCubeOpen(false)}
        />
      )}
    </div>
  );
}
