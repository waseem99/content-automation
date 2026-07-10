#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const input = process.argv[2];
if (!input) {
  console.error("Usage: node scripts/validate-project.mjs <project.json>");
  process.exit(1);
}

const projectPath = path.resolve(process.cwd(), input);
const project = JSON.parse(fs.readFileSync(projectPath, "utf8"));
const errors = [];
const warnings = [];

const requiredStrings = ["id", "title", "narration", "disclosure", "callToAction"];
for (const key of requiredStrings) {
  if (typeof project[key] !== "string" || !project[key].trim()) {
    errors.push(`${key} must be a non-empty string`);
  }
}

if (project.schemaVersion !== "p65.video_project.v1") {
  errors.push("schemaVersion must be p65.video_project.v1");
}
if (project.format !== "vertical_short") {
  errors.push("P65 currently supports vertical_short only");
}
if (project.humanReviewRequired !== true) {
  errors.push("humanReviewRequired must be true");
}
if (!project.render || project.render.width !== 1080 || project.render.height !== 1920) {
  errors.push("render dimensions must be 1080x1920 for the P65 template");
}
if (project.render?.fps !== 30) {
  errors.push("render fps must be 30");
}
if (project.render?.durationSeconds < 15 || project.render?.durationSeconds > 60) {
  errors.push("durationSeconds must be between 15 and 60 for the current template");
}
if (!Array.isArray(project.scenes) || project.scenes.length < 5) {
  errors.push("at least five scenes are required");
}
if (!Array.isArray(project.captions) || project.captions.length < 5) {
  errors.push("at least five caption chunks are required");
}
if (!Array.isArray(project.sources) || project.sources.length < 1) {
  errors.push("at least one editorial source record is required");
}

let cursor = 0;
for (const [index, scene] of (project.scenes || []).entries()) {
  if (scene.startSec !== cursor) {
    errors.push(`scene ${index + 1} must start at ${cursor}, received ${scene.startSec}`);
  }
  if (!(scene.endSec > scene.startSec)) {
    errors.push(`scene ${index + 1} has an invalid time range`);
  }
  cursor = scene.endSec;
}
if (Math.abs(cursor - project.render.durationSeconds) > 0.001) {
  errors.push("scenes must cover the full render duration without a gap");
}

for (const [index, caption] of (project.captions || []).entries()) {
  if (!(caption.endSec > caption.startSec)) {
    errors.push(`caption ${index + 1} has an invalid time range`);
  }
  if (caption.endSec > project.render.durationSeconds) {
    errors.push(`caption ${index + 1} ends after the video duration`);
  }
  if (caption.text.split(/\s+/).length > 8) {
    warnings.push(`caption ${index + 1} is longer than the recommended eight words`);
  }
}

if (project.editorialStatus !== "approved") {
  warnings.push(`editorialStatus is ${project.editorialStatus}; do not publish this render`);
}
if (project.sources?.some((source) => source.status !== "verified")) {
  warnings.push("one or more source records still require verification");
}
if (!project.voiceoverFile) {
  warnings.push("no voiceoverFile is set; the render will be caption-led and silent");
}

if (errors.length) {
  console.error("Project validation failed:");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log(`Validated ${project.id}`);
console.log(`Scenes: ${project.scenes.length}`);
console.log(`Captions: ${project.captions.length}`);
console.log(`Duration: ${project.render.durationSeconds}s`);
for (const warning of warnings) console.warn(`Warning: ${warning}`);
