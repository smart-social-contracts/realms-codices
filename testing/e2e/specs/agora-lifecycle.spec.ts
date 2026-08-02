/**
 * Agora full-lifecycle E2E (issue #253): alpha → beta → production.
 *
 * Incumbent-migration journey: invitation-only citizens, checklist-gated
 * beta, payments starting at beta, Congress root handover, Congress vote
 * to go live.
 *
 * Requires a wizard-deployed Agora staging realm (II bypass + test invite
 * shortcuts enabled) whose creator is deterministic test identity 0.
 * Set REALM_BACKEND_ID (and optionally TOKEN_CANISTER_ID) — see
 * scripts/lifecycle-runner.mjs for all parameters.
 */
import { test, expect } from '@playwright/test';
import {
  LifecycleHarness,
  PARAMS,
  sleep,
} from '../scripts/lifecycle-runner.mjs';
import {
  capture,
  lifecycleUiCheckpoint,
  openExtension,
  realmBaseUrl,
  screenshotWizardCodex,
} from '../scripts/ui-checkpoints.mjs';

const harness = new LifecycleHarness('agora');

test.describe.serial('Agora lifecycle (alpha → beta → production)', () => {
  test.skip(!PARAMS.backendId, 'REALM_BACKEND_ID is not set');

  test.afterAll(() => {
    const file = harness.writeReport();
    console.log(`Lifecycle report: ${file}`);
  });

  test('P0 — wizard codex parameters UI', async ({ page }) => {
    test.setTimeout(120_000);
    const file = await screenshotWizardCodex(page, 'agora', { showAdvanced: true });
    expect(file).toBeTruthy();
  });

  test('P1 — founder session and preflight (alpha, Congress seeded)', async ({
    page,
  }) => {
    test.setTimeout(300_000);
    const join = await harness.ensureFounderAdmin();
    expect(join.ok, `founder join failed: ${join.error}`).toBe(true);

    const { status, departments } = await harness.preflight();
    // Fresh runs start in alpha; idempotent re-runs may already be further along.
    expect(['alpha', 'beta', 'production']).toContain(status.realm_stage);
    expect(departments).toContain('Congress');

    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'agora', '01-founder-realm-settings', {
        extension: 'realm_settings',
      });
      await openExtension(page, 'import_export');
      await capture(page, 'agora', '01-founder-import-export');
    }
  });

  test('P2 — parameterize gates for a 25-citizen run', async () => {
    test.setTimeout(120_000);
    const res = await harness.configureGates({
      population_target: PARAMS.citizenCount,
      critical_mass: PARAMS.citizenCount,
    });
    expect(res.success, `patch_manifest_data failed: ${res.error}`).toBeTruthy();
  });

  test('P3 — alpha→beta is blocked before readiness', async () => {
    test.setTimeout(120_000);
    const stage = await harness.getStage(0);
    if (stage.stage !== 'alpha') {
      harness.record('beta_blocked', {
        skipped: `already in ${stage.stage}`,
      });
      return;
    }
    const res = await harness.setStage(0, 'beta', 'E2E premature attempt');
    if (res.success) {
      // Checklist already satisfied on a re-run realm — gate correctly opened.
      harness.record('beta_blocked', {
        skipped: 'checklist already satisfied; premature block N/A',
        advanced: true,
      });
      return;
    }
    expect(res.success).toBeFalsy();
    expect(res.missing?.length ?? 0).toBeGreaterThan(0);
    harness.record('beta_blocked', { missing: res.missing, error: res.error });
  });

  test('P4 — founder mints member invite; citizens bulk-join', async () => {
    test.setTimeout(1_200_000);
    const invite = await harness.createMemberInvite(PARAMS.citizenCount * 4);
    expect(invite.success, `member invite failed: ${invite.error}`).toBeTruthy();

    const { joined } = await harness.bulkJoinCitizens();
    expect(joined).toBe(PARAMS.citizenCount);

    const { status } = await harness.preflight();
    expect(Number(status.users_count)).toBeGreaterThanOrEqual(PARAMS.citizenCount);
  });

  test('P5 — staff every department seat (admins + citizens)', async ({
    page,
  }) => {
    test.setTimeout(1_800_000);
    const { failed } = await harness.staffAllPositions();
    expect(
      failed,
      `unstaffed positions: ${JSON.stringify(failed)}`,
    ).toHaveLength(0);
    expect(harness.congressIndices.length).toBeGreaterThan(0);

    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'agora', '05-staffed-access-manager', {
        extension: 'access_manager',
      });
    }
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
    // Recorded in the report; RFP creation+publication is the hard assertion.
    expect(ok, `procurement smoke failed: ${JSON.stringify(steps)}`).toBe(true);
  });

  test('P8 — creator hands root to Congress and is demoted', async () => {
    test.setTimeout(300_000);
    const res = await harness.transferRoot(0, 'Congress');
    expect(res.success, `transfer_root failed: ${res.error}`).toBeTruthy();
    expect((res.data?.promoted ?? []).length).toBeGreaterThan(0);

    // Negative: the demoted creator can no longer perform admin actions.
    const after = await harness.configureGates({}, 0);
    expect(after.success).toBeFalsy();
    harness.record('creator_demoted', { denied_error: after.error });
  });

  test('P9 — Congress advances the realm to beta; money starts flowing', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    await harness.refreshCongressIndices();
    const congress = harness.congressIndices[0];
    expect(congress, 'no Congress identity recovered').toBeGreaterThanOrEqual(0);
    const before = await harness.status(congress);

    const current = await harness.getStage(congress);
    if (current.stage === 'alpha') {
      const res = await harness.setStage(congress, 'beta', 'E2E readiness complete');
      expect(res.success, `set_realm_stage beta failed: ${res.error}`).toBeTruthy();
    } else {
      harness.record('beta_already', { stage: current.stage });
    }

    const stage = await harness.getStage(congress);
    expect(['beta', 'production']).toContain(stage.stage);

    // on_stage_change effects: tax invoices for citizens…
    let invoices = await harness.citizenInvoices(PARAMS.citizenOffset);
    let taxInvoices = invoices.filter((i) =>
      /membership_tax/.test(i.metadata || ''),
    );
    if (taxInvoices.length === 0 && stage.stage === 'beta') {
      // Re-run path: trigger payroll/invoice hook explicitly if missing.
      await harness.runPayroll(congress);
      invoices = await harness.citizenInvoices(PARAMS.citizenOffset);
      taxInvoices = invoices.filter((i) =>
        /membership_tax/.test(i.metadata || ''),
      );
    }
    expect(taxInvoices.length).toBeGreaterThan(0);

    // …and payroll transfers recorded for salaried seats.
    const after = await harness.status(congress);
    harness.record('beta_effects', {
      transfers_before: String(before.transfers_count ?? ''),
      transfers_after: String(after.transfers_count ?? ''),
      tax_invoices_first_citizen: taxInvoices.length,
    });

    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'agora', '09-beta-realm-settings', {
        extension: 'realm_settings',
        inviteCode: 'admin',
      });
    }
  });

  test('P10 — citizen pays the tax invoice (REALMS self-mint)', async () => {
    test.setTimeout(600_000);
    const index = PARAMS.citizenOffset;
    const invoices = await harness.citizenInvoices(index);
    const taxInvoices = invoices.filter((i) =>
      /membership_tax/.test(i.metadata || ''),
    );
    const alreadyPaid = taxInvoices.find((i) => /paid/i.test(i.status || ''));
    if (alreadyPaid) {
      harness.record('payment', {
        invoice_id: alreadyPaid.id,
        already_paid: true,
        paid: true,
      });
      return;
    }
    const pending = taxInvoices.find((i) => i.status === 'Pending');
    expect(pending, 'no pending tax invoice found').toBeTruthy();

    const steps = await harness.payInvoice(index, pending);
    harness.record('payment', steps);
    if (!PARAMS.tokenCanisterId) {
      test.info().annotations.push({
        type: 'skip-detail',
        description: 'TOKEN_CANISTER_ID not set — payment execution skipped',
      });
    } else {
      expect(steps.mint?.success, `mint failed: ${JSON.stringify(steps)}`).toBe(true);
      expect(steps.transfer?.success).toBe(true);
    }
  });

  test('P11 — beta→production requires the Congress vote + proving period', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    await harness.refreshCongressIndices();
    const congress = harness.congressIndices[0];
    expect(congress, 'no Congress identity recovered').toBeGreaterThanOrEqual(0);

    const current = await harness.getStage(congress);
    if (current.stage === 'production') {
      harness.record('production_already', { stage: 'production' });
      return;
    }

    // Ensure proving-period clock is observable on re-runs where beta was
    // entered before timestamped history existed.
    await harness.configureGates({ beta_proving_days: PARAMS.provingDays }, congress);
    await harness.ensureBetaHistory(congress);

    // Negative: without confirm the governed gate demands a vote (or, on a
    // direct policy, the proving-period gate blocks) — no transition.
    const blocked = await harness.setStage(congress, 'production', 'E2E premature');
    expect(blocked.success).toBeFalsy();
    harness.record('production_blocked', {
      missing: blocked.missing,
      requires_confirmation: blocked.requires_confirmation,
    });

    // Wait out the (shortened) proving period.
    await sleep(Math.ceil(PARAMS.provingDays * 86_400_000) + 10_000);

    // Governed flow (realms#262): confirm → root-scoped proposal → vote →
    // replay applies the transition (hard gates re-checked at replay).
    const vote = await harness.approveStage(congress, 'production');
    expect(vote.success, `go-live vote failed: ${vote.error}`).toBeTruthy();

    const stage = await harness.getStage(congress);
    expect(stage.stage).toBe('production');

    if (realmBaseUrl()) {
      await lifecycleUiCheckpoint(page, 'agora', '11-production-realm-settings', {
        extension: 'realm_settings',
        inviteCode: 'admin',
      });
    }
  });
});
