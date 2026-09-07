import "../../lib/cesiumSetup";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { useEffect, useRef, useState } from "react";

export interface GridIndex {
  latIdx: number;
  lonIdx: number;
}

export interface GridPoint extends GridIndex {
  lat: number;
  lon: number;
  /** Literal hex, precomputed by the caller (see lib/oceanColor.ts) --
   * Three.js/Cesium materials can't parse a CSS var() reference. */
  color: string;
}

interface RegionBBox {
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

interface CesiumGlobeProps {
  /** Every real grid cell (up to 69x81 = 5589 points), colored by the
   * currently-selected depth level's real SST. */
  points: GridPoint[];
  regionBBox: RegionBBox;
  selected: GridIndex | null;
  onPointClick: (index: GridIndex) => void;
  className?: string;
}

function samePoint(a: GridIndex | null, b: GridIndex): boolean {
  return a !== null && a.latIdx === b.latIdx && a.lonIdx === b.lonIdx;
}

/**
 * A second, genuinely distinct 3D globe engine (CesiumJS) for the Cube
 * Explorer, alongside the React Three Fiber globe used on the Digital Twin
 * page -- deliberately not replacing it there.
 *
 * Free-roam, Google-Earth-style navigation across the whole Bay of Bengal
 * (and beyond) -- the camera is never locked to a bounding box, only framed
 * there initially. Every real grid cell renders as a point (a
 * PointPrimitiveCollection, not individual Entities -- thousands of
 * Entities gets sluggish, PointPrimitiveCollection is built for exactly
 * this scale).
 *
 * Runs entirely offline/token-free on purpose: no Cesium ion account, no
 * network imagery fetch, nothing that can fail because a jury room has bad
 * wifi. Base imagery is Cesium's own bundled Natural Earth II texture
 * (ships with the npm package, copied to public/cesium/ -- see
 * lib/cesiumSetup.ts) and terrain is the default flat WGS84 ellipsoid.
 */
export function CesiumGlobe({ points, regionBBox, selected, onPointClick, className }: CesiumGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const collectionRef = useRef<Cesium.PointPrimitiveCollection | null>(null);
  const onPointClickRef = useRef(onPointClick);
  onPointClickRef.current = onPointClick;
  const hasFlownRef = useRef(false);
  // The viewer initializes asynchronously (awaiting the imagery provider),
  // so `points` can already be loaded before viewerRef.current is set -- a
  // plain ref wouldn't re-trigger the sync effects once the viewer becomes
  // ready. This state flip does.
  const [viewerReady, setViewerReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;
    let viewer: Cesium.Viewer | null = null;

    async function init() {
      const imageryProvider = await Cesium.TileMapServiceImageryProvider.fromUrl(
        Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII"),
      );
      if (cancelled || !containerRef.current) return;

      viewer = new Cesium.Viewer(containerRef.current, {
        baseLayer: new Cesium.ImageryLayer(imageryProvider),
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: false,
      });
      viewer.scene.globe.enableLighting = false;

      // Initial framing only -- camera stays fully free after this (no
      // rectangle lock), so the whole Bay of Bengal (and beyond) is
      // reachable by dragging/zooming, same as Google Earth.
      viewer.camera.setView({
        destination: Cesium.Rectangle.fromDegrees(
          regionBBox.lonMin - 3,
          regionBBox.latMin - 3,
          regionBBox.lonMax + 3,
          regionBBox.latMax + 3,
        ),
      });

      const collection = new Cesium.PointPrimitiveCollection();
      viewer.scene.primitives.add(collection);
      collectionRef.current = collection;

      viewer.screenSpaceEventHandler.setInputAction((movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
        const picked = viewer!.scene.pick(movement.position);
        const id = picked?.primitive?.id as GridIndex | undefined;
        if (id && typeof id.latIdx === "number") onPointClickRef.current(id);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

      viewerRef.current = viewer;
      // Exposed for debugging/e2e tests only (harmless in production).
      (window as unknown as { __cesiumViewer?: Cesium.Viewer; __Cesium?: typeof Cesium }).__cesiumViewer = viewer;
      (window as unknown as { __cesiumViewer?: Cesium.Viewer; __Cesium?: typeof Cesium }).__Cesium = Cesium;
      setViewerReady(true);
    }

    init();

    return () => {
      cancelled = true;
      setViewerReady(false);
      viewer?.destroy();
      viewerRef.current = null;
      collectionRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const collection = collectionRef.current;
    const viewer = viewerRef.current;
    if (!collection || !viewer || viewer.isDestroyed()) return;
    collection.removeAll();
    for (const p of points) {
      const isSelected = samePoint(selected, p);
      const color = Cesium.Color.fromCssColorString(p.color);
      collection.add({
        id: { latIdx: p.latIdx, lonIdx: p.lonIdx } satisfies GridIndex,
        position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat),
        pixelSize: isSelected ? 15 : 5,
        color,
        outlineColor: isSelected ? Cesium.Color.WHITE : color.withAlpha(0.35),
        outlineWidth: isSelected ? 3 : 0,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      });
    }
  }, [points, selected, viewerReady]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed() || !selected) return;
    // The very first `selected` is just the default starting cell, not a
    // real navigation -- skip the fly-in so the initial view stays the
    // wide whole-Bay-of-Bengal framing set above. Only actual navigation
    // (arrow keys, a click) should zoom the camera in to follow.
    if (!hasFlownRef.current) {
      hasFlownRef.current = true;
      return;
    }
    const point = points.find((p) => p.latIdx === selected.latIdx && p.lonIdx === selected.lonIdx);
    if (!point) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(point.lon, point.lat, 220_000),
      duration: 0.5,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, viewerReady]);

  return <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }} />;
}
