/**
 * cohort-lib.mjs — Browser helpers for the mass-E2E cohort runner.
 *
 * These drive the REAL realm frontend through its test-mode II-bypass flow —
 * the same path a manual QA session takes (see my-manual-E2E-test-checklist.md):
 *
 *   /join → pick "Other identity" number → Continue → Terms → Invitation → Join Realm
 *
 * No localStorage auth mocks: every context logs in with a deterministic
 * Ed25519 test identity (src/realm_frontend/src/lib/test-identities.js) that
 * signs actual canister calls.
 */

import { testPrincipal } from '../scripts/identities.mjs';

/** Human-facing identity number is 1-based: index 0 → "Identity 1". */
export function identityNumberForIndex(index) {
  return index + 1;
}

/** Cohort identity-index range — see cursor_realm_mass_e2e_design.md §3. */
export const COHORT_INDEX_BASE = 10_000;

export class CohortError extends Error {}

/**
 * Assert the realm frontend is actually in II-bypass test mode before spending
 * time on a journey. Fails fast with a clear message otherwise.
 */
export async function assertTestModeJoinPage(page) {
  const picker = page.getByText('Pick a test identity', { exact: false });
  try {
    await picker.waitFor({ state: 'visible', timeout: 30_000 });
  } catch {
    throw new CohortError(
      'Join page did not show the test-identity picker — is the realm in ' +
      'test_mode with test_mode_ii_bypass? (Check status() runtime flags.)',
    );
  }
}

/**
 * Log in through the join page's test-identity picker as the given index.
 * Verifies the persona principal shown in the UI matches the deterministic
 * principal (checklist §0: "deterministic test identities resolve to the
 * expected principals"). Returns the principal text.
 */
export async function loginAsTestIdentity(page, index) {
  await assertTestModeJoinPage(page);

  const expectedPrincipal = testPrincipal(index);
  const number = identityNumberForIndex(index);

  await page.locator('#join-custom-identity-number').fill(String(number));
  // Commit the number (change handler selects the persona) and click Select.
  await page.locator('#join-custom-identity-number').press('Enter');
  await page.getByRole('button', { name: 'Select', exact: true }).click();

  // The custom persona card renders the principal for the entered number.
  const personaCard = page.locator(`text=${expectedPrincipal.slice(0, 12)}`);
  await personaCard.first().waitFor({ state: 'visible', timeout: 10_000 });

  await page.getByRole('button', { name: new RegExp(`Continue as Identity ${number}`) }).click();
  return expectedPrincipal;
}

/**
 * Complete the post-login join pipeline: Terms → Invitation → Join Realm → Welcome.
 *
 * Event-driven state machine rather than a fixed click sequence: the join page
 * auto-validates magic invite codes client-side and has reactive guards that
 * bounce forward through steps, so any given control may already be gone by the
 * time we look for it. We poll for whichever state is current and act on it.
 */
