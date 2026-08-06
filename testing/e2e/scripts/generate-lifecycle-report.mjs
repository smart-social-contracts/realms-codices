#!/usr/bin/env node
/**
 * Build a self-contained HTML lifecycle report from JSON evidence, UI
 * screenshots, Playwright per-test videos, and phase narratives.
 *
 * Output: test-results/lifecycle-report/<codex>/index.html + assets/
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { phasesForCodex } from './lifecycle-phases.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function readJson(file) {
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/** @returns {Map<string, object>} phaseId -> run metadata */
function collectPlaywrightRuns(codex) {
  const runs = new Map();
  const tr = path.join(ROOT, 'test-results');
  if (!fs.existsSync(tr)) return runs;

  const prefix = `${codex}-lifecycle`;
  for (const entry of fs.readdirSync(tr)) {
    if (!entry.startsWith(prefix) || !entry.endsWith('-chromium')) continue;
    const dir = path.join(tr, entry);
    if (!fs.statSync(dir).isDirectory()) continue;

    // Match P0 — wizard … from folder slug
    const phaseMatch = entry.match(/P(\d+)|wizard|founder|parameterize|blocked|citizens|staff|zones|procurement|handover|Congress|identity|tax|production/i);
    let phaseId = null;
    const titleHints = [
      ['wizard', 'P0'],
      ['founder', 'P1'],
      ['parameterize', 'P2'],
      ['blocked', 'P3'],
      ['citizens', 'P4'],
      ['staff', 'P5'],
      ['zones', 'P6'],
      ['procurement', 'P7'],
      ['handover', 'P8'],
      ['beta', 'P9'],
      ['identity', 'P10'],
      ['tax', 'P11'],
      ['production', 'P12'],
    ];
    for (const [hint, id] of titleHints) {
      if (entry.toLowerCase().includes(hint)) {
        phaseId = id;
        break;
      }
    }

    const video = ['video.webm', 'video.mp4']
      .map((f) => path.join(dir, f))
      .find((p) => fs.existsSync(p));
    const screenshot = ['test-finished-1.png', 'test-failed-1.png']
      .map((f) => path.join(dir, f))
      .find((p) => fs.existsSync(p));

    if (phaseId) {
      runs.set(phaseId, { dir: entry, video, screenshot });
    }
  }
  return runs;
}

function copyAsset(src, destDir, destName) {
  if (!src || !fs.existsSync(src)) return null;
  fs.mkdirSync(destDir, { recursive: true });
  const ext = path.extname(src);
  const base = destName || path.basename(src, ext);
  const dest = path.join(destDir, `${base}${ext}`);
  fs.copyFileSync(src, dest);
  return path.relative(path.join(ROOT, 'test-results', 'lifecycle-report'), dest).split(path.sep).join('/');
}

function formatJson(obj) {
  return escapeHtml(JSON.stringify(obj, null, 2));
}

function phaseEvidence(report, phaseMeta) {
  const keys = {
    P1: ['preflight', 'founder_admin'],
    P2: ['configure_gates'],
    P3: ['beta_blocked'],
    P4: ['bulk_join', 'member_invite'],
    P5: ['staffing'],
    P6: ['zones'],
    P7: ['procurement'],
    P8: ['root_transfer', 'creator_demoted'],
    P9: ['beta_history', 'beta_effects'],
    P10: ['identity_submissions'],
    P11: ['payment'],
    P12: ['production_blocked'],
  };
  const out = {};
  for (const k of keys[phaseMeta.id] || []) {
    if (report.phases?.[k]) out[k] = report.phases[k];
  }
  return out;
}

