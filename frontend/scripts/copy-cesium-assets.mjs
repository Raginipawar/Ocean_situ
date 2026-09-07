// Copies CesiumJS's static runtime assets (Workers/Assets/Widgets/ThirdParty)
// from node_modules into public/cesium, where Vite serves them verbatim at
// /cesium/... in both dev and production builds. Cesium needs these to be
// plain static files (web workers, terrain/imagery data, widget CSS) --
// they can't be bundled through Vite's normal JS/CSS pipeline. Runs
// automatically via the `postinstall` npm script so a fresh `npm install`
// is enough; not committed to git (see .gitignore) since it's fully
// derived from the installed cesium package.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const src = join(root, "node_modules", "cesium", "Build", "Cesium");
const dest = join(root, "public", "cesium");

if (!existsSync(src)) {
  console.warn("[copy-cesium-assets] cesium package not found, skipping (not installed yet?)");
  process.exit(0);
}

mkdirSync(dest, { recursive: true });
for (const folder of ["Assets", "Workers", "Widgets", "ThirdParty"]) {
  cpSync(join(src, folder), join(dest, folder), { recursive: true });
}

console.log(`[copy-cesium-assets] copied Cesium static assets to ${dest}`);
