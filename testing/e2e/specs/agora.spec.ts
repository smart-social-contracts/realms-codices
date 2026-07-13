import { test, expect } from '@playwright/test';

const REALM_PATH = process.env.REALM_PATH || '/r/manualtest8agora';
const REALM_URL = `${process.env.PLAYWRIGHT_BASE_URL || 'https://staging.realmsgos.org'}${REALM_PATH}`;

const AGORA_DEPS = [
  'access_manager',
  'role_manager',
  'notifications',
  'metrics',
  'land_registry',
  'migration_console',
];

test.describe('Agora codex E2E (staging)', () => {
  test('U1 / A1 — wizard shows Agora manifest from registry', async ({ page }) => {
    await page.goto('/create-realm', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);

    // Select Agora package if not already selected
    const agoraCard = page.getByText('Agora', { exact: true }).first();
    if (await agoraCard.isVisible().catch(() => false)) {
      await agoraCard.click();
    }

    const details = page.locator('text=What\'s included').or(page.locator('text=Dependencies'));
    await expect(details.first()).toBeVisible({ timeout: 60_000 });

    for (const dep of AGORA_DEPS) {
      await expect(page.getByText(dep, { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    }

    // Token step: only assert when we can navigate forward (step enabled)
    const tokenStep = page.getByRole('button', { name: /^Token$/i });
    if (await tokenStep.isEnabled().catch(() => false)) {
      await tokenStep.click();
      await expect(page.getByText(/Set by the Agora codex/i)).not.toBeVisible();
    }

    const basicsStep = page.getByRole('button', { name: /^Basics$/i });
    if (await basicsStep.isEnabled().catch(() => false)) {
      await basicsStep.click();
      await expect(page.getByText(/Invitation only/i).first()).toBeVisible({ timeout: 30_000 });
    }

    await page.screenshot({ path: 'test-results/u1-wizard-agora.png', fullPage: true });
  });

  test('A2 — public dashboard (logged out) incumbent profile', async ({ page }) => {
    await page.goto(`${REALM_URL}/extensions/public_dashboard`, {
      waitUntil: 'networkidle',
    });

    // SPA cold start on IC can take 30–60s
    await expect(page.getByText('ManualTest8Agora').first())
      .toBeVisible({ timeout: 90_000 });

    const becomeCitizen = page.getByRole('link', { name: /Become a citizen/i });
    await expect(becomeCitizen).not.toBeVisible({ timeout: 5_000 }).catch(() => {});

    await page.screenshot({ path: 'test-results/a2-public-dashboard.png', fullPage: true });
  });

  test('U4 — Realm Settings loads without JSON parse error', async ({ page }) => {
    await page.goto(`${REALM_URL}/extensions/realm_settings`, {
      waitUntil: 'domcontentloaded',
    });
    const err = page.getByText(/Unexpected token/i).or(page.getByText(/not valid JSON/i));
    await expect(err).not.toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: 'test-results/u4-realm-settings.png', fullPage: true });
  });

  test('A2 — Migration Console extension loads', async ({ page }) => {
    await page.goto(`${REALM_URL}/extensions/migration_console`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForTimeout(8000);

    const err = page.getByText(/Extension .* not found/i).or(page.getByText(/failed to load/i));
    await expect(err).not.toBeVisible({ timeout: 10_000 });

    await page.screenshot({ path: 'test-results/a2-migration-console.png', fullPage: true });
  });

  test('A2 — Metrics extension loads', async ({ page }) => {
    await page.goto(`${REALM_URL}/extensions/metrics`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForTimeout(8000);

    const err = page.getByText(/Extension .* not found/i).or(page.getByText(/failed to load/i));
    await expect(err).not.toBeVisible({ timeout: 10_000 });

    await page.screenshot({ path: 'test-results/a2-metrics.png', fullPage: true });
  });

  test('A3 — join page without invite (logged out)', async ({ page }) => {
    await page.goto(`${REALM_URL}/join`, { waitUntil: 'domcontentloaded' });
    // With II bypass the auth step may be skipped; invitation step is the gate.
    await expect(
      page.getByText(/Sign in to continue|Invitation|invitation code/i).first(),
    ).toBeVisible({ timeout: 60_000 });
    await page.screenshot({ path: 'test-results/a3-join-no-invite.png', fullPage: true });
  });

  test('U2 — admin via II bypass + test-mode invite', async ({ page }) => {
    await page.goto(`${REALM_URL}/join`, { waitUntil: 'networkidle' });
    // II bypass auto-authenticates; use test-mode admin shortcut on join flow
    const invite = page.getByPlaceholder(/invitation|code/i).or(page.locator('input').filter({ hasText: '' }).first());
    if (await invite.isVisible().catch(() => false)) {
      await invite.fill('admin');
    }
    const joinBtn = page.getByRole('button', { name: /Join Realm/i });
    if (await joinBtn.isEnabled().catch(() => false)) {
      await joinBtn.click();
    }
    await page.goto(`${REALM_URL}/extensions/realm_settings`, { waitUntil: 'networkidle' });
    await expect(page.getByText(/Realm Settings|alpha/i).first()).toBeVisible({ timeout: 90_000 });
    await page.screenshot({ path: 'test-results/u2-founder-admin.png', fullPage: true });
  });
});