export function generateLifecycleReport({
  codex = 'syntropia',
  outDir = path.join('test-results', 'lifecycle-report', codex),
  testRuns = {},
} = {}) {
  const phases = phasesForCodex(codex);
  const reportFile = path.join(ROOT, 'test-results', `${codex}-lifecycle-report.json`);
  const report = readJson(reportFile) || { codex, phases: {}, params: {} };
  const pwRuns = collectPlaywrightRuns(codex);

  const assetsDir = path.join(ROOT, outDir, 'assets');
  fs.mkdirSync(assetsDir, { recursive: true });

  const realmPath = process.env.REALM_PATH || '';
  const realmUrl = realmPath
    ? `${process.env.PLAYWRIGHT_BASE_URL || 'https://staging.gos.earth'}${realmPath.startsWith('/') ? realmPath : `/${realmPath}`}`
    : '';

  const mergedRuns = { ...Object.fromEntries(pwRuns), ...testRuns };

  const phaseSections = phases.map((phase) => {
    const uiDir = path.join(ROOT, 'test-results', 'ui', codex);
    const shots = [];
    for (const name of phase.uiShots || []) {
      const src = path.join(uiDir, `${name}.png`);
      const rel = copyAsset(src, assetsDir, `${phase.id}-${name}`);
      if (rel) shots.push({ label: name, src: rel });
    }

    const run = mergedRuns[phase.id] || {};
    let videoRel = null;
    if (run.video) {
      videoRel = copyAsset(run.video, assetsDir, `${phase.id}-recording`);
    } else {
      const pw = pwRuns.get(phase.id);
      if (pw?.video) videoRel = copyAsset(pw.video, assetsDir, `${phase.id}-recording`);
    }

    let autoShot = null;
    const pw = pwRuns.get(phase.id);
    if (pw?.screenshot) {
      autoShot = copyAsset(pw.screenshot, assetsDir, `${phase.id}-auto-screenshot`);
    }

    const evidence = phaseEvidence(report, phase);
    const runMeta = report.testRuns?.[phase.id];
    const status = runMeta?.status || (Object.keys(evidence).length ? 'passed' : '—');
    const durationMs = runMeta?.duration;

    const actionsHtml = phase.actions
      .map((a) => `<li>${escapeHtml(a)}</li>`)
      .join('');
    const checklistHtml = phase.checklist
      .map((c) => `<li>${escapeHtml(c)}</li>`)
      .join('');

    const shotsHtml = shots
      .map(
        (s) =>
          `<figure><figcaption>${escapeHtml(s.label)}</figcaption><img src="assets/${escapeHtml(path.basename(s.src))}" alt="" loading="lazy"/></figure>`,
      )
      .join('\n');

    const autoShotHtml = autoShot
      ? `<figure><figcaption>Playwright end-of-test screenshot</figcaption><img src="assets/${escapeHtml(path.basename(autoShot))}" alt="" loading="lazy"/></figure>`
      : '';

    const videoHtml = videoRel
      ? `<figure class="video"><figcaption>Screen recording (${phase.id})</figcaption><video controls preload="metadata" src="assets/${escapeHtml(path.basename(videoRel))}"></video></figure>`
      : '';

    const evidenceHtml =
      Object.keys(evidence).length > 0
        ? `<details open><summary>API / backend evidence</summary><pre>${formatJson(evidence)}</pre></details>`
        : '';

    return `<section id="${phase.id.toLowerCase()}" class="phase ${status === 'passed' ? 'pass' : status === 'failed' ? 'fail' : ''}">
  <header>
    <h2>${escapeHtml(phase.id)} — ${escapeHtml(phase.title)}</h2>
    <p class="status">${escapeHtml(String(status))}${durationMs ? ` · ${(durationMs / 1000).toFixed(1)}s` : ''}</p>
  </header>
  <p class="summary">${escapeHtml(phase.summary)}</p>
  <div class="cols">
    <div><h3>What we did</h3><ul>${actionsHtml}</ul></div>
    <div><h3>Checklist</h3><ul>${checklistHtml}</ul></div>
  </div>
  ${evidenceHtml}
  <div class="media">${videoHtml}${shotsHtml}${autoShotHtml}</div>
</section>`;
  });

  const passed = Object.values(report.testRuns || {}).filter((r) => r.status === 'passed').length;
  const total = phases.length;

  const html = `<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${escapeHtml(codex)} lifecycle E2E report</title>
<style>
  :root { --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8; --accent: #38bdf8; --pass: #4ade80; --fail: #f87171; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); margin: 0; line-height: 1.5; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem 4rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.5rem; }
  .meta { color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }
  .meta code { background: var(--card); padding: 0.1rem 0.35rem; border-radius: 4px; }
  nav { background: var(--card); padding: 1rem; border-radius: 8px; margin-bottom: 2rem; }
  nav a { color: var(--accent); margin-right: 1rem; text-decoration: none; font-size: 0.85rem; }
  nav a:hover { text-decoration: underline; }
  .phase { background: var(--card); border-radius: 8px; padding: 1.25rem; margin-bottom: 2rem; border-left: 4px solid var(--muted); }
  .phase.pass { border-left-color: var(--pass); }
  .phase.fail { border-left-color: var(--fail); }
  .phase h2 { margin: 0 0 0.25rem; font-size: 1.1rem; }
  .status { color: var(--muted); font-size: 0.85rem; margin: 0 0 1rem; text-transform: uppercase; letter-spacing: 0.04em; }
  .summary { margin: 0 0 1rem; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
  @media (max-width: 700px) { .cols { grid-template-columns: 1fr; } }
  h3 { font-size: 0.85rem; text-transform: uppercase; color: var(--muted); margin: 0 0 0.5rem; }
  ul { margin: 0; padding-left: 1.2rem; font-size: 0.92rem; }
  details { margin: 1rem 0; }
  pre { background: #0b1220; padding: 0.75rem; border-radius: 6px; overflow: auto; font-size: 0.75rem; max-height: 280px; }
  figure { margin: 1rem 0 0; }
  figcaption { font-weight: 600; font-size: 0.85rem; margin-bottom: 0.5rem; }
  img { max-width: 100%; border-radius: 6px; border: 1px solid #334155; }
  video { max-width: 100%; border-radius: 6px; border: 1px solid #334155; background: #000; }
  .video video { width: 100%; }
  table.params { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 1rem 0; }
  table.params th, table.params td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid #334155; }
</style>
</head><body>
<div class="wrap">
  <h1>${escapeHtml(codex.charAt(0).toUpperCase() + codex.slice(1))} lifecycle E2E report</h1>
  <p class="meta">
    Generated ${escapeHtml(new Date().toISOString())}<br/>
    <a href="../../index.html" style="color:var(--accent)">← All test results</a><br/>
    Backend: <code>${escapeHtml(report.backendId || report.params?.backendId || '—')}</code>
    ${realmUrl ? `<br/>Realm: <a href="${escapeHtml(realmUrl)}" style="color:var(--accent)">${escapeHtml(realmUrl)}</a>` : ''}
    <br/>Phases passed (instrumented): ${passed}/${total}
  </p>
  <nav>${phases.map((p) => `<a href="#${p.id.toLowerCase()}">${p.id}</a>`).join('')}</nav>
  <table class="params"><tbody>
    ${Object.entries(report.params || {})
      .filter(([k]) => !['backendId'].includes(k))
      .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(String(v))}</td></tr>`)
      .join('')}
  </tbody></table>
  ${phaseSections.join('\n')}
</div>
</body></html>`;

  const outPath = path.join(ROOT, outDir);
  fs.mkdirSync(outPath, { recursive: true });
  const indexFile = path.join(outPath, 'index.html');
  fs.writeFileSync(indexFile, html);
  fs.writeFileSync(path.join(outPath, 'report-data.json'), JSON.stringify({ report, phases: phases.map((p) => p.id) }, null, 2));

  // tarball for download
  return indexFile;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const codex = process.env.CODEX || process.argv[2] || 'syntropia';
  const file = generateLifecycleReport({ codex });
  console.log(`Lifecycle report: ${file}`);
}
