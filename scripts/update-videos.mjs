#!/usr/bin/env node
// Refresh src/data/videos.json from YouTube playlist RSS.
// Run locally (Japan IP works, GitHub Actions is blocked).
// Usage: node scripts/update-videos.mjs

import { writeFileSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(__dirname, '../src/data/videos.json');

const PLAYLISTS = {
  playlist1: 'PLNdj0Iz_UsvPDvPgyDfii0qix4aHPaa_1', // Free Association
  playlist2: 'PLNdj0Iz_UsvMTLJxFynqiRLgM75kh1ugp', // Music Videos
};

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

async function fetchPlaylist(id) {
  const res = await fetch(`https://www.youtube.com/feeds/videos.xml?playlist_id=${id}`, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.5' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${id}`);
  const xml = await res.text();
  const entries = xml.match(/<entry>([\s\S]*?)<\/entry>/g) || [];
  if (entries.length === 0) throw new Error(`0 entries for ${id}`);
  return entries.map((e) => ({
    videoId: e.match(/<yt:videoId>(.*?)<\/yt:videoId>/)?.[1] ?? '',
    title: e.match(/<media:title>(.*?)<\/media:title>/)?.[1]
      ?? e.match(/<title>(.*?)<\/title>/)?.[1] ?? '',
  }));
}

const next = {};
for (const [name, id] of Object.entries(PLAYLISTS)) {
  process.stdout.write(`  ${name} (${id})… `);
  next[name] = await fetchPlaylist(id);
  console.log(`${next[name].length} videos`);
}

let prev = {};
try { prev = JSON.parse(readFileSync(OUT, 'utf-8')); } catch {}
const changed = JSON.stringify(prev) !== JSON.stringify(next);

if (!changed) {
  console.log('no changes');
  process.exit(0);
}

writeFileSync(OUT, JSON.stringify(next, null, 2) + '\n');
console.log(`updated ${OUT}`);
