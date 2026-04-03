/**
 * rehype-auto-embed
 *
 * A rehype plugin that transforms standalone URLs in content into rich embeds:
 * - YouTube URLs (youtu.be, youtube.com/watch) -> responsive iframe
 * - Other URLs on their own line -> OGP link card (with cached metadata)
 *
 * Works on the HAST (HTML AST) so it handles both:
 * - Bare URLs in markdown that become <p><a href="URL">URL</a></p>
 * - Already-linked URLs from Movable Type HTML exports
 *
 * Existing <iframe> embeds are left untouched.
 */

import { visit } from 'unist-util-visit';
import { fromHtml } from 'hast-util-from-html';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

const CACHE_DIR = path.join(
  fileURLToPath(new URL('.', import.meta.url)),
  '../../.ogp-cache',
);
const CACHE_FILE = path.join(CACHE_DIR, 'ogp-cache.json');
const CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

/** @type {Record<string, { ts: number, data: OgpData | null }>} */
let cache = {};

function loadCache() {
  try {
    if (fs.existsSync(CACHE_FILE)) {
      cache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf-8'));
    }
  } catch {
    cache = {};
  }
}

function saveCache() {
  try {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2), 'utf-8');
  } catch {
    // silently ignore cache write errors
  }
}

// ---------------------------------------------------------------------------
// YouTube helpers
// ---------------------------------------------------------------------------

const YOUTUBE_PATTERNS = [
  // youtu.be/VIDEO_ID
  /^https?:\/\/(?:www\.)?youtu\.be\/([A-Za-z0-9_-]+)/,
  // youtube.com/watch?v=VIDEO_ID
  /^https?:\/\/(?:www\.)?youtube\.com\/watch\?v=([A-Za-z0-9_-]+)/,
];

function extractYouTubeId(url) {
  for (const pattern of YOUTUBE_PATTERNS) {
    const m = url.match(pattern);
    if (m) return m[1];
  }
  return null;
}

function makeYouTubeEmbed(videoId) {
  const html = `<div class="embed-youtube"><iframe src="https://www.youtube.com/embed/${videoId}" title="YouTube video" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen loading="lazy"></iframe></div>`;
  const fragment = fromHtml(html, { fragment: true });
  return fragment.children[0];
}

// ---------------------------------------------------------------------------
// OGP fetch
// ---------------------------------------------------------------------------

/**
 * @typedef {{ title?: string, description?: string, image?: string, favicon?: string, siteName?: string }} OgpData
 */

/**
 * Fetch OGP metadata for a URL, with caching.
 * Returns null on failure.
 * @param {string} url
 * @returns {Promise<OgpData | null>}
 */
async function fetchOgp(url) {
  // Check cache
  const cached = cache[url];
  if (cached && Date.now() - cached.ts < CACHE_MAX_AGE_MS) {
    return cached.data;
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (compatible; AstroOGPBot/1.0; +https://intheblueshirt.com)',
        Accept: 'text/html,application/xhtml+xml',
      },
      redirect: 'follow',
    });
    clearTimeout(timeout);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const contentType = res.headers.get('content-type') || '';
    if (!contentType.includes('text/html') && !contentType.includes('xhtml')) {
      throw new Error('Not HTML');
    }

    const html = await res.text();
    const data = parseOgp(html, url);

    cache[url] = { ts: Date.now(), data };
    return data;
  } catch {
    // Cache the failure too so we don't retry on every build
    cache[url] = { ts: Date.now(), data: null };
    return null;
  }
}

/**
 * Parse OGP meta tags from HTML string.
 */
