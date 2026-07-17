/**
 * Syntropia full-lifecycle E2E (issue #253): alpha → beta → production.
 *
 * Greenfield smart-city journey: open citizen registration, critical-mass
 * gated beta, deposits + tax invoicing, real-identity submission at beta,
 * Congress root handover, Congress vote to go live.
 *
 * Requires a wizard-deployed Syntropia staging realm (II bypass enabled)
 * whose creator is deterministic test identity 0. Set REALM_BACKEND_ID
 * (and optionally TOKEN_CANISTER_ID) — see scripts/lifecycle-runner.mjs.
 */
import { test, expect } from '@playwright/test';
import {
  LifecycleHarness,
  PARAMS,
  sleep,
} from '../scripts/lifecycle-runner.mjs';

const harness = new LifecycleHarness('syntropia');

test.describe.serial('Syntropia lifecycle (alpha → beta → production)', () => {
  test.skip(!PARAMS.backendId, 'REALM_BACKEND_ID is not set');

  test.afterAll(() => {
    const file = harness.writeReport();
    console.log(`Lifecycle report: ${file}`);
  });

  test('P1 — founder session and preflight (alpha, Congress seeded)', async () => {
    test.setTimeout(300_000);
    const join = await harness.ensureFounderAdmin();
    expect(join.ok, `founder join failed: ${join.error}`).toBe(true);

    const { status, departments } = await harness.preflight();
    expect(status.realm_stage).toBe('alpha');
    expect(status.open_registration).toBe(true);
    expect(departments).toContain('Congress');
    expect(departments).toContain('Citizenship & Identity');
  });

  test('P2 — parameterize gates for a 25-citizen run', async () => {
    test.setTimeout(120_000);
    const res = await harness.configureGates({
      critical_mass: PARAMS.citizenCount,
    });
    expect(res.success, `patch_manifest_data failed: ${res.error}`).toBeTruthy();
  });

  test('P3 — alpha→beta is blocked before critical mass', async () => {
    test.setTimeout(120_000);
    const res = await harness.setStage(0, 'beta', 'E2E premature attempt');
    expect(res.success).toBeFalsy();
    expect(String(res.error || '')).toMatch(/critical mass|milestone/i);
    harness.record('beta_blocked', { missing: res.missing, error: res.error });
  });

  test('P4 — citizens join openly until critical mass', async () => {
    test.setTimeout(1_200_000);
    const { joined } = await harness.bulkJoinCitizens();
    expect(joined).toBe(PARAMS.citizenCount);

    // Greenfield onboarding: each citizen received a deposit invoice.
    const invoices = await harness.citizenInvoices(PARAMS.citizenOffset);
    const deposits = invoices.filter((i) => /deposit/i.test(i.metadata || ''));
    expect(deposits.length).toBeGreaterThan(0);

    const { status } = await harness.preflight();
    expect(Number(status.users_count)).toBeGreaterThanOrEqual(PARAMS.citizenCount);
  });

  test('P5 — staff every department seat (admins + citizens)', async () => {
    test.setTimeout(1_800_000);
    const { failed } = await harness.staffAllPositions();
    expect(
      failed,
      `unstaffed positions: ${JSON.stringify(failed)}`,
    ).toHaveLength(0);
    expect(harness.congressIndices.length).toBeGreaterThan(0);
  });

  test('P6 — Infrastructure defines zones', async () => {
    test.setTimeout(300_000);
    const results = await harness.defineZones(0, 2);
    expect(results.filter((r) => r.success).length).toBeGreaterThan(0);
  });

  test('P7 — Defense appoints an external company via procurement', async () => {
    test.setTimeout(600_000);
    const vendorIndex = PARAMS.citizenOffset + PARAMS.citizenCount + 50;
    const { ok, steps } = await harness.procurementSmoke(0, vendorIndex);
    expect(ok, `procurement smoke failed: ${JSON.stringify(steps)}`).toBe(true);
  });

  test('P8 — creator hands root to Congress and is demoted', async () => {
    test.setTimeout(300_000);
    const res = await harness.transferRoot(0, 'Congress');
    expect(res.success, `transfer_root failed: ${res.error}`).toBeTruthy();
    expect((res.data?.promoted ?? []).length).toBeGreaterThan(0);

    const after = await harness.configureGates({}, 0);
    expect(after.success).toBeFalsy();
    harness.record('creator_demoted', { denied_error: after.error });
  });

  test('P9 — Congress advances the realm to beta; money starts flowing', async () => {
    test.setTimeout(600_000);
    const congress = harness.congressIndices[0];
    const before = await harness.status(congress);

    const res = await harness.setStage(congress, 'beta', 'Critical mass reached');
    expect(res.success, `set_realm_stage beta failed: ${res.error}`).toBeTruthy();

    const stage = await harness.getStage(congress);
    expect(stage.stage).toBe('beta');
    expect(stage.lifecycle?.deposits_locked).toBe(true);

    // on_stage_change effects: tax invoices for citizens…
    const invoices = await harness.citizenInvoices(PARAMS.citizenOffset);
    const taxInvoices = invoices.filter((i) =>
      /membership_tax/.test(i.metadata || ''),
    );
    expect(taxInvoices.length).toBeGreaterThan(0);

    const after = await harness.status(congress);
    harness.record('beta_effects', {
      transfers_before: String(before.transfers_count ?? ''),
      transfers_after: String(after.transfers_count ?? ''),
      tax_invoices_first_citizen: taxInvoices.length,
    });
  });

  test('P10 — citizens submit real identity; registrar reviews', async () => {
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

    // Review: a Congress member (realm admin after handover) approves.
    const { testPrincipal } = await import('../scripts/identities.mjs');
    const review = await harness.reviewIdentity(
      congress,
      testPrincipal(PARAMS.citizenOffset),
      true,
    );
    expect(review.success, `review failed: ${review.error}`).toBeTruthy();
    expect(review.attestation?.status).toBe('approved');
    harness.record('identity_submissions', { submitted: results, review });
  });

  test('P11 — citizen pays the tax invoice (REALMS self-mint)', async () => {
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
  });

  test('P12 — beta→production requires the Congress vote + proving period', async () => {
    test.setTimeout(600_000);
    const congress = harness.congressIndices[0];

    const blocked = await harness.setStage(congress, 'production', 'E2E premature');
    expect(blocked.success).toBeFalsy();
    harness.record('production_blocked', { missing: blocked.missing });

    const vote = await harness.approveStage(congress, 'production');
    expect(vote.success, `approve failed: ${vote.error}`).toBeTruthy();

    await sleep(Math.ceil(PARAMS.provingDays * 86_400_000) + 10_000);

    const res = await harness.setStage(congress, 'production', 'Congress vote passed');
    expect(res.success, `go-live failed: ${res.error}`).toBeTruthy();

    const stage = await harness.getStage(congress);
    expect(stage.stage).toBe('production');
  });
});
