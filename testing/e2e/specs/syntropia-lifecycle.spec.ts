/**
 * Syntropia full-lifecycle E2E (issue #253): alpha → beta → production.
 */
import { test, expect } from '@playwright/test';
import {
  LifecycleHarness,
  PARAMS,
  sleep,
} from '../scripts/lifecycle-runner.mjs';
import {
  capture,
  capturePhaseShots,
  lifecycleUiCheckpoint,
  openExtension,
  realmBaseUrl,
  screenshotWizardCodex,
} from '../scripts/ui-checkpoints.mjs';
import { buildTestResultsSite } from '../scripts/build-test-results-site.mjs';

const harness = new LifecycleHarness('syntropia');

function phaseId(title) {
  return title.match(/^(P\d+)/)?.[1] || null;
}

test.describe.serial('Syntropia lifecycle (alpha → beta → production)', () => {
  test.skip(!PARAMS.backendId, 'REALM_BACKEND_ID is not set');

  test.afterEach(async ({}, testInfo) => {
    const id = phaseId(testInfo.title);
    if (id) harness.recordTestRun(id, testInfo);
  });

  test.afterAll(async () => {
    harness.writeReport();
    buildTestResultsSite();
  });

  test('P0 — wizard codex parameters UI', async ({ page }) => {
    test.setTimeout(120_000);
    await screenshotWizardCodex(page, 'syntropia', { showAdvanced: false, name: '00-wizard-codex-basic' });
    const file = await screenshotWizardCodex(page, 'syntropia', { showAdvanced: true, name: '00-wizard-codex-parameters' });
    expect(file).toBeTruthy();
  });

  test('P1 — founder session and preflight (alpha, Congress seeded)', async ({ page }) => {
    test.setTimeout(300_000);
    const join = await harness.ensureFounderAdmin();
    expect(join.ok, `founder join failed: ${join.error}`).toBe(true);

    const { status, departments } = await harness.preflight();
    expect(status.realm_stage).toBe('alpha');
    expect(status.open_registration).toBe(true);
    expect(departments).toContain('Congress');
    expect(departments).toContain('Citizenship & Identity');

    if (realmBaseUrl()) {
      await capturePhaseShots(page, 'syntropia', [
        { extension: 'realm_settings', name: '01-founder-realm-settings' },
        { extension: 'voting', name: '01-founder-voting' },
        { extension: 'admin_dashboard', name: '01-founder-admin-dashboard' },
        { extension: 'public_dashboard', name: '01-public-dashboard' },
      ]);
    }
  });

  test('P2 — parameterize gates for a 25-citizen run', async ({ page }) => {
    test.setTimeout(120_000);
    const res = await harness.configureGates({ critical_mass: PARAMS.citizenCount });
    expect(res.success, `patch_manifest_data failed: ${res.error}`).toBeTruthy();
    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'syntropia', '02-alpha-realm-settings-gates', {
        extension: 'realm_settings',
      });
    }
  });

  test('P3 — alpha→beta is blocked before critical mass', async ({ page }) => {
    test.setTimeout(120_000);
    const res = await harness.setStage(0, 'beta', 'E2E premature attempt');
    expect(res.success).toBeFalsy();
    expect(String(res.error || '')).toMatch(/critical mass|milestone/i);
    harness.record('beta_blocked', { missing: res.missing, error: res.error });
    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'syntropia', '03-beta-blocked-lifecycle', {
        extension: 'realm_settings',
      });
    }
  });

  test('P4 — citizens join openly until critical mass', async ({ page }) => {
    test.setTimeout(1_200_000);
    const { joined } = await harness.bulkJoinCitizens();
    expect(joined).toBe(PARAMS.citizenCount);

    const invoices = await harness.citizenInvoices(PARAMS.citizenOffset);
    const deposits = invoices.filter((i) => /deposit/i.test(i.metadata || ''));
    expect(deposits.length).toBeGreaterThan(0);

    const { status } = await harness.preflight();
    expect(Number(status.users_count)).toBeGreaterThanOrEqual(PARAMS.citizenCount);

    if (realmBaseUrl()) {
      await capturePhaseShots(page, 'syntropia', [
        { extension: 'member_dashboard', name: '04-post-join-member-dashboard', inviteCode: '' },
        { extension: 'vault', name: '04-member-vault-deposits', inviteCode: '' },
        { extension: 'census', name: '04-census-population', inviteCode: '' },
      ], { joinFirst: false });
    }
  });

  test('P5 — staff every department seat (admins + citizens)', async ({ page }) => {
    test.setTimeout(1_800_000);
    const { failed } = await harness.staffAllPositions();
    expect(failed, `unstaffed positions: ${JSON.stringify(failed)}`).toHaveLength(0);
    expect(harness.congressIndices.length).toBeGreaterThan(0);

    if (realmBaseUrl()) {
      await capturePhaseShots(page, 'syntropia', [
        { extension: 'access_manager', name: '05-staffed-access-manager' },
        { extension: 'census', name: '05-census-population' },
      ]);
    }
  });

  test('P6 — Infrastructure defines zones', async ({ page }) => {
    test.setTimeout(300_000);
    const results = await harness.defineZones(0, 2);
    expect(results.filter((r) => r.success).length).toBeGreaterThan(0);
    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'syntropia', '06-zone-selector-map', {
        extension: 'zone_selector',
      });
    }
  });

  test('P7 — Defense appoints an external company via procurement', async ({ page }) => {
    test.setTimeout(600_000);
    const vendorIndex = PARAMS.citizenOffset + PARAMS.citizenCount + 50;
    const { ok, steps } = await harness.procurementSmoke(0, vendorIndex);
    expect(ok, `procurement smoke failed: ${JSON.stringify(steps)}`).toBe(true);
    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'syntropia', '07-procurement-rfp-list', {
        extension: 'procurement',
      });
    }
  });

  test('P8 — creator hands root to Congress and is demoted', async ({ page }) => {
    test.setTimeout(300_000);
    const res = await harness.transferRoot(0, 'Congress');
    expect(res.success, `transfer_root failed: ${res.error}`).toBeTruthy();
    expect((res.data?.promoted ?? []).length).toBeGreaterThan(0);

    const after = await harness.configureGates({}, 0);
    expect(after.success).toBeFalsy();
    harness.record('creator_demoted', { denied_error: after.error });

    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'syntropia', '08-post-handover-realm-settings', {
        extension: 'realm_settings',
      });
    }
  });

  test('P9 — Congress advances the realm to beta; money starts flowing', async ({ page }) => {
    test.setTimeout(600_000);
    const congress = harness.congressIndices[0];
    const before = await harness.status(congress);

    const res = await harness.setStage(congress, 'beta', 'Critical mass reached');
    expect(res.success, `set_realm_stage beta failed: ${res.error}`).toBeTruthy();

    const stage = await harness.getStage(congress);
    expect(stage.stage).toBe('beta');
    expect(stage.lifecycle?.deposits_locked).toBe(true);

    const invoices = await harness.citizenInvoices(PARAMS.citizenOffset);
    const taxInvoices = invoices.filter((i) => /membership_tax/.test(i.metadata || ''));
    expect(taxInvoices.length).toBeGreaterThan(0);

    harness.record('beta_effects', {
      transfers_before: String(before.transfers_count ?? ''),
      transfers_after: String((await harness.status(congress)).transfers_count ?? ''),
      tax_invoices_first_citizen: taxInvoices.length,
    });

    if (realmBaseUrl()) {
      await capturePhaseShots(page, 'syntropia', [
        { extension: 'realm_settings', name: '09-beta-realm-settings', inviteCode: 'admin' },
        { extension: 'voting', name: '09-beta-voting-filters', inviteCode: 'admin' },
        { extension: 'vault', name: '09-beta-vault-taxes', inviteCode: 'admin' },
      ], { joinFirst: true, inviteCode: 'admin' });
    }
  });

  test('P10 — citizens submit real identity; registrar reviews', async ({ page }) => {
    test.setTimeout(600_000);
    const congress = harness.congressIndices[0];
    const results = [];
    const SAMPLE = Math.min(5, PARAMS.citizenCount);
    for (let i = 0; i < SAMPLE; i++) {
      const index = PARAMS.citizenOffset + i;
      const submit = await harness.submitIdentity(index);
      results.push({ index, submit: !!submit.success, error: submit.error || null });
    }
    expect(results.every((r) => r.submit)).toBe(true);

    const { testPrincipal } = await import('../scripts/identities.mjs');
    const review = await harness.reviewIdentity(congress, testPrincipal(PARAMS.citizenOffset), true);
    expect(review.success, `review failed: ${review.error}`).toBeTruthy();
    expect(review.attestation?.status).toBe('approved');
    harness.record('identity_submissions', { submitted: results, review });

    if (realmBaseUrl()) {
      await capturePhaseShots(page, 'syntropia', [
        { extension: 'identity', name: '10-identity-submission', inviteCode: 'admin' },
        { extension: 'census', name: '10-registrar-queue', inviteCode: 'admin' },
      ], { joinFirst: true, inviteCode: 'admin' });
    }
  });

  test('P11 — citizen pays the tax invoice (REALMS self-mint)', async ({ page }) => {
    test.setTimeout(600_000);
    const index = PARAMS.citizenOffset;
    const invoices = await harness.citizenInvoices(index);
    const pending = invoices.find(
      (i) => i.status === 'Pending' && /membership_tax/.test(i.metadata || ''),
    );
    expect(pending, 'no pending tax invoice found').toBeTruthy();

    const steps = await harness.payInvoice(index, pending);
    harness.record('payment', steps);
    if (PARAMS.tokenCanisterId) {
      expect(steps.mint?.success, `mint failed: ${JSON.stringify(steps)}`).toBe(true);
      expect(steps.transfer?.success).toBe(true);
    }

    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'syntropia', '11-vault-tax-payment', {
        extension: 'vault',
        inviteCode: '',
        join: true,
      });
    }
  });

  test('P12 — beta→production requires the Congress vote + proving period', async ({ page }) => {
    test.setTimeout(600_000);
    const congress = harness.congressIndices[0];

    // Without confirm the governed gate demands a vote (or, on a direct
    // policy, the proving-period gate blocks) — either way no transition.
    const blocked = await harness.setStage(congress, 'production', 'E2E premature');
    expect(blocked.success).toBeFalsy();
    harness.record('production_blocked', {
      missing: blocked.missing,
      requires_confirmation: blocked.requires_confirmation,
    });

    await sleep(Math.ceil(PARAMS.provingDays * 86_400_000) + 10_000);

    // Governed flow (realms#262): confirm → root-scoped proposal → vote →
    // replay applies the transition (hard gates re-checked at replay).
    const vote = await harness.approveStage(congress, 'production');
    expect(vote.success, `go-live vote failed: ${vote.error}`).toBeTruthy();

    const stage = await harness.getStage(congress);
    expect(stage.stage).toBe('production');

    if (realmBaseUrl()) {
      await capturePhaseShots(page, 'syntropia', [
        { extension: 'realm_settings', name: '12-production-realm-settings', inviteCode: 'admin' },
        { extension: 'voting', name: '12-production-voting-history', inviteCode: 'admin' },
      ], { joinFirst: true, inviteCode: 'admin' });
    }
  });
});