function parseOgp(html, url) {
  const get = (pattern) => {
    const m = html.match(pattern);
    return m ? decodeHtmlEntities(m[1].trim()) : undefined;
  };

  const title =
    get(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']/i) ??
    get(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:title["']/i) ??
    get(/<title[^>]*>([^<]+)<\/title>/i);

  const description =
    get(
      /<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)["']/i,
    ) ??
    get(
      /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:description["']/i,
    ) ??
    get(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i) ??
    get(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']description["']/i);

  const image =
    get(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i) ??
    get(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);

  const siteName =
    get(
      /<meta[^>]+property=["']og:site_name["'][^>]+content=["']([^"']+)["']/i,
    ) ??
    get(
      /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:site_name["']/i,
    );

  // Favicon: look for <link rel="icon" ...>
  let favicon =
    get(
      /<link[^>]+rel=["'](?:shortcut )?icon["'][^>]+href=["']([^"']+)["']/i,
    ) ??
    get(
      /<link[^>]+href=["']([^"']+)["'][^>]+rel=["'](?:shortcut )?icon["']/i,
    );

  // Resolve relative URLs
  let origin;
  try {
    origin = new URL(url).origin;
  } catch {
    origin = '';
  }

  if (favicon && !favicon.startsWith('http')) {
    favicon = favicon.startsWith('/')
      ? origin + favicon
      : origin + '/' + favicon;
  }
  if (!favicon) {
    favicon = origin + '/favicon.ico';
  }

  const resolvedImage =
    image && !image.startsWith('http')
      ? image.startsWith('/')
        ? origin + image
        : origin + '/' + image
      : image;

  return {
    title: title || new URL(url).hostname,
    description: description || '',
    image: resolvedImage,
    favicon,
    siteName: siteName || new URL(url).hostname,
  };
}

function decodeHtmlEntities(str) {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, '/');
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function makeLinkCard(url, ogp) {
  const title = escapeHtml(ogp.title);
  const desc = escapeHtml(
    ogp.description ? ogp.description.slice(0, 120) : '',
  );
  const siteName = escapeHtml(ogp.siteName);
  const favicon = escapeHtml(ogp.favicon);
  const image = ogp.image ? escapeHtml(ogp.image) : '';

  const imageHtml = image
    ? `<div class="link-card__image"><img src="${image}" alt="" loading="lazy" /></div>`
    : '';

  const html = `<a href="${escapeHtml(url)}" class="link-card" target="_blank" rel="noopener noreferrer">${imageHtml}<div class="link-card__content"><div class="link-card__title">${title}</div>${desc ? `<div class="link-card__description">${desc}</div>` : ''}<div class="link-card__meta"><img src="${favicon}" alt="" class="link-card__favicon" width="16" height="16" loading="lazy" onerror="this.style.display='none'" /><span class="link-card__hostname">${siteName}</span></div></div></a>`;

  const fragment = fromHtml(html, { fragment: true });
  return fragment.children[0];
}

function makeFallbackLink(url) {
  const fragment = fromHtml(
    `<p><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a></p>`,
    { fragment: true },
  );
  return fragment.children[0];
}

// ---------------------------------------------------------------------------
// Detect standalone URL paragraphs
// ---------------------------------------------------------------------------

/**
 * Check if a HAST <p> node contains only a single URL
 * (possibly wrapped in <a>), with no other meaningful content.
 *
 * Returns the URL string or null.
 */
function extractStandaloneUrl(node) {
  if (node.tagName !== 'p') return null;

  const meaningful = (node.children || []).filter((child) => {
    if (child.type === 'text' && child.value.trim() === '') return false;
    return true;
  });

  if (meaningful.length !== 1) return null;

  const child = meaningful[0];

  // Case 1: <p><a href="URL">URL</a></p> where link text matches the URL
  if (child.tagName === 'a' && child.properties?.href) {
    const href = child.properties.href;
    const textContent = getTextContent(child).trim();
    // Link text should be the URL itself (or very close)
    if (
      textContent === href ||
      textContent === href.replace(/^https?:\/\//, '') ||
      isUrlLike(textContent)
    ) {
      return href;
    }
  }

  // Case 2: bare text that is a URL (shouldn't happen after remark, but just in case)
  if (child.type === 'text') {
    const text = child.value.trim();
    if (/^https?:\/\/\S+$/.test(text)) {
      return text;
    }
  }

  return null;
}

function getTextContent(node) {
  if (node.type === 'text') return node.value;
  if (node.children) return node.children.map(getTextContent).join('');
  return '';
}

function isUrlLike(str) {
  return /^https?:\/\/\S+$/.test(str) || /^[a-z0-9.-]+\.[a-z]{2,}/.test(str);
}

/**
 * Check if a <p> node contains an existing <iframe> (already embedded).
 */
function containsIframe(node) {
  if (node.tagName === 'iframe') return true;
  if (node.children) return node.children.some(containsIframe);
  return false;
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

export default function rehypeAutoEmbed() {
  return async function transformer(tree) {
    loadCache();

    // Collect nodes to transform
    /** @type {{ parent: any, index: number, url: string }[]} */
    const replacements = [];

    visit(tree, 'element', (node, index, parent) => {
      if (!parent || index === undefined) return;

      // Skip paragraphs that already contain iframes
      if (node.tagName === 'p' && containsIframe(node)) return;

      const url = extractStandaloneUrl(node);
      if (url) {
        replacements.push({ parent, index, url });
      }
    });

    if (replacements.length === 0) return;

    // Process all OGP fetches concurrently for non-YouTube URLs
    const ogpPromises = replacements.map(async (r) => {
      const ytId = extractYouTubeId(r.url);
      if (ytId) {
        r.youtubeId = ytId;
        return;
      }
      r.ogp = await fetchOgp(r.url);
    });

    await Promise.all(ogpPromises);

    // Apply replacements in reverse order (so indices stay valid)
    for (let i = replacements.length - 1; i >= 0; i--) {
      const { parent, index, url, youtubeId, ogp } = replacements[i];

      let newNode;
      if (youtubeId) {
        newNode = makeYouTubeEmbed(youtubeId);
      } else if (ogp) {
        newNode = makeLinkCard(url, ogp);
      } else {
        // Fetch failed - leave as a regular link
        newNode = makeFallbackLink(url);
      }

      parent.children.splice(index, 1, newNode);
    }

    saveCache();
  };
}
