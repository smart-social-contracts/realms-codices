/**
 * Shared driver for the full-lifecycle E2E suites (issue #253).
 *
 * Drives a staging realm through alpha → beta → production with three
 * actor groups derived from deterministic test identities:
 *
 *   founder  — identity 0 (deployed the realm through the wizard)
 *   admins   — identities ADMIN_INDEX_OFFSET+i, appointed to department seats
 *   citizens — identities CITIZEN_INDEX_OFFSET+i, bulk-joined programmatically
 *
 * Test parameters (env):
 *   REALM_BACKEND_ID      target realm backend canister (required)
 *   TOKEN_CANISTER_ID     ICRC-1 token with test-mode mint (optional; payment
 *                         execution is skipped without it)
 *   TEST_CITIZEN_COUNT    bulk citizens to join (default 25)
 *   TEST_QUARTER_CAPACITY expected per-quarter capacity (default 10, informational)
 *   TEST_PROVING_DAYS     beta→production proving period override (default 0.0005 ≈ 43 s)
 *   ADMIN_INDEX_OFFSET    identity index of the first admin (default 10)
 *   CITIZEN_INDEX_OFFSET  identity index of the first citizen (default 1000)
 */
import fs from 'node:fs';
import path from 'node:path';
import { testIdentity, testPrincipal } from './identities.mjs';
import {
  extCall,
  joinRealm,
  myInvoices,
  realmActor,
  realmStatus,
  sha256Hex,
  tokenActor,
} from './realm-client.mjs';

export const PARAMS = {
  backendId: process.env.REALM_BACKEND_ID || '',
  tokenCanisterId: process.env.TOKEN_CANISTER_ID || '',
  citizenCount: parseInt(process.env.TEST_CITIZEN_COUNT || '25', 10),
  quarterCapacity: parseInt(process.env.TEST_QUARTER_CAPACITY || '10', 10),
  provingDays: parseFloat(process.env.TEST_PROVING_DAYS || '0.0005'),
  adminOffset: parseInt(process.env.ADMIN_INDEX_OFFSET || '10', 10),
  citizenOffset: parseInt(process.env.CITIZEN_INDEX_OFFSET || '1000', 10),
};

export class LifecycleHarness {
  /**
   * @param {'agora'|'syntropia'} codex
   */
  constructor(codex) {
    this.codex = codex;
    this.params = { ...PARAMS };
    this.actors = new Map(); // identity index -> actor
    this.report = {
      codex,
      backendId: this.params.backendId,
      params: this.params,
      startedAt: new Date().toISOString(),
      phases: {},
    };
    this.memberInviteCode = ''; // plaintext member invite (Agora)
    this.congressIndices = []; // identity indices appointed to Congress
  }

  record(phase, data) {
    this.report.phases[phase] = { at: new Date().toISOString(), ...data };
  }

  /** Playwright test outcome + attachments for the HTML report. */
  recordTestRun(phaseId, testInfo) {
    if (!this.report.testRuns) this.report.testRuns = {};
    const video = testInfo.attachments?.find((a) =>
      (a.contentType || '').startsWith('video/'),
    );
    this.report.testRuns[phaseId] = {
      title: testInfo.title,
      status: testInfo.status,
      duration: testInfo.duration,
      video: video?.path || null,
      errors: testInfo.errors?.map((e) => e.message) || [],
      at: new Date().toISOString(),
    };
  }

