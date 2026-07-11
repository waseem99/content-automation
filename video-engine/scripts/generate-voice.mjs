#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";

const input = process.argv[2];
if (!input) {
  console.error("Usage: node scripts/generate-voice.mjs <project.json>");
  process.exit(1);
}

const root = process.cwd();
const projectPath = path.resolve(root, input);
const project = JSON.parse(fs.readFileSync(projectPath, "utf8"));
const outDir = path.join(root, "out");
const publicDir = path.join(root, "public", "generated");
fs.mkdirSync(outDir, {recursive: true});
fs.mkdirSync(publicDir, {recursive: true});

const provider = (process.env.VOICE_PROVIDER || "kokoro").toLowerCase();

const writeCaptionFallback = (reason) => {
  const fallback = {
    ...project,
    voiceoverFile: undefined,
    voiceGeneration: {
      provider: "caption_only_fallback",
      generatedAt: new Date().toISOString(),
      reason,
    },
  };
  const fallbackPath = path.join(outDir, `${project.id}-caption-only.json`);
  fs.writeFileSync(fallbackPath, JSON.stringify(fallback, null, 2));
  console.warn(reason);
  console.warn(`Caption-led project written to ${fallbackPath}`);
};

if (provider === "caption_only") {
  writeCaptionFallback("VOICE_PROVIDER=caption_only");
  process.exit(0);
}

if (provider === "kokoro") {
  const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
  const result = spawnSync(
    python,
    [path.join(root, "scripts", "generate_voice_kokoro.py"), projectPath],
    {
      cwd: root,
      stdio: "inherit",
      env: process.env,
    },
  );
  if (result.error) {
    console.error(`Unable to start local Kokoro generator: ${result.error.message}`);
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

if (provider !== "elevenlabs") {
  console.error(`Unsupported VOICE_PROVIDER: ${provider}`);
  process.exit(1);
}

const apiKey = process.env.ELEVENLABS_API_KEY;
const voiceId = process.env.ELEVENLABS_VOICE_ID;
const modelId = process.env.ELEVENLABS_MODEL_ID || "eleven_multilingual_v2";

if (!apiKey || !voiceId) {
  writeCaptionFallback("ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID is missing");
  process.exit(0);
}

const endpoint = `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(voiceId)}/with-timestamps?output_format=mp3_44100_128`;
const response = await fetch(endpoint, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "xi-api-key": apiKey,
  },
  body: JSON.stringify({
    text: project.narration,
    model_id: modelId,
    voice_settings: {
      stability: 0.48,
      similarity_boost: 0.72,
      style: 0.28,
      use_speaker_boost: true,
    },
  }),
});

if (!response.ok) {
  const body = await response.text();
  throw new Error(`ElevenLabs request failed (${response.status}): ${body.slice(0, 500)}`);
}

const payload = await response.json();
if (!payload.audio_base64) {
  throw new Error("ElevenLabs response did not include audio_base64");
}

const audioName = `${project.id}.mp3`;
const audioPath = path.join(publicDir, audioName);
fs.writeFileSync(audioPath, Buffer.from(payload.audio_base64, "base64"));

const alignmentPath = path.join(outDir, `${project.id}-alignment.json`);
fs.writeFileSync(
  alignmentPath,
  JSON.stringify(
    {
      provider: "elevenlabs",
      modelId,
      voiceId,
      alignment: payload.alignment ?? null,
      normalizedAlignment: payload.normalized_alignment ?? null,
    },
    null,
    2,
  ),
);

const voicedProject = {
  ...project,
  voiceoverFile: `generated/${audioName}`,
  voiceGeneration: {
    provider: "elevenlabs",
    modelId,
    voiceId,
    generatedAt: new Date().toISOString(),
    alignmentFile: path.relative(root, alignmentPath),
  },
};
const voicedProjectPath = path.join(outDir, `${project.id}-voiced.json`);
fs.writeFileSync(voicedProjectPath, JSON.stringify(voicedProject, null, 2));

console.log(`Voiceover written to ${audioPath}`);
console.log(`Alignment written to ${alignmentPath}`);
console.log(`Render project written to ${voicedProjectPath}`);
