import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const raw = readFileSync(join(__dirname, 'blog.intheblueshirt.com.export.txt'), 'utf-8');

// Split entries by the "--------" separator
const entries = raw.split(/\n--------\n/).filter(s => s.trim());

const blogDir = join(__dirname, '..', 'src', 'content', 'blog');

let count = 0;

for (const entry of entries) {
  // Split metadata section from body section by "-----"
  const sections = entry.split(/\n-----\n/);
  if (sections.length < 2) continue;

  const metaSection = sections[0];
  const bodySection = sections.slice(1).join('\n-----\n');

  // Parse metadata
  const meta = {};
  for (const line of metaSection.split('\n')) {
    const match = line.match(/^(\w[\w\s]*?):\s*(.*)$/);
    if (match) {
      meta[match[1].trim()] = match[2].trim();
    }
  }

  // Only include published entries
  if (meta['STATUS'] !== 'Publish') continue;

  // Parse date: "MM/DD/YYYY HH:MM:SS" -> Date object
  const dateStr = meta['DATE'];
  if (!dateStr) continue;
  const dateMatch = dateStr.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})$/);
  if (!dateMatch) continue;
  const [, month, day, year, hour, min, sec] = dateMatch;
  const isoDate = `${year}-${month}-${day}T${hour}:${min}:${sec}`;

  // Extract body (remove "BODY:" prefix)
  let body = bodySection.replace(/^BODY:\n?/, '');
  // Also remove any trailing EXTENDED BODY or COMMENT sections
  body = body.split(/\nEXTENDED BODY:/)[0];
  body = body.split(/\nEXCERPT:/)[0];
  body = body.trim();

  // Title
  let title = meta['TITLE'] || '無題';
  if (!title) title = '無題';

  // Generate slug from BASENAME (e.g. "2025/04/06/150645" -> "2025-04-06-150645")
  const basename = meta['BASENAME'] || '';
  const slug = basename.replace(/\//g, '-');
  if (!slug) continue;

  // Create description from first paragraph text (strip HTML, truncate)
  const textContent = body.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  const description = textContent.substring(0, 120).replace(/"/g, '\\"');

  // Escape title for YAML
  const safeTitle = title.replace(/"/g, '\\"');

  // Build frontmatter
  const frontmatter = `---
title: "${safeTitle}"
pubDate: "${isoDate}"
description: "${description}"
---`;

  const fileContent = `${frontmatter}\n\n${body}\n`;

  // Write file
  const filePath = join(blogDir, `${slug}.md`);
  writeFileSync(filePath, fileContent, 'utf-8');
  count++;
}

console.log(`Converted ${count} blog posts to ${blogDir}`);
