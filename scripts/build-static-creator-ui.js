#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const source = path.join(root, "web", "static-creator-ui");
const dist = path.join(root, "dist");

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
    return;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function assertFile(relativePath) {
  const file = path.join(dist, relativePath);
  if (!fs.existsSync(file)) {
    throw new Error(`Static build missing expected file: ${relativePath}`);
  }
}

if (!fs.existsSync(source)) {
  throw new Error(`Static UI source folder not found: ${source}`);
}

fs.rmSync(dist, { recursive: true, force: true });
copyRecursive(source, dist);

assertFile("index.html");
assertFile(path.join("assets", "app.js"));
assertFile(path.join("assets", "portfolio-api.js"));
assertFile(path.join("assets", "styles.css"));
assertFile("sample-brief.json");
assertFile("wordpress-embed.html");

console.log(`Static Creator UI copied to ${path.relative(root, dist)}`);
console.log("Vercel can serve dist/ without scanning Python/FastAPI entrypoints.");
