# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: agora.spec.ts >> Agora codex E2E (staging) >> A3 — join page without invite (logged out)
- Location: specs/agora.spec.ts:97:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText(/Sign in to continue/i)
Expected: visible
Timeout: 60000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 60000ms
  - waiting for getByText(/Sign in to continue/i)

```

```yaml
- iframe
- button "AI Assistant"
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | 
  3   | const REALM_PATH = process.env.REALM_PATH || '/r/manualtest8agora';
  4   | const REALM_URL = `${process.env.PLAYWRIGHT_BASE_URL || 'https://staging.realmsgos.org'}${REALM_PATH}`;
  5   | 
  6   | const AGORA_DEPS = [
  7   |   'access_manager',
  8   |   'role_manager',
  9   |   'notifications',
  10  |   'metrics',
  11  |   'land_registry',
  12  |   'migration_console',
  13  | ];
  14  | 
  15  | test.describe('Agora codex E2E (staging)', () => {
  16  |   test('U1 / A1 — wizard shows Agora manifest from registry', async ({ page }) => {
  17  |     await page.goto('/create-realm', { waitUntil: 'domcontentloaded' });
  18  |     await page.waitForTimeout(3000);
  19  | 
  20  |     // Select Agora package if not already selected
  21  |     const agoraCard = page.getByText('Agora', { exact: true }).first();
  22  |     if (await agoraCard.isVisible().catch(() => false)) {
  23  |       await agoraCard.click();
  24  |     }
  25  | 
  26  |     const details = page.locator('text=What\'s included').or(page.locator('text=Dependencies'));
  27  |     await expect(details.first()).toBeVisible({ timeout: 60_000 });
  28  | 
  29  |     for (const dep of AGORA_DEPS) {
  30  |       await expect(page.getByText(dep, { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  31  |     }
  32  | 
  33  |     // Token step: only assert when we can navigate forward (step enabled)
  34  |     const tokenStep = page.getByRole('button', { name: /^Token$/i });
  35  |     if (await tokenStep.isEnabled().catch(() => false)) {
  36  |       await tokenStep.click();
  37  |       await expect(page.getByText(/Set by the Agora codex/i)).not.toBeVisible();
  38  |     }
  39  | 
  40  |     const basicsStep = page.getByRole('button', { name: /^Basics$/i });
  41  |     if (await basicsStep.isEnabled().catch(() => false)) {
  42  |       await basicsStep.click();
  43  |       await expect(page.getByText(/Invitation only/i).first()).toBeVisible({ timeout: 30_000 });
  44  |     }
  45  | 
  46  |     await page.screenshot({ path: 'test-results/u1-wizard-agora.png', fullPage: true });
  47  |   });
  48  | 
  49  |   test('A2 — public dashboard (logged out) incumbent profile', async ({ page }) => {
  50  |     await page.goto(`${REALM_URL}/extensions/public_dashboard`, {
  51  |       waitUntil: 'networkidle',
  52  |     });
  53  | 
  54  |     // SPA cold start on IC can take 30–60s
  55  |     await expect(page.getByRole('heading', { name: /ManualTest8Agora/i }))
  56  |       .toBeVisible({ timeout: 90_000 });
  57  | 
  58  |     const becomeCitizen = page.getByRole('link', { name: /Become a citizen/i });
  59  |     await expect(becomeCitizen).not.toBeVisible({ timeout: 5_000 }).catch(() => {});
  60  | 
  61  |     await page.screenshot({ path: 'test-results/a2-public-dashboard.png', fullPage: true });
  62  |   });
  63  | 
  64  |   test('U4 — Realm Settings loads without JSON parse error', async ({ page }) => {
  65  |     await page.goto(`${REALM_URL}/extensions/realm_settings`, {
  66  |       waitUntil: 'domcontentloaded',
  67  |     });
  68  |     const err = page.getByText(/Unexpected token/i).or(page.getByText(/not valid JSON/i));
  69  |     await expect(err).not.toBeVisible({ timeout: 30_000 });
  70  |     await page.screenshot({ path: 'test-results/u4-realm-settings.png', fullPage: true });
  71  |   });
  72  | 
  73  |   test('A2 — Migration Console extension loads', async ({ page }) => {
  74  |     await page.goto(`${REALM_URL}/extensions/migration_console`, {
  75  |       waitUntil: 'domcontentloaded',
  76  |     });
  77  |     await page.waitForTimeout(8000);
  78  | 
  79  |     const err = page.getByText(/Extension .* not found/i).or(page.getByText(/failed to load/i));
  80  |     await expect(err).not.toBeVisible({ timeout: 10_000 });
  81  | 
  82  |     await page.screenshot({ path: 'test-results/a2-migration-console.png', fullPage: true });
  83  |   });
  84  | 
  85  |   test('A2 — Metrics extension loads', async ({ page }) => {
  86  |     await page.goto(`${REALM_URL}/extensions/metrics`, {
  87  |       waitUntil: 'domcontentloaded',
  88  |     });
  89  |     await page.waitForTimeout(8000);
  90  | 
  91  |     const err = page.getByText(/Extension .* not found/i).or(page.getByText(/failed to load/i));
  92  |     await expect(err).not.toBeVisible({ timeout: 10_000 });
  93  | 
  94  |     await page.screenshot({ path: 'test-results/a2-metrics.png', fullPage: true });
  95  |   });
  96  | 
  97  |   test('A3 — join page without invite (logged out)', async ({ page }) => {
  98  |     await page.goto(`${REALM_URL}/join`, { waitUntil: 'domcontentloaded' });
> 99  |     await expect(page.getByText(/Sign in to continue/i)).toBeVisible({ timeout: 60_000 });
      |                                                          ^ Error: expect(locator).toBeVisible() failed
  100 |     await page.screenshot({ path: 'test-results/a3-join-no-invite.png', fullPage: true });
  101 |   });
  102 | 
  103 |   test('U2 — admin via II bypass + test-mode invite', async ({ page }) => {
  104 |     await page.goto(`${REALM_URL}/join`, { waitUntil: 'networkidle' });
  105 |     // II bypass auto-authenticates; use test-mode admin shortcut on join flow
  106 |     const invite = page.getByPlaceholder(/invitation|code/i).or(page.locator('input').filter({ hasText: '' }).first());
  107 |     if (await invite.isVisible().catch(() => false)) {
  108 |       await invite.fill('admin');
  109 |     }
  110 |     const joinBtn = page.getByRole('button', { name: /Join Realm/i });
  111 |     if (await joinBtn.isEnabled().catch(() => false)) {
  112 |       await joinBtn.click();
  113 |     }
  114 |     await page.goto(`${REALM_URL}/extensions/realm_settings`, { waitUntil: 'networkidle' });
  115 |     await expect(page.getByText(/Realm Settings|alpha/i).first()).toBeVisible({ timeout: 90_000 });
  116 |     await page.screenshot({ path: 'test-results/u2-founder-admin.png', fullPage: true });
  117 |   });
  118 | });
  119 | 
```