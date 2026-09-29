#!/usr/bin/env node
// Refresh src/data/videos.json from YouTube playlists.
//
// YouTube's RSS endpoint (feeds/videos.xml) started returning 404 for every
// playlist/channel in Sep 2026, so we now scrape the playlist page and read
// the embedded `ytInitialData` JSON instead.
//
// Run locally (Japan IP works; GitHub Actions runners get blocked).
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

// Extract the ytInitialData blob. YouTube serves two layouts at random (seen Sep 2026):
//   new: <script id="yt-initial-data" type="application/json">{...}</script>
//   old: var ytInitialData = {...};
// The old one uses brace-matching rather than a regex so nested braces /
// strings inside the JSON don't trip it.
function extractInitialData(html) {
  const tag = html.match(/<script[^>]*\bid="yt-initial-data"[^>]*>/);
  if (tag) {
    const begin = tag.index + tag[0].length;
    const end = html.indexOf('</script>', begin);
    if (end !== -1) return JSON.parse(html.slice(begin, end));
  }
  const marker = 'var ytInitialData = ';
  const start = html.indexOf(marker);
  if (start === -1) throw new Error('ytInitialData not found');
  let i = start + marker.length;
  let depth = 0, inStr = false, esc = false;
  const begin = i;
  for (; i < html.length; i++) {
    const c = html[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') inStr = true;
    else if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) { i++; break; } }
  }
  return JSON.parse(html.slice(begin, i));
}

// Walk the whole tree collecting playlist items in document order.
//
// Current YouTube layout (2026): each item is a `lockupViewModel` with
//   contentType === 'LOCKUP_CONTENT_TYPE_VIDEO'
//   contentId    -> videoId
//   metadata.lockupMetadataViewModel.title.content -> title
// Older layout used `playlistVideoRenderer` { videoId, title.runs[] }; kept
// as a fallback in case YouTube serves it again.
function collectVideos(node, out = []) {
  if (Array.isArray(node)) { for (const n of node) collectVideos(n, out); return out; }
  if (node && typeof node === 'object') {
    if (node.lockupViewModel) {
      const l = node.lockupViewModel;
      if (l.contentType === 'LOCKUP_CONTENT_TYPE_VIDEO' && l.contentId) {
        const title = l.metadata?.lockupMetadataViewModel?.title?.content ?? '';
        out.push({ videoId: l.contentId, title });
      }
    } else if (node.playlistVideoRenderer) {
      const r = node.playlistVideoRenderer;
      const title = (r.title?.runs ?? []).map((x) => x.text).join('') || r.title?.simpleText || '';
      if (r.videoId) out.push({ videoId: r.videoId, title });
    }
    for (const v of Object.values(node)) collectVideos(v, out);
  }
  return out;
}

async function fetchPlaylist(id) {
  const res = await fetch(`https://www.youtube.com/playlist?list=${id}`, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'ja,en-US;q=0.8,en;q=0.5' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${id}`);
  const html = await res.text();
  const data = extractInitialData(html);
  const seen = new Set();
  const videos = collectVideos(data).filter((v) => !seen.has(v.videoId) && seen.add(v.videoId));
  if (videos.length === 0) throw new Error(`0 videos parsed for ${id}`);
  return videos;
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