  writeReport(dir = 'test-results') {
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${this.codex}-lifecycle-report.json`);
    fs.writeFileSync(file, JSON.stringify(this.report, replacer, 2));
    return file;
  }

  async actor(index) {
    if (!this.actors.has(index)) {
      this.actors.set(
        index,
        await realmActor(this.params.backendId, testIdentity(index)),
      );
    }
    return this.actors.get(index);
  }

  founder() {
    return this.actor(0);
  }

  /** Public status() record as any identity (works pre/post demotion). */
  async status(byIndex = 0) {
    return realmStatus(await this.actor(byIndex));
  }

  // ------------------------------------------------------------------
  // Phase 1 — preflight
  // ------------------------------------------------------------------

  async preflight() {
    const founder = await this.founder();
    const status = await realmStatus(founder);
    let depts = await extCall(founder, 'access_manager', 'list_departments');
    let deptList = depts.data?.departments || depts.departments || [];
    // After root handover the demoted founder may no longer list orgs —
    // fall back to a Congress identity.
    if (!deptList.length) {
      await this.refreshCongressIndices();
      const congress = this.congressIndices[0];
      if (congress != null) {
        depts = await extCall(
          await this.actor(congress),
          'access_manager',
          'list_departments',
        );
        deptList = depts.data?.departments || depts.departments || [];
      }
    }
    // Stage metadata also carries the seeded department name list.
    if (!deptList.length) {
      const stage = await extCall(founder, 'realm_settings', 'get_realm_stage');
      const seeded = stage.data?.departments || [];
      if (Array.isArray(seeded) && seeded.length) {
        deptList = seeded.map((n) => (typeof n === 'string' ? { name: n } : n));
      }
    }
    const names = deptList.map((d) => d.name || d);
    this.record('preflight', {
      realm_name: status.realm_name,
      stage: status.realm_stage,
      users_count: Number(status.users_count),
      open_registration: status.open_registration,
      test_mode_ii_bypass: status.test_mode_ii_bypass,
      departments: names,
    });
    return { status, departments: names };
  }

  // ------------------------------------------------------------------
  // Phase 2 — founder session + gate parameterization
  // ------------------------------------------------------------------

  async ensureFounderAdmin() {
    const founder = await this.founder();
    // First probe without an invite. If the founder is already a member,
    // do NOT redeem the test-mode "admin" checksum — that would re-grant
    // the admin profile and undo a prior root handover demotion.
    let res = await joinRealm(founder, '');
    if (!res.ok && !res.alreadyMember) {
      res = await joinRealm(founder, 'admin');
    } else if (res.ok || res.alreadyMember) {
      // Open registration (Syntropia) lets an empty join succeed as a plain
      // member. get_realm_stage is public — probe an admin-only write instead.
      // Elevate via "admin" only while still in alpha (pre root-handover).
      try {
        const probe = await extCall(
          founder,
          'realm_settings',
          'patch_manifest_data',
          { fields: { lifecycle_overrides: {} } },
        );
        const denied = /not a realm admin|access denied/i.test(
          String(probe.error || ''),
        );
        if (denied) {
          const status = await realmStatus(founder);
          if (status.realm_stage === 'alpha') {
            res = await joinRealm(founder, 'admin');
          }
        }
      } catch {
        // status/probe failed — leave the open-join result as-is
      }
    }
    this.record('founder_admin', {
      principal: testPrincipal(0),
      joined: res.ok,
      alreadyMember: !!res.alreadyMember,
      error: res.error || null,
    });
    return res;
  }

  /**
   * Prefer the founder while they still hold admin; after root handover fall
   * back to the first Congress identity we know about.
   */
  async adminIndex() {
    if (this.congressIndices.length > 0) return this.congressIndices[0];
    // Probe: can the founder still patch settings?
    return 0;
  }

  /** Patch gate parameters so a 25-citizen run can reach beta/production. */
  async configureGates(overrides, byIndex = null) {
    const lifecycleOverrides = {
      beta_proving_days: this.params.provingDays,
      ...overrides,
    };
    const configOverrides = {};
    const lifecycleBlock = {};
    if (overrides.critical_mass != null) {
      lifecycleBlock.critical_mass = overrides.critical_mass;
    }
    if (overrides.population_target != null) {
      lifecycleBlock.population_target = overrides.population_target;
    }
    if (Object.keys(lifecycleBlock).length) {
      configOverrides.lifecycle = lifecycleBlock;
    }
    const fields = { lifecycle_overrides: lifecycleOverrides };
    if (Object.keys(configOverrides).length) {
      fields.config_overrides = configOverrides;
    }
    const tryAt = async (index) =>
      extCall(await this.actor(index), 'realm_settings', 'patch_manifest_data', {
        fields,
      });

    let index = byIndex != null ? byIndex : 0;
    let res = await tryAt(index);
    if (!res.success && byIndex == null) {
      await this.refreshCongressIndices();
      if (this.congressIndices[0] != null) {
        index = this.congressIndices[0];
        res = await tryAt(index);
      }
    }
    this.record('configure_gates', {
      overrides: lifecycleOverrides,
      by_index: index,
      success: !!res.success,
      error: res.error || null,
    });
    return res;
  }

  // ------------------------------------------------------------------
  // Phase 3 — joining (citizens + staff)
  // ------------------------------------------------------------------

  /** Agora only: mint a multi-use member invite code (founder, else Congress). */
  async createMemberInvite(maxUses) {
    this.memberInviteCode = `e2e-member-${Date.now()}`;
    const payload = {
      code_hash: sha256Hex(this.memberInviteCode),
      profile: 'member',
      max_uses: maxUses,
      expires_in_hours: 24,
      created_by: testPrincipal(0),
      user_id: '',
    };
    let res = await extCall(
      await this.founder(),
      'role_manager',
      'generate_registration_url',
      payload,
    );
    if (!res.success) {
      await this.refreshCongressIndices();
      const congress = this.congressIndices[0];
      if (congress != null) {
        payload.created_by = testPrincipal(congress);
        res = await extCall(
          await this.actor(congress),
          'role_manager',
          'generate_registration_url',
          payload,
        );
      }
    }
    this.record('member_invite', {
      success: !!res.success,
      max_uses: maxUses,
      error: res.error || null,
    });
    return res;
  }

  /**
   * Join one identity as member/citizen. Agora uses the shared member invite;
   * Syntropia joins codeless (open registration).
   */
  async joinCitizen(index) {
    const actor = await this.actor(index);
    const code = this.codex === 'agora' ? this.memberInviteCode : '';
    return joinRealm(actor, code);
  }

  async bulkJoinCitizens() {
    const { citizenCount, citizenOffset } = this.params;
    const results = [];
    const CONCURRENCY = 5;
    for (let base = 0; base < citizenCount; base += CONCURRENCY) {
      const batch = [];
      for (let i = base; i < Math.min(base + CONCURRENCY, citizenCount); i++) {
        const index = citizenOffset + i;
        batch.push(
          this.joinCitizen(index).then((r) => ({
            index,
            principal: testPrincipal(index),
            ok: r.ok,
            alreadyMember: !!r.alreadyMember,
            error: r.error || null,
          })),
        );
      }
      results.push(...(await Promise.all(batch)));
    }
    const joined = results.filter((r) => r.ok).length;
    this.record('bulk_join', {
      requested: citizenCount,
      joined,
      failures: results.filter((r) => !r.ok),
    });
    return { results, joined };
  }

  // ------------------------------------------------------------------
  // Phase 4 — staffing departments
  // ------------------------------------------------------------------

  async listDepartmentsFull() {
    const tryList = async (index) => {
      const res = await extCall(
        await this.actor(index),
        'access_manager',
        'list_departments',
      );
      return res.data?.departments || res.departments || [];
    };
    let depts = await tryList(0);
    if (depts.length) return depts;
    // Demoted founder / non-admin: probe known admin and Congress ranges.
    const { adminOffset } = this.params;
    const candidates = [
      ...this.congressIndices,
      ...Array.from({ length: 24 }, (_, i) => adminOffset + i),
    ];
    for (const index of candidates) {
      depts = await tryList(index);
      if (depts.length) return depts;
    }
    return [];
  }

  /** Force 1/1 policy so appointments apply immediately (not as proposals). */
  async ensureDirectPolicy(byIndex, deptName) {
    const actor = await this.actor(byIndex);
    return extCall(actor, 'access_manager', 'update_department', {
      name: deptName,
      threshold_m: 1,
      threshold_n: 1,
      quorum_percent: 0,
    });
  }

  async appoint(byIndex, positionKey, principal) {
    const actor = await this.actor(byIndex);
    const deptName = String(positionKey || '').split('/')[0];
    if (deptName) {
      await this.ensureDirectPolicy(byIndex, deptName);
    }
    const res = await extCall(actor, 'access_manager', 'manage_position', {
      action: 'appoint',
      key: positionKey,
      principal,
    });
    // A "success" that only opened a proposal did not fill the seat.
    if (res.success && (res.data?.applied === 'proposal' || res.applied === 'proposal')) {
      return {
        success: false,
        error: `appointment became a proposal (org policy not direct): ${res.data?.summary || ''}`,
        data: res.data,
      };
    }
    return res;
  }

  /**
   * Staff every open position with at least one holder:
   *   - head seats (first position of each department) get dedicated admin
   *     identities (ADMIN_INDEX_OFFSET+i) — the "civil servants";
   *   - remaining seats are filled round-robin with citizens.
   * All appointees must already be realm members.
   */
  /**
   * Map a principal text back to a deterministic identity index we control
   * (admins / citizens / vendor range). Returns null when unknown.
   */
  principalToIndex(principal) {
    const { adminOffset, citizenOffset, citizenCount } = this.params;
    const ranges = [
      [0, 1], // founder
      [adminOffset, adminOffset + 64],
      [citizenOffset, citizenOffset + citizenCount + 64],
    ];
    for (const [start, end] of ranges) {
      for (let i = start; i < end; i++) {
        if (testPrincipal(i) === principal) return i;
      }
    }
    return null;
  }

  /** Refresh congressIndices from live Department holders (idempotent re-runs). */
  async refreshCongressIndices() {
    const departments = await this.listDepartmentsFull();
    const congress = departments.find((d) => d.name === 'Congress');
    const indices = [];
    for (const pos of congress?.positions || []) {
      for (const holder of pos.holders || []) {
        const idx = this.principalToIndex(holder.principal);
        if (idx != null && !indices.includes(idx)) indices.push(idx);
      }
    }
    for (const m of congress?.members || []) {
      const idx = this.principalToIndex(m.principal);
      if (idx != null && !indices.includes(idx)) indices.push(idx);
    }
    this.congressIndices = indices;
    return indices;
  }

  async staffAllPositions() {
    const departments = await this.listDepartmentsFull();
    const { adminOffset, citizenOffset, citizenCount } = this.params;

    const appointments = [];
    let adminCursor = 0;
    let citizenCursor = 0;

    for (const dept of departments) {
      if (dept.is_root) continue;
      const positions = dept.positions || [];
      for (let p = 0; p < positions.length; p++) {
        const pos = positions[p];
        if ((pos.status || 'open') !== 'open') continue;
        if ((pos.filled || 0) > 0) {
          appointments.push({ key: pos.key, skipped: 'already filled' });
          // Advance admin cursor past head seats that were already filled so
          // later head appointments don't collide with previous runs.
          if (p === 0) adminCursor++;
          continue;
        }
        let index;
        if (p === 0) {
          index = adminOffset + adminCursor++;
          // Head seats get dedicated admin identities; join them first.
          const joinRes = await this.joinCitizen(index);
          if (!joinRes.ok) {
            appointments.push({ key: pos.key, error: `join failed: ${joinRes.error}` });
            continue;
          }
        } else {
          index = citizenOffset + (citizenCursor++ % citizenCount);
        }
        const principal = testPrincipal(index);
        const res = await this.appoint(0, pos.key, principal);
        appointments.push({
          key: pos.key,
          principal,
          identity_index: index,
          success: !!res.success,
          error: res.error || res.data?.error || null,
        });
      }
    }

    // Always rebuild Congress actors from live state so re-runs (where every
    // seat is already filled) still know who can vote / advance stages.
    await this.refreshCongressIndices();

    const failed = appointments.filter((a) => a.error);
    this.record('staffing', {
      appointments,
      failed_count: failed.length,
      congress_indices: this.congressIndices,
    });
    return { appointments, failed };
  }

  // ------------------------------------------------------------------
  // Phase 5 — zones, procurement
  // ------------------------------------------------------------------

  async defineZones(byIndex, count = 2) {
    const actor = await this.actor(byIndex);
    const results = [];
    // Offset per codex so Agora/Syntropia capitals don't share one map pin.
    const codexShift = this.codex === 'syntropia' ? 0.12 : 0;
    for (let i = 0; i < count; i++) {
      // The backend stores only the H3 cell index; geometry is computed on
      // the frontend using h3-js. Use a deterministic pseudo-cell id here.
      const lat = 41.38 + codexShift + i * 0.05;
      const lng = 2.17 + codexShift * 0.5 + i * 0.05;
      const res = await extCall(actor, 'zone_selector', 'add_zone', {
        user_id: testPrincipal(byIndex),
        h3_index: `e2e_${lat.toFixed(4)}_${lng.toFixed(4)}`,
        name: `E2E Zone ${i + 1}`,
        description: `Zone defined by Infrastructure during the ${this.codex} lifecycle E2E`,
      });
      // Idempotent re-runs: an existing zone at the same cell still counts.
      const already =
        /already (have|exists)/i.test(res.error || '') ||
        /already exists/i.test(res.error || '');
      results.push({
        success: !!res.success || already,
        error: res.success || already ? null : res.error || null,
        already,
      });
    }
    this.record('zones', { created: results.filter((r) => r.success).length, results });
    return results;
  }

  /**
   * Procurement smoke: an admin publishes an RFP, an external vendor
   * (fresh identity joined as member) bids, admin closes and awards.
   * Every step is recorded; failures are reported but tolerated so the
   * lifecycle can proceed (the extension may be absent on older realms).
   */
  async procurementSmoke(adminIndex, vendorIndex) {
    let adminIdx = adminIndex;
    let admin = await this.actor(adminIdx);
    const steps = {};
    const now = Math.floor(Date.now() / 1000);

    const vendorJoin = await this.joinCitizen(vendorIndex);
    steps.vendor_join = { ok: vendorJoin.ok, error: vendorJoin.error || null };

    const rfpArgs = {
      title: 'Security patrol services (E2E)',
      description: 'External third-party appointment exercised by the lifecycle E2E',
      opens_at: now - 60,
      closes_at: now + 3600,
      rubric_json: [{ id: 'price', label: 'Price', weight: 1.0, max_score: 100 }],
    };
    let created = await extCall(admin, 'procurement', 'create_rfp', rfpArgs);
    // After root handover the founder can no longer create RFPs — use Congress.
    if (!created.success) {
      await this.refreshCongressIndices();
      if (this.congressIndices[0] != null) {
        adminIdx = this.congressIndices[0];
        admin = await this.actor(adminIdx);
        created = await extCall(admin, 'procurement', 'create_rfp', rfpArgs);
      }
    }
    steps.create_rfp = created;
    steps.admin_index = adminIdx;
    const rfpId = created.rfp?.rfp_id || created.data?.rfp?.rfp_id;

    if (rfpId) {
      steps.publish_rfp = await extCall(admin, 'procurement', 'publish_rfp', {
        rfp_id: rfpId,
      });

      const vendor = await this.actor(vendorIndex);
      const shell = await extCall(vendor, 'procurement', 'create_bid_shell', {
        rfp_id: rfpId,
      });
      steps.create_bid_shell = shell;
      const bidId = shell.bid_id || shell.data?.bid_id || shell.bid?.bid_id;
      if (bidId) {
        steps.set_bid_payload = await extCall(vendor, 'procurement', 'set_bid_payload', {
          bid_id: bidId,
          ciphertext: JSON.stringify({ price: 1000, notes: 'E2E vendor bid' }),
          encryption_mode: 'none',
        });
      }

      steps.close_rfp = await extCall(admin, 'procurement', 'close_rfp', {
        rfp_id: rfpId,
      });
      if (bidId) {
        steps.award_rfp = await extCall(admin, 'procurement', 'award_rfp', {
          rfp_id: rfpId,
          bid_id: bidId,
        });
        steps.execute_contract = await extCall(admin, 'procurement', 'execute_contract', {
          rfp_id: rfpId,
        });
      }
    }

    const ok = !!(steps.create_rfp?.success && steps.publish_rfp?.success);
    this.record('procurement', { ok, rfp_id: rfpId || null, steps });
    return { ok, steps };
  }

  // ------------------------------------------------------------------
  // Phase 6 — lifecycle transitions
  // ------------------------------------------------------------------

  async getStage(byIndex = 0) {
    const actor = await this.actor(byIndex);
    const res = await extCall(actor, 'realm_settings', 'get_realm_stage');
    return res.data || {};
  }

  async setStage(byIndex, stage, reason) {
    const actor = await this.actor(byIndex);
    return extCall(actor, 'realm_settings', 'set_realm_stage', { stage, reason });
  }

  async transferRoot(byIndex = 0, targetOrg = 'Congress') {
    const actor = await this.actor(byIndex);
    // Governed action (realms#262): confirm up front; a non-1/1 root policy
    // yields a proposal whose replay demotes the recorded initiator (the
    // founder), which we force through with the test-mode executor.
    let res = await extCall(actor, 'realm_settings', 'transfer_root', {
      target_org: targetOrg,
      confirm: true,
    });
    if (res.applied === 'proposal' && res.proposal_id) {
      const exec = await extCall(actor, 'voting', 'demo_approve_and_execute', {
        proposal_id: res.proposal_id,
      });
      res = { ...exec, proposal_id: res.proposal_id };
    }
    // Idempotent re-run: founder already demoted after a prior handover.
    if (
      !res.success &&
      /not a realm admin/i.test(res.error || '')
    ) {
      await this.refreshCongressIndices();
      const already = {
        success: true,
        data: {
          already: true,
          target_org: targetOrg,
          promoted: this.congressIndices.map((i) => testPrincipal(i)),
        },
      };
      this.record('root_transfer', {
        target_org: targetOrg,
        success: true,
        already: true,
        promoted: already.data.promoted,
        error: null,
      });
      return already;
    }
    await this.refreshCongressIndices();
    this.record('root_transfer', {
      target_org: targetOrg,
      success: !!res.success,
      promoted: res.data?.promoted || [],
      error: res.error || null,
    });
    return res;
  }

  /**
   * Drive a governed stage transition to execution (realms#262): submit
   * set_realm_stage with confirm=true. When the root policy demands a vote
   * this creates a root-scoped proposal, which we force through with the
   * test-mode demo_approve_and_execute helper; a 1/1 policy applies
   * directly. The lifecycle hard gates (proving period, checklist) are
   * re-checked when the proposal replays.
   */
  async approveStage(byIndex, stage) {
    const actor = await this.actor(byIndex);
    const res = await extCall(actor, 'realm_settings', 'set_realm_stage', {
      stage,
      reason: 'Congress vote (E2E)',
      confirm: true,
    });
    if (res.applied === 'proposal' && res.proposal_id) {
      const exec = await extCall(actor, 'voting', 'demo_approve_and_execute', {
        proposal_id: res.proposal_id,
      });
      return { ...exec, proposal_id: res.proposal_id };
    }
    return res;
  }

  /**
   * Ensure lifecycle.history has a timestamped beta entry so the proving
   * period gate can evaluate. Needed on re-runs where beta was entered
   * before set_realm_stage recorded `at` timestamps.
   */
  async ensureBetaHistory(byIndex = 0) {
    const actor = await this.actor(byIndex);
    const stage = await extCall(actor, 'realm_settings', 'get_realm_stage');
    const history = stage.data?.lifecycle?.history || [];
    const hasBeta = history.some(
      (h) => h && h.stage === 'beta' && Number(h.at) > 0,
    );
    if (hasBeta) {
      this.record('beta_history', { already: true, history });
      return { success: true, already: true };
    }
    // Write via patch_manifest_data (admin). Use a beta timestamp 2 minutes ago.
    const at = Math.floor(Date.now() / 1000) - 120;
    const res = await extCall(actor, 'realm_settings', 'patch_manifest_data', {
      fields: {
        lifecycle: {
          ...(stage.data?.lifecycle || {}),
          history: [...history, { stage: 'beta', reason: 'E2E history backfill', at }],
        },
      },
    });
    this.record('beta_history', {
      success: !!res.success,
      at,
      error: res.error || null,
    });
    return res;
  }

  // ------------------------------------------------------------------
  // Phase 7 — money flow at beta
  // ------------------------------------------------------------------

  async citizenInvoices(index) {
    const actor = await this.actor(index);
    return myInvoices(actor);
  }

  /**
   * Full payment loop for one citizen invoice: test-mode mint → ICRC-1
   * transfer of the exact nonce-adjusted amount to the realm principal →
   * refresh_invoice. Requires TOKEN_CANISTER_ID; returns a step record.
   */
  async payInvoice(index, invoice) {
    const steps = { invoice_id: invoice.id };
    if (!this.params.tokenCanisterId) {
      steps.skipped = 'TOKEN_CANISTER_ID not set';
      return steps;
    }
    try {
      const identity = testIdentity(index);
      const token = await tokenActor(this.params.tokenCanisterId, identity);
      const decimals = Number(await token.icrc1_decimals());
      const fee = BigInt(await token.icrc1_fee());
      const baseRaw = BigInt(Math.round(Number(invoice.amount) * 10 ** decimals));
      const amountRaw = baseRaw + BigInt(invoice.payment_nonce || 0);

      const mint = await token.mint({
        to: { owner: identity.getPrincipal(), subaccount: [] },
        amount: amountRaw + fee * 2n,
      });
      steps.mint = { success: mint.success, error: mint.error?.[0] || null };

      const { Principal } = await import('@dfinity/principal');
      const transfer = await token.icrc1_transfer({
        from_subaccount: [],
        to: { owner: Principal.fromText(this.params.backendId), subaccount: [] },
        amount: amountRaw,
        fee: [],
        memo: [],
        created_at_time: [],
      });
      steps.transfer = {
        success: transfer.success,
        error: transfer.error?.[0] || null,
      };

      const actor = await this.actor(index);
      const refreshRaw = await actor.refresh_invoice(
        JSON.stringify({ invoice_id: invoice.id }),
      );
      let refresh;
      try {
        refresh = JSON.parse(refreshRaw);
      } catch {
        refresh = { raw: refreshRaw };
      }
      steps.refresh = refresh;
      steps.paid = !!(
        refresh?.success &&
        /paid/i.test(JSON.stringify(refresh?.data || ''))
      );
    } catch (e) {
      steps.error = String(e?.message || e);
    }
    return steps;
  }

  // ------------------------------------------------------------------
  // Syntropia-specific: real-identity submission
  // ------------------------------------------------------------------

  async submitIdentity(index) {
    const actor = await this.actor(index);
    return extCall(actor, 'syntropia', 'submit_identity', {
      full_name: `E2E Citizen ${index}`,
      document_ref: `PASSPORT-${index}`,
    });
  }

  async reviewIdentity(byIndex, userPrincipal, approve = true) {
    const actor = await this.actor(byIndex);
    return extCall(actor, 'syntropia', 'review_identity', {
      user_id: userPrincipal,
      approve,
    });
  }

  async runPayroll(byIndex) {
    const actor = await this.actor(byIndex);
    return extCall(actor, this.codex, 'run_payroll', {});
  }
}

function replacer(_key, value) {
  return typeof value === 'bigint' ? value.toString() : value;
}

export async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
