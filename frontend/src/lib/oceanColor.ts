import * as THREE from "three";

/** Same physically-motivated SST range used server-side (graph_fusion
 * config.py VARIABLE_RANGES) purely for a temperature color scale -- never
 * clipped in any displayed/returned value, only in how it's colored. Shared
 * by the globe's point cloud and the cube's depth slabs so a given real
 * temperature always reads as the same color everywhere in the Explorer. */
const SST_COLOR_MIN = 20;
const SST_COLOR_MAX = 32;

const COLD = new THREE.Color("#2b6cb0");
const WARM = new THREE.Color("#c1402f");

export function sstToColor(sstC: number | null): string {
  if (sstC === null) return "#79a4c0";
  const t = THREE.MathUtils.clamp((sstC - SST_COLOR_MIN) / (SST_COLOR_MAX - SST_COLOR_MIN), 0, 1);
  return `#${COLD.clone().lerp(WARM, t).getHexString()}`;
}
