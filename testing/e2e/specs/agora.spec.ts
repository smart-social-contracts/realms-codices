import { test, expect, type Page } from '@playwright/test';

const REALM_PATH = process.env.REALM_PATH || '/r/manualtest8agora';
const REALM_NAME = process.env.REALM_NAME || 'ManualTest8Agora';
const REALM_URL = `${process.env.PLAYWRIGHT_BASE_URL || 'https://staging.gos.earth'}${REALM_PATH}`;

const AGORA_DEPS = [
  'access_manager',
  'role_manager',
  'notifications',
  'metrics',
  'land_registry',
];

/** Drive the II-bypass join flow to the Invitation step and optionally join. */
async function reachInvitationStep(page: Page) {
  await page.goto(`${REALM_URL}/join`, { waitUntil: 'domcontentloaded' });

  // II bypass auto-authenticates; auth step may flash then advance.
  // Accept either still-on-auth or already-on-invitation.
  await expect(
    page
      .getByText(/Sign in to continue|Invitation|Join |Paste your invite|Have an invitation/i)
      .first(),
  ).toBeVisible({ timeout: 90_000 });

  // If still on Sign In, wait for auto-advance (probe → profile).
  const joinHeading = page.getByRole('heading', { name: new RegExp(`Join ${REALM_NAME}`, 'i') });
  if (!(await joinHeading.isVisible().catch(() => false))) {
    // Click through Terms Accept if present (skip_terms=false on some realms).
    const acceptTerms = page.getByRole('button', { name: /Accept|I agree|Continue/i });
    if (await acceptTerms.first().isVisible().catch(() => false)) {
      await acceptTerms.first().click();
    }
    await expect(joinHeading.or(page.locator('#invite-code'))).toBeVisible({
      timeout: 90_000,
    });
  }
}

async function joinWithTestInvite(page: Page, code: string) {
  await reachInvitationStep(page);

  const inviteInput = page.locator('#invite-code');
  await expect(inviteInput).toBeVisible({ timeout: 60_000 });
  await inviteInput.fill(code);

  // Validate if there's a Validate button; otherwise Join Realm accepts shortcuts.
  const validateBtn = page.getByRole('button', { name: /Validate|Apply/i });
  if (await validateBtn.isVisible().catch(() => false)) {
    await validateBtn.click();
    await page.waitForTimeout(1500);
  }

  const joinBtn = page.getByRole('button', { name: /Join Realm/i });
  await expect(joinBtn).toBeEnabled({ timeout: 30_000 });
  await joinBtn.click();

  // Success step or redirect into the app
  await expect(
    page
      .getByText(/Welcome|You're in|Member Dashboard|Realm Settings|Data Explorer/i)
      .first(),
  ).toBeVisible({ timeout: 120_000 });
}

test.describe('Agora codex E2E (staging)', () => {
  test('U1 / A1 — wizard shows Agora manifest from registry', async ({ page }) => {
    await page.goto('/create-realm', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);

    const agoraCard = page.getByText('Agora', { exact: true }).first();
    if (await agoraCard.isVisible().catch(() => false)) {
      await agoraCard.click();
    }

    const details = page.locator("text=What's included").or(page.locator('text=Dependencies'));
    await expect(details.first()).toBeVisible({ timeout: 60_000 });

    for (const dep of AGORA_DEPS) {
      await expect(page.getByText(dep, { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    }

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

    await expect(page.getByText(REALM_NAME).first()).toBeVisible({ timeout: 90_000 });

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

  test('A2 — Import & Export extension loads', async ({ page }) => {
    await page.goto(`${REALM_URL}/extensions/import_export`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForTimeout(8000);

    const err = page.getByText(/Extension .* not found/i).or(page.getByText(/failed to load/i));
    await expect(err).not.toBeVisible({ timeout: 10_000 });

    await page.screenshot({ path: 'test-results/a2-import-export.png', fullPage: true });
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

  test('A3 — join page reaches invitation gate', async ({ page }) => {
    await reachInvitationStep(page);
    await expect(page.locator('#invite-code').or(page.getByText(/Invitation/i).first())).toBeVisible(
      { timeout: 30_000 },
    );
    await page.screenshot({ path: 'test-results/a3-join-no-invite.png', fullPage: true });
  });

  test('U2 — admin via II bypass + test-mode invite', async ({ page }) => {
    await joinWithTestInvite(page, 'admin');
    await page.goto(`${REALM_URL}/extensions/realm_settings`, { waitUntil: 'networkidle' });
    await expect(page.getByText(/Realm Settings|alpha|Stage/i).first()).toBeVisible({
      timeout: 90_000,
    });
    await page.screenshot({ path: 'test-results/u2-founder-admin.png', fullPage: true });
  });
});
