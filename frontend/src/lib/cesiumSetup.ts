/**
 * Must be imported before any other Cesium code runs. Cesium resolves its
 * own static assets (Web Workers, Assets/Textures, Widgets CSS) relative to
 * `window.CESIUM_BASE_URL` -- there is no bundler-aware way to point it at
 * an npm package, so those files are copied to public/cesium/ instead (see
 * scripts/copy-cesium-assets.mjs) and served verbatim by Vite at /cesium/.
 */
declare global {
  interface Window {
    CESIUM_BASE_URL?: string;
  }
}

window.CESIUM_BASE_URL = "/cesium/";

export {};
