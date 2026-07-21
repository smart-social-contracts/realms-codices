#!/usr/bin/env node
/**
 * Serve lifecycle E2E artifacts for remote viewing via SSH tunnel.
 *
 *   ssh -L 9323:127.0.0.1:9323 srv1.pzjj.org
 *   node scripts/serve-e2e-gallery.mjs
 *   open http://localhost:9323
 */
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = parseInt(process.env.GALLERY_PORT || '9323', 10);
const HOST = process.env.GALLERY_HOST || '127.0.0.1';

const MIME = {
  '.png': 'image/png',
  '.webm': 'video/webm',
  '.mp4': 'video/mp4',
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json',
};

/** @returns {{ rel: string, abs: string, label: string, kind: string }[]} */
function collectArtifacts() {
  const out = [];

  const reportHtml = path.join(ROOT, 'test-results', 'lifecycle-report', 'syntropia', 'index.html');
  if (fs.existsSync(reportHtml)) {
    out.push({
      rel: 'test-results/lifecycle-report/syntropia/index.html',
      abs: reportHtml,
      label: 'Full lifecycle report (open this)',
      kind: 'report',
    });
  }

  const uiDir = path.join(ROOT, 'test-results', 'ui');
  if (fs.existsSync(uiDir)) {
    for (const codex of fs.readdirSync(uiDir)) {
      const dir = path.join(uiDir, codex);
      if (!fs.statSync(dir).isDirectory()) continue;
      for (const file of fs.readdirSync(dir)) {
        if (!/\.(png|webm)$/.test(file)) continue;
        const rel = path.join('test-results', 'ui', codex, file);
        out.push({ rel, abs: path.join(ROOT, rel), label: `${codex} · ${file}`, kind: 'media' });
      }
    }
  }

  const tr = path.join(ROOT, 'test-results');
  if (fs.existsSync(tr)) {
    for (const entry of fs.readdirSync(tr)) {
      const dir = path.join(tr, entry);
      if (!fs.statSync(dir).isDirectory()) continue;
      for (const file of ['test-finished-1.png', 'test-failed-1.png', 'video.webm']) {
        const abs = path.join(dir, file);
        if (!fs.existsSync(abs)) continue;
        const rel = path.join('test-results', entry, file);
        out.push({ rel, abs, label: `${entry} · ${file}`, kind: 'media' });
      }
    }
  }

  return out.sort((a, b) => a.label.localeCompare(b.label));
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function htmlPage(artifacts) {
  const report = artifacts.find((a) => a.kind === 'report');
  const items = artifacts
    .filter((a) => a.kind !== 'report')
    .map((a) => {
      const href = `/${a.rel.split(path.sep).join('/')}`;
      if (a.rel.endsWith('.webm')) {
        return `<figure><figcaption>${escapeHtml(a.label)}</figcaption><video controls src="${href}" style="max-width:100%"></video></figure>`;
      }
      if (a.rel.endsWith('.png')) {
        return `<figure><figcaption>${escapeHtml(a.label)}</figcaption><a href="${href}"><img src="${href}" alt="" loading="lazy"/></a></figure>`;
      }
      return '';
    })
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>E2E artifacts</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#0f172a;color:#e2e8f0}
  .banner{background:#1e293b;padding:1rem;border-radius:8px;margin-bottom:2rem}
  .banner a{color:#38bdf8;font-weight:600;font-size:1.1rem}
  figure{background:#1e293b;border-radius:8px;margin:0 0 2rem;padding:1rem}
  img,video{max-width:100%;border-radius:4px;border:1px solid #334155}
</style></head><body>
<h1>E2E lifecycle artifacts</h1>
${report ? `<p class="banner">📋 <a href="/${report.rel}">Open the full lifecycle report</a> — narratives, API evidence, all screenshots &amp; videos per phase.</p>` : ''}
<p>${artifacts.length} file(s) · tunnel: <code>ssh -L ${PORT}:127.0.0.1:${PORT} srv1.pzjj.org</code></p>
${items || '<p>No artifacts yet.</p>'}
</body></html>`;
}

const artifacts = collectArtifacts();

const server = http.createServer((req, res) => {
  const url = decodeURIComponent((req.url || '/').split('?')[0]);
  if (url === '/' || url === '/index.html') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(htmlPage(artifacts));
    return;
  }

  const rel = url.replace(/^\//, '');
  const abs = path.resolve(ROOT, rel);
  if (!abs.startsWith(ROOT) || !fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
    res.writeHead(404);
    res.end('Not found');
    return;
  }

  const ext = path.extname(abs);
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
  fs.createReadStream(abs).pipe(res);
});

server.listen(PORT, HOST, () => {
  console.log(`E2E gallery: http://${HOST}:${PORT}/`);
  const report = artifacts.find((a) => a.kind === 'report');
  if (report) console.log(`Full report: http://${HOST}:${PORT}/${report.rel}`);
  console.log(`Tunnel: ssh -L ${PORT}:127.0.0.1:${PORT} srv1.pzjj.org`);
});
