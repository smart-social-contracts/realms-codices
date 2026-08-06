/**
 * Browser UI checkpoint screenshots for lifecycle E2E suites.
 *
 * Uses the staging portal + II bypass (fresh Playwright contexts inherit
 * the realm's test_mode_ii_bypass join flow). Screenshots land under
 * test-results/ui/<codex>/.
 */
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'https://staging.gos.earth';

export function realmBaseUrl() {
  const realmPath = (process.env.REALM_PATH || '').trim();
  if (realmPath) {
    return `${BASE_URL}${realmPath.startsWith('/') ? realmPath : `/${realmPath}`}`;
  }
  const frontendId = (process.env.REALM_FRONTEND_ID || '').trim();
  if (frontendId) {
    return `https://${frontendId}.icp0.io`;
  }
  return '';
}

export function uiShotDir(codex) {
  const dir = path.join('test-results', 'ui', codex);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {string} codex
 * @param {string} name  filename without extension
 */
export async function capture(page, codex, name, { fullPage = true } = {}) {
  const dir = uiShotDir(codex);
  const file = path.join(dir, `${name}.png`);
  await page.screenshot({ path: file, fullPage });
  return file;
}

/** Open a realm extension route and wait for load errors to settle. */
export async function openExtension(page, extPath, { timeout = 90_000 } = {}) {
  const base = realmBaseUrl();
  if (!base) {
    console.warn('ui-checkpoints: REALM_PATH not set — skipping browser navigation');
    return false;
  }
  const url = `${base}/extensions/${extPath.replace(/^\//, '')}`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
  await page.waitForTimeout(4000);
  const err = page
    .getByText(/Extension .* not found/i)
    .or(page.getByText(/failed to load/i))
    .or(page.getByText(/Unexpected token/i));
  if (await err.first().isVisible().catch(() => false)) {
    throw new Error(`Extension load error at ${url}`);
  }
  return true;
}

/** Join via II bypass (founder/admin shortcut when still in alpha). */
export async function joinViaBypass(page, inviteCode = 'admin') {
  const base = realmBaseUrl();
  if (!base) return false;
  await page.goto(`${base}/join`, { waitUntil: 'domcontentloaded', timeout: 120_000 });
  await page.waitForTimeout(2000);

  const inviteInput = page.locator('#invite-code');
  if (await inviteInput.isVisible().catch(() => false)) {
    await inviteInput.fill(inviteCode);
    const validateBtn = page.getByRole('button', { name: /Validate|Apply/i });
    if (await validateBtn.isVisible().catch(() => false)) {
      await validateBtn.click();
      await page.waitForTimeout(1500);
    }
    const joinBtn = page.getByRole('button', { name: /Join Realm/i });
    if (await joinBtn.isEnabled().catch(() => false)) {
      await joinBtn.click();
    }
  }

  await page.waitForTimeout(3000);
  return true;
}

/** Screenshot wizard codex parameters panel (Syntropia / Agora). */
export async function screenshotWizardCodex(page, codex, { showAdvanced = false, name } = {}) {
  await page.goto(`${BASE_URL}/create-realm`, {
    waitUntil: 'domcontentloaded',
    timeout: 120_000,
  });
  await page.waitForTimeout(3000);

  const label = codex === 'agora' ? 'Agora' : 'Syntropia';
  const card = page.getByText(label, { exact: true }).first();
  await card.waitFor({ state: 'visible', timeout: 60_000 });
  await card.click();

  // Manifest fetch from the file registry can be slow on cold start.
  await page.waitForTimeout(5000);
  const details = page
    .locator("text=What's included")
    .or(page.locator('text=Parameters'))
    .or(page.locator('.codex-manifest-details'));
  await details.first().waitFor({ state: 'visible', timeout: 120_000 });

  if (showAdvanced) {
    const adv = page.getByRole('button', {
      name: /Show advanced parameters/i,
    });
    if (await adv.isVisible().catch(() => false)) {
      await adv.click();
      await page.waitForTimeout(500);
    }
  }

  return capture(page, codex, name || '00-wizard-codex-parameters');
}

async function expectVisible(page, pattern, timeout) {
  await page.getByText(pattern).first().waitFor({ state: 'visible', timeout });
}

/** Standard lifecycle UI checkpoint bundle. */
export async function lifecycleUiCheckpoint(page, codex, phase, opts = {}) {
  const base = realmBaseUrl();
  if (!base) {
    console.warn(`ui-checkpoints: skip ${phase} — no REALM_PATH`);
    return null;
  }

  if (opts.join !== false) {
    await joinViaBypass(page, opts.inviteCode ?? 'admin');
  }

  if (opts.extension) {
    await openExtension(page, opts.extension);
  }

  return capture(page, codex, phase, { fullPage: opts.fullPage !== false });
}

/**
 * Capture multiple UI screenshots for one lifecycle phase.
 * @param {import('@playwright/test').Page} page
 * @param {string} codex
 * @param {{ extension: string, name: string, join?: boolean, inviteCode?: string }[]} shots
 */
export async function capturePhaseShots(page, codex, shots, { joinFirst = true, inviteCode = 'admin' } = {}) {
  const files = [];
  if (!realmBaseUrl()) return files;
  if (joinFirst) {
    await joinViaBypass(page, inviteCode);
  }
  for (const shot of shots) {
    if (shot.join) {
      await joinViaBypass(page, shot.inviteCode ?? inviteCode);
    }
    await openExtension(page, shot.extension);
    files.push(await capture(page, codex, shot.name, { fullPage: shot.fullPage !== false }));
  }
  return files;
}
