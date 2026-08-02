#!/usr/bin/env node
/**
 * cohort-runner.mjs — Mass browser-cohort runner for realm E2E testing.
 *
 * Spins up N isolated browser contexts, each logged in through the real join
 * UI with its own deterministic test identity (II-bypass test mode), and runs a
 * journey matrix mapped to my-manual-E2E-test-checklist.md.
 *
 * This is Layer 2 of the mass-E2E architecture (cursor_realm_mass_e2e_design.md):
 * a *sampled* cohort through the real frontend while geister's swarm_pool
 * (Layer 1) bulk-populates the realm via canister calls.
 *
 * Usage
 * -----
 *   node cohort/cohort-runner.mjs \
 *     --base-url https://<realm-frontend>.icp0.io \
 *     --members 40 --concurrency 4 \
 *     [--journey join-member,member-vault] [--shard 1/3] [--headful]
 *
 * Artifacts land in cohort-artifacts/<run-id>/ (report.json, screenshots,
 * traces for failures). Exit code is non-zero if any slot failed.
 */

import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JOURNEYS, buildCohortPlan } from './journeys.mjs';
import { trackConsoleErrors } from './cohort-lib.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const args = {
    baseUrl: process.env.PLAYWRIGHT_BASE_URL || 'https://staging.realmsgos.org',
    members: 40,
    concurrency: 4,
    indexBase: 10_000,
    journey: '',
    runId: `run_${new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)}`,
    artifacts: '',
    headful: false,
    shard: '',
    help: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const [key, val] = argv[i].replace(/^--/, '').split('=');
    const next = () => argv[++i];
    switch (key) {
      case 'base-url': args.baseUrl = val ?? next(); break;
      case 'members': args.members = Number(val ?? next()); break;
      case 'concurrency': args.concurrency = Number(val ?? next()); break;
      case 'index-base': args.indexBase = Number(val ?? next()); break;
      case 'journey': args.journey = val ?? next(); break;
      case 'run-id': args.runId = val ?? next(); break;
      case 'artifacts': args.artifacts = val ?? next(); break;
      case 'headful': args.headful = true; break;
      case 'shard': args.shard = val ?? next(); break;
      case 'help': args.help = true; break;
      default: throw new Error(`unknown flag --${key}`);
    }
  }
  if (!args.artifacts) args.artifacts = path.join(__dirname, 'cohort-artifacts', args.runId);
  args.baseUrl = args.baseUrl.replace(/\/$/, '');
  return args;
}

function applyShard(plan, shard) {
  if (!shard) return plan;
  const m = shard.match(/^(\d+)\/(\d+)$/);
  if (!m) throw new Error('--shard must look like 1/3');
  const [, idx, count] = m.map(Number);
  return plan.filter((_, i) => i % count === idx - 1);
}

async function runSlot(browser, slot, args, artifactsDir) {
  const journey = JOURNEYS[slot.journey];
  const startedAt = Date.now();
  const ctx = {
    baseUrl: args.baseUrl,
    index: slot.index,
    role: journey.role,
    runId: args.runId,
    principal: '',
    consoleErrors: [],
  };
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();
  trackConsoleErrors(page, ctx);

  const outcome = { slot: slot.index, journey: slot.journey, role: journey.role, checklist: journey.checklist };
  try {
    await journey.fn(page, ctx);
    outcome.ok = true;
    outcome.principal = ctx.principal;
    const shot = path.join(artifactsDir, 'screenshots', `${slot.index}-${slot.journey}.png`);
    await page.screenshot({ path: shot, fullPage: true }).catch(() => {});
    await context.tracing.stop(); // discard trace on success
  } catch (err) {
    outcome.ok = false;
    outcome.error = String(err?.message || err).slice(0, 500);
    outcome.principal = ctx.principal || undefined;
    const shot = path.join(artifactsDir, 'screenshots', `FAIL-${slot.index}-${slot.journey}.png`);
    await page.screenshot({ path: shot, fullPage: true }).catch(() => {});
    const trace = path.join(artifactsDir, 'traces', `${slot.index}-${slot.journey}.zip`);
    await context.tracing.stop({ path: trace }).catch(() => {});
    outcome.trace = trace;
  } finally {
    outcome.durationMs = Date.now() - startedAt;
    if (ctx.consoleErrors.length) outcome.consoleErrors = ctx.consoleErrors.slice(0, 20);
    await context.close().catch(() => {});
  }
  return outcome;
}

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    console.log('node cohort/cohort-runner.mjs --base-url <url> [--members 40] [--concurrency 4]');
    console.log('  [--journey a,b] [--shard 1/3] [--run-id slug] [--index-base 10000] [--artifacts dir] [--headful]');
    console.log('\nJourneys:', Object.keys(JOURNEYS).join(', '));
    return 0;
  }

  const only = args.journey ? args.journey.split(',').map((s) => s.trim()) : [];
  const unknown = only.filter((j) => !JOURNEYS[j]);
  if (unknown.length) throw new Error(`unknown journeys: ${unknown.join(', ')}`);

  let plan = buildCohortPlan(args.members, { only, indexBase: args.indexBase });
  plan = applyShard(plan, args.shard);
  if (!plan.length) throw new Error('empty cohort plan (check --journey/--shard)');

  const artifactsDir = args.artifacts;
  await mkdir(path.join(artifactsDir, 'screenshots'), { recursive: true });
  await mkdir(path.join(artifactsDir, 'traces'), { recursive: true });

  console.log(`[cohort] run_id=${args.runId} base=${args.baseUrl}`);
  console.log(`[cohort] ${plan.length} slots, concurrency=${args.concurrency}`);
  console.log(`[cohort] artifacts → ${artifactsDir}`);

  const browser = await chromium.launch({ headless: !args.headful });
  const outcomes = [];
  let cursor = 0;

  async function worker(id) {
    while (cursor < plan.length) {
      const slot = plan[cursor++];
      const tag = `[#${slot.index} ${slot.journey}]`;
      try {
        const outcome = await runSlot(browser, slot, args, artifactsDir);
        outcomes.push(outcome);
        console.log(`${outcome.ok ? '✓' : '✗'} ${tag} ${outcome.ok ? '' : outcome.error} (${(outcome.durationMs / 1000).toFixed(1)}s)`);
      } catch (err) {
        outcomes.push({ slot: slot.index, journey: slot.journey, ok: false, error: String(err) });
        console.log(`✗ ${tag} runner error: ${err}`);
      }
    }
  }

  const t0 = Date.now();
  await Promise.all(Array.from({ length: Math.min(args.concurrency, plan.length) }, (_, i) => worker(i)));
  await browser.close();

  const failed = outcomes.filter((o) => !o.ok);
  const report = {
    run_id: args.runId,
    base_url: args.baseUrl,
    started_slots: outcomes.length,
    passed: outcomes.length - failed.length,
    failed: failed.length,
    duration_s: Math.round((Date.now() - t0) / 1000),
    outcomes: outcomes.sort((a, b) => a.slot - b.slot),
  };
  await writeFile(path.join(artifactsDir, 'report.json'), JSON.stringify(report, null, 2));

  console.log('\n' + '='.repeat(60));
  console.log(`COHORT REPORT  ${report.passed}/${outcomes.length} passed in ${report.duration_s}s`);
  for (const f of failed) console.log(`  ✗ #${f.slot} ${f.journey}: ${(f.error || '').slice(0, 120)}`);
  console.log('='.repeat(60));
  return failed.length ? 1 : 0;
}

main().then((code) => process.exit(code)).catch((err) => {
  console.error('[cohort] fatal:', err);
  process.exit(2);
});