export async function completeJoinFlow(page, { inviteCode = '', timeoutMs = 120_000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  const agree = page.locator('input[type="checkbox"]').first();
  const inviteInput = page.locator('#invite-code');
  const validateBtn = page.getByRole('button', { name: 'Validate', exact: true });
  const grantedText = page.getByText(/Valid — grants/i);
  const joinBtn = page.getByRole('button', { name: 'Join Realm', exact: true });
  const welcome = page.getByRole('heading', { name: /Welcome to/i });
  const continueBtn = page.getByRole('button', { name: 'Continue', exact: true });

  let inviteFilled = false;
  while (Date.now() < deadline) {
    if (await welcome.isVisible().catch(() => false)) return;

    if (await agree.isVisible().catch(() => false)) {
      await agree.check().catch(() => {});
      if (await continueBtn.isVisible().catch(() => false)) {
        await continueBtn.click().catch(() => {});
      }
    } else if (await grantedText.isVisible().catch(() => false)) {
      // Invite already validated (client-side shortcut) — nothing to do;
      // the page may auto-advance, otherwise Join Realm is clicked below.
    } else if (inviteCode && !inviteFilled && await inviteInput.isVisible().catch(() => false)) {
      await inviteInput.fill(inviteCode);
      inviteFilled = true;
      if (await validateBtn.isVisible().catch(() => false)) {
        await validateBtn.click().catch(() => {}); // may have auto-validated mid-click
      }
    }

    if (await joinBtn.isVisible().catch(() => false)) {
      await joinBtn.click().catch(() => {});
    }
    await page.waitForTimeout(500);
  }
  throw new CohortError(`Join flow did not reach the Welcome step within ${timeoutMs}ms`);
}

/**
 * Join a realm end-to-end through the UI as deterministic identity `index`.
 * If the identity is already a member, the join page bounces to the dashboard —
 * treated as a successful "already_joined" outcome.
 */
export async function joinRealmViaUI(page, baseUrl, index, { inviteCode = '', timeoutMs } = {}) {
  await page.goto(`${baseUrl}/join?standalone=1`, { waitUntil: 'domcontentloaded' });

  const picker = page.getByText('Pick a test identity', { exact: false });
  const winner = await Promise.race([
    picker.waitFor({ state: 'visible', timeout: 45_000 }).then(() => 'picker'),
    page.waitForURL((url) => !url.pathname.startsWith('/join'), { timeout: 45_000 })
      .then(() => 'redirected'),
  ]).catch(() => 'timeout');

  if (winner === 'redirected') return testPrincipal(index); // already a member
  if (winner !== 'picker') {
    throw new CohortError(
      'Join page showed neither the test-identity picker nor a member redirect — ' +
      'is the realm in test_mode with test_mode_ii_bypass?',
    );
  }

  const principal = await loginAsTestIdentity(page, index);
  await completeJoinFlow(page, { inviteCode, timeoutMs });
  return principal;
}

/**
 * Assert every sidebar extension mounts without the pink error box
 * (checklist §2 "All selected extensions appear in the sidebar and mount
 * without errors"). Returns the list of visited extension labels.
 */
export async function assertExtensionsMount(page, { settleMs = 2_500 } = {}) {
  const visited = [];
  const sidebarLinks = page.locator('aside a[href], nav a[href]');
  const count = await sidebarLinks.count();
  const hrefs = new Set();
  for (let i = 0; i < count; i++) {
    const href = await sidebarLinks.nth(i).getAttribute('href');
    if (href && !href.startsWith('http') && !hrefs.has(href)) hrefs.add(href);
  }
  const errorBox = page.locator('.bg-red-50, .border-red-200').first();
  for (const href of hrefs) {
    const absolute = new URL(href, page.url()).href;
    await page.goto(absolute, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(settleMs);
    if (await errorBox.isVisible().catch(() => false)) {
      const text = (await errorBox.textContent().catch(() => ''))?.trim().slice(0, 200);
      throw new CohortError(`Extension at ${href} mounted with an error box: ${text}`);
    }
    visited.push(href);
  }
  return visited;
}

/**
 * Assert the sidebar does NOT contain any of the forbidden labels — used for
 * per-role checks (member must not see admin extensions, visitor must not see
 * member ones; checklist §2 per-role sanity).
 */
export async function assertSidebarExcludes(page, forbiddenLabels) {
  const sidebar = page.locator('aside, nav').first();
  for (const label of forbiddenLabels) {
    const item = sidebar.getByText(label, { exact: false });
    if (await item.isVisible().catch(() => false)) {
      throw new CohortError(`Sidebar leaked a forbidden entry for this role: "${label}"`);
    }
  }
}

/** Collect console errors from the page into ctx.consoleErrors (call early). */
export function trackConsoleErrors(page, ctx) {
  ctx.consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') ctx.consoleErrors.push(msg.text().slice(0, 300));
  });
  page.on('pageerror', (err) => ctx.consoleErrors.push(String(err).slice(0, 300)));
}
