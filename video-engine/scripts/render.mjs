#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {bundle} from "@remotion/bundler";
import {renderMedia, selectComposition} from "@remotion/renderer";

const input = process.argv[2];
const requestedOutput = process.argv[3];
if (!input) {
  console.error("Usage: node scripts/render.mjs <project.json> [output.mp4]");
  process.exit(1);
}

const root = process.cwd();
const projectPath = path.resolve(root, input);
const validation = spawnSync(
  process.execPath,
  [path.join(root, "scripts", "validate-project.mjs"), projectPath],
  {stdio: "inherit"}
);
if (validation.status !== 0) process.exit(validation.status ?? 1);

const project = JSON.parse(fs.readFileSync(projectPath, "utf8"));
const outDir = path.join(root, "out");
fs.mkdirSync(outDir, {recursive: true});
const output = requestedOutput
  ? path.resolve(root, requestedOutput)
  : path.join(outDir, `${project.id}.mp4`);
fs.mkdirSync(path.dirname(output), {recursive: true});

console.log("Bundling Remotion composition...");
const serveUrl = await bundle({
  entryPoint: path.join(root, "src", "index.ts"),
  publicDir: path.join(root, "public")
});

const inputProps = {project};
const composition = await selectComposition({
  serveUrl,
  id: "RawrNationShort",
  inputProps
});

console.log(`Rendering ${composition.width}x${composition.height} at ${composition.fps}fps...`);
await renderMedia({
  composition,
  serveUrl,
  codec: "h264",
  outputLocation: output,
  inputProps,
  pixelFormat: "yuv420p",
  audioCodec: "aac",
  concurrency: Math.max(1, Math.min(4, Number(process.env.REMOTION_CONCURRENCY || 2))),
  overwrite: true
});

const manifest = {
  schemaVersion: "p65.render_result.v1",
  projectId: project.id,
  compositionId: composition.id,
  output,
  width: composition.width,
  height: composition.height,
  fps: composition.fps,
  durationInFrames: composition.durationInFrames,
  voiceoverIncluded: Boolean(project.voiceoverFile),
  editorialStatus: project.editorialStatus,
  humanReviewRequired: true,
  renderedAt: new Date().toISOString()
};
const manifestPath = output.replace(/\.mp4$/i, ".render.json");
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

console.log(`MP4 written to ${output}`);
console.log(`Render manifest written to ${manifestPath}`);
console.log("Human review is required before publishing.");
