/**
 * journeys.mjs — Cohort journey matrix.
 *
 * Each journey maps to a section of my-manual-E2E-test-checklist.md and runs in
 * its own isolated browser context with its own deterministic test identity.
 * Journeys receive (page, ctx) where ctx = { baseUrl, index, role, runId, consoleErrors }.
 *
 * Roles: root | admin | member | visitor | contractor  (checklist §0).
 */

import {
  COHORT_INDEX_BASE,
  CohortError,
  assertExtensionsMount,
  assertSidebarExcludes,
  joinRealmViaUI,
  loginAsTestIdentity,
} from './cohort-lib.mjs';

/** Admin-only sidebar entries that must never leak to lesser roles. */
const ADMIN_ONLY_LABELS = ['Admin Dashboard', 'Access Manager', 'Realm Settings', 'Member Manager'];

async function gotoDashboard(page, ctx) {
  await page.goto(`${ctx.baseUrl}/?standalone=1`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3_000); // let the sidebar/profile hydrate
}

/** §2 Onboarding — member joins through the real UI. */
async function journeyJoinMember(page, ctx) {
  ctx.principal = await joinRealmViaUI(page, ctx.baseUrl, ctx.index, { inviteCode: 'member' });
  await gotoDashboard(page, ctx);
  await assertSidebarExcludes(page, ADMIN_ONLY_LABELS);
}

/** §2 Onboarding — admin joins via the magic "admin" invite code. */
async function journeyJoinAdmin(page, ctx) {
  ctx.principal = await joinRealmViaUI(page, ctx.baseUrl, ctx.index, { inviteCode: 'admin' });
  await gotoDashboard(page, ctx);
}

/** §2 Root sanity — every sidebar extension mounts without a pink error box. */
async function journeyExtensionMountSweep(page, ctx) {
  ctx.principal = await joinRealmViaUI(page, ctx.baseUrl, ctx.index, { inviteCode: 'admin' });
  await gotoDashboard(page, ctx);
  ctx.mounted = await assertExtensionsMount(page);
}

/** §2 Per-role sanity — non-member visitor: public dashboard, no privileged data. */
async function journeyVisitorPublicDashboard(page, ctx) {
  await page.goto(`${ctx.baseUrl}/?standalone=1`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3_000);
  await assertSidebarExcludes(page, [...ADMIN_ONLY_LABELS, 'Vault', 'Voting', 'Member Dashboard']);
}

/** §3 Governance — member opens the voting extension; list + filters render. */
async function journeyMemberVoting(page, ctx) {
  ctx.principal = await joinRealmViaUI(page, ctx.baseUrl, ctx.index, { inviteCode: 'member' });
  await gotoDashboard(page, ctx);
  await page.goto(`${ctx.baseUrl}/extensions/voting?standalone=1`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4_000);
  const errorBox = page.locator('.bg-red-50, .border-red-200').first();
  if (await errorBox.isVisible().catch(() => false)) {
    throw new CohortError('voting extension rendered an error box');
  }
}

/** §3 Payments — member opens the vault extension; balances area renders. */
async function journeyMemberVault(page, ctx) {
  ctx.principal = await joinRealmViaUI(page, ctx.baseUrl, ctx.index, { inviteCode: 'member' });
  await gotoDashboard(page, ctx);
  await page.goto(`${ctx.baseUrl}/extensions/vault?standalone=1`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4_000);
  const errorBox = page.locator('.bg-red-50, .border-red-200').first();
  if (await errorBox.isVisible().catch(() => false)) {
    throw new CohortError('vault extension rendered an error box');
  }
}

/**
 * The cohort matrix. `count(n)` distributes n member-sized slots across the
 * member journeys; role journeys run once each.
 */
export const JOURNEYS = {
  'join-member': { role: 'member', checklist: '§2 Onboarding', fn: journeyJoinMember },
  'join-admin': { role: 'admin', checklist: '§2 Onboarding (admin invite)', fn: journeyJoinAdmin },
  'extension-mount-sweep': { role: 'admin', checklist: '§2 Root sanity', fn: journeyExtensionMountSweep },
  'visitor-public': { role: 'visitor', checklist: '§2 Per-role (non-member)', fn: journeyVisitorPublicDashboard },
  'member-voting': { role: 'member', checklist: '§3 Governance UI', fn: journeyMemberVoting },
  'member-vault': { role: 'member', checklist: '§3 Payments UI', fn: journeyMemberVault },
};

const MEMBER_JOURNEYS = ['join-member', 'member-voting', 'member-vault'];

/**
 * Build the cohort plan: one slot per fixed journey + n member slots round-robin
 * across the member journeys. Slot indices are disjoint deterministic-identity
 * indices (indexBase + slot). Bump indexBase per run against the same realm so
 * cohort identities never collide with a previous run's members.
 */
export function buildCohortPlan(members = 40, { only = [], indexBase = COHORT_INDEX_BASE } = {}) {
  const plan = [];
  const enabled = (id) => (only.length === 0 || only.includes(id));

  let slot = 0;
  for (const id of Object.keys(JOURNEYS)) {
    if (MEMBER_JOURNEYS.includes(id) || !enabled(id)) continue;
    plan.push({ journey: id, index: indexBase + slot++ });
  }
  for (let i = 0; i < members; i++) {
    const id = MEMBER_JOURNEYS[i % MEMBER_JOURNEYS.length];
    if (!enabled(id)) continue;
    plan.push({ journey: id, index: indexBase + slot++ });
  }
  return plan;
}
