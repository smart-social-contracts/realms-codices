#!/usr/bin/env node
/**
 * Build the browsable test-results site served at https://srv1.pzjj.org/test-results/
 *
 * Regenerates lifecycle HTML reports and writes test-results/index.html.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { generateLifecycleReport } from './generate-lifecycle-report.mjs';
import { phasesForCodex } from './lifecycle-phases.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'test-results');

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function readJson(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function discoverSuites() {
  const suites = [];
  const reportDir = path.join(OUT, 'lifecycle-report');
  if (fs.existsSync(reportDir)) {
    for (const codex of fs.readdirSync(reportDir)) {
      const index = path.join(reportDir, codex, 'index.html');
      if (!fs.existsSync(index)) continue;
      const json = readJson(path.join(OUT, `${codex}-lifecycle-report.json`));
      const phases = phasesForCodex(codex);
      const runs = json?.testRuns || {};
      const passed = Object.values(runs).filter((r) => r.status === 'passed').length;
      const failed = Object.values(runs).filter((r) => r.status === 'failed').length;
      suites.push({
        id: `${codex}-lifecycle`,
        codex,
        title: `${codex.charAt(0).toUpperCase() + codex.slice(1)} lifecycle (alpha → beta → production)`,
        href: `lifecycle-report/${codex}/index.html`,
        passed,
        failed,
        total: phases.length,
        backendId: json?.backendId || json?.params?.backendId || '',
        startedAt: json?.startedAt || '',
      });
    }
  }

  // Playwright HTML report if present
  const pwReport = path.join(ROOT, 'playwright-report', 'index.html');
  if (fs.existsSync(pwReport)) {
    suites.push({
      id: 'playwright-html',
      codex: 'playwright',
      title: 'Playwright raw HTML report',
      href: '../playwright-report/index.html',
      passed: null,
      failed: null,
      total: null,
      note: 'Machine-oriented report with traces; lifecycle reports above are human-readable.',
    });
  }

  return suites;
}

function phaseCards(codex) {
  const json = readJson(path.join(OUT, `${codex}-lifecycle-report.json`));
  const phases = phasesForCodex(codex);
  return phases
    .map((p) => {
      const run = json?.testRuns?.[p.id];
      const status = run?.status || 'not run';
      const cls = status === 'passed' ? 'pass' : status === 'failed' ? 'fail' : 'skip';
      return `<a class="phase-card ${cls}" href="lifecycle-report/${codex}/index.html#${p.id.toLowerCase()}">
  <span class="pid">${escapeHtml(p.id)}</span>
  <span class="ptitle">${escapeHtml(p.title)}</span>
  <span class="pstatus">${escapeHtml(status)}</span>
</a>`;
    })
    .join('\n');
}

export function buildTestResultsSite() {
  return buildIndex();
}

function buildIndex() {
  for (const codex of ['syntropia', 'agora']) {
    const jsonPath = path.join(OUT, `${codex}-lifecycle-report.json`);
    if (fs.existsSync(jsonPath) || fs.existsSync(path.join(OUT, 'lifecycle-report', codex))) {
      generateLifecycleReport({ codex });
    }
  }

  const suites = discoverSuites();

  const suiteBlocks = suites
    .map((s) => {
      const stats =
        s.total != null
          ? `<span class="stat pass">${s.passed} passed</span> <span class="stat fail">${s.failed} failed</span> <span class="stat">${s.total} phases</span>`
          : '';
      const phases =
        s.codex === 'syntropia' || s.codex === 'agora'
          ? `<div class="phase-grid">${phaseCards(s.codex)}</div>`
          : '';
      return `<section class="suite">
  <h2><a href="${escapeHtml(s.href)}">${escapeHtml(s.title)}</a></h2>
  ${s.backendId ? `<p class="meta">Backend <code>${escapeHtml(s.backendId)}</code>${s.startedAt ? ` · started ${escapeHtml(s.startedAt)}` : ''}</p>` : ''}
  ${s.note ? `<p class="meta">${escapeHtml(s.note)}</p>` : ''}
  <p>${stats} <a class="open-report" href="${escapeHtml(s.href)}">Open full report →</a></p>
  ${phases}
</section>`;
    })
    .join('\n');

  const html = `<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Realms E2E test results</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8; --pass:#4ade80; --fail:#f87171; }
  body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.5; }
  .wrap { max-width: 960px; margin: 0 auto; padding: 2rem 1rem 4rem; }
  h1 { margin: 0 0 0.25rem; font-size: 1.5rem; }
  .lead { color: var(--muted); margin-bottom: 2rem; }
  .suite { background: var(--card); border-radius: 10px; padding: 1.25rem; margin-bottom: 2rem; }
  .suite h2 { margin: 0 0 0.5rem; font-size: 1.15rem; }
  .suite h2 a { color: var(--text); text-decoration: none; }
  .suite h2 a:hover { color: var(--accent); }
  .meta { color: var(--muted); font-size: 0.85rem; margin: 0.25rem 0; }
  .meta code { background: #0b1220; padding: 0.1rem 0.3rem; border-radius: 4px; }
  .stat { font-size: 0.85rem; margin-right: 0.75rem; }
  .stat.pass { color: var(--pass); }
  .stat.fail { color: var(--fail); }
  .open-report { color: var(--accent); font-size: 0.9rem; }
  .phase-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.75rem; margin-top: 1rem; }
  .phase-card { display: block; background: #0b1220; border-radius: 8px; padding: 0.75rem; text-decoration: none; color: inherit; border-left: 3px solid var(--muted); }
  .phase-card:hover { background: #111827; }
  .phase-card.pass { border-left-color: var(--pass); }
  .phase-card.fail { border-left-color: var(--fail); }
  .phase-card.skip { border-left-color: #64748b; opacity: 0.85; }
  .pid { font-weight: 700; display: block; }
  .ptitle { font-size: 0.85rem; color: var(--muted); display: block; margin: 0.25rem 0; }
  .pstatus { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
</style>
</head><body>
<div class="wrap">
  <h1>Realms E2E test results</h1>
  <p class="lead">Pick a suite, then a phase — each phase has explanations, API evidence, screenshots, and screen recordings.</p>
  ${suiteBlocks || '<p>No lifecycle reports yet. Run <code>LIFECYCLE_E2E=1 npm run test:syntropia-lifecycle</code> then <code>npm run build:test-site</code>.</p>'}
</div>
</body></html>`;

  fs.writeFileSync(path.join(OUT, 'index.html'), html);
  console.log(`Test results index: ${path.join(OUT, 'index.html')}`);
  return suites.length;
}

const n = buildTestResultsSite();
console.log(`${n} suite(s) indexed`);
