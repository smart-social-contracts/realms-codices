/** Narrative metadata for lifecycle E2E phases (issue #253). */

export const SYNTROPIA_PHASES = [
  {
    id: 'P0',
    title: 'Wizard — codex parameters UI',
    summary:
      'Open the staging registry create-realm wizard, select the Syntropia codex, and verify the Parameters panel renders defaults plus advanced governance fields.',
    actions: [
      'Navigate to /create-realm on the staging portal.',
      'Select Syntropia; wait for the codex manifest (extensions + parameters schema).',
      'Expand advanced parameters and capture the full wizard panel.',
    ],
    checklist: ['§1 wizard completes', '§1 parameters visible with defaults', '§1 overrides editable'],
    uiShots: ['00-wizard-codex-basic', '00-wizard-codex-parameters'],
  },
  {
    id: 'P1',
    title: 'Founder session & alpha preflight',
    summary:
      'Join the deployed realm as deterministic test identity 0 (founder), confirm alpha stage, open registration, and Congress + Citizenship departments seeded.',
    actions: [
      'Programmatic founder join via realm backend API.',
      'status() + list_departments preflight.',
      'Browser: realm_settings lifecycle card and voting extension shell.',
    ],
    checklist: ['§2 root login', '§2 extensions mount', '§2 realm settings alpha', '§1 departments seeded'],
    uiShots: ['01-founder-realm-settings', '01-founder-voting', '01-founder-admin-dashboard'],
  },
  {
    id: 'P2',
    title: 'Parameterize lifecycle gates',
    summary:
      'Patch manifest_data to set critical_mass to the test citizen count (25) and shorten proving period for automation.',
    actions: [
      'configureGates({ critical_mass: 25, beta_proving_days: ~43s }).',
      'Verify patch_manifest_data success.',
    ],
    checklist: ['§1 overridden parameters in effect'],
    uiShots: ['02-alpha-realm-settings-gates'],
  },
  {
    id: 'P3',
    title: 'Alpha→beta blocked before critical mass',
    summary:
      'Attempt premature stage advance; expect failure citing critical mass / milestone.',
    actions: ['set_realm_stage(beta) as founder while population < target.'],
    checklist: ['§2 stage gate blocked with clear error'],
    uiShots: ['03-beta-blocked-lifecycle'],
  },
  {
    id: 'P4',
    title: 'Citizens join until critical mass',
    summary:
      'Bulk-join 25 citizens via programmatic identities; each receives a refundable deposit invoice.',
    actions: [
      'bulkJoinCitizens() with identities 1000–1024.',
      'Assert deposit invoices on first citizen.',
      'Browser: member dashboard after open join.',
    ],
    checklist: ['§2 open registration', '§2 deposit invoice per citizen', '§2 critical mass reached'],
    uiShots: ['04-post-join-member-dashboard', '04-member-vault-deposits'],
  },
  {
    id: 'P5',
    title: 'Staff every department seat',
    summary:
      'Appoint admins and citizens to all department positions; Congress actors identified for later votes.',
    actions: [
      'staffAllPositions() — head + member seats across all departments.',
      'Browser: access_manager org chart.',
    ],
    checklist: ['§2 staff appointments succeed', '§2 Congress staffed'],
    uiShots: ['05-staffed-access-manager', '05-census-population'],
  },
  {
    id: 'P6',
    title: 'Infrastructure defines zones',
    summary:
      'Infrastructure dept adds H3 zones via zone_selector extension (Syntropia land prep).',
    actions: ['defineZones(founder, 2) with deterministic lat/lng cells.'],
    checklist: ['§3 land/zones — zones defined'],
    uiShots: ['06-zone-selector-map'],
  },
  {
    id: 'P7',
    title: 'Defense procurement smoke',
    summary:
      'Publish an RFP, external vendor bids, award — exercises third-party appointment path.',
    actions: [
      'joinCitizen(vendor identity).',
      'create_rfp → publish → bid → close → award via procurement extension.',
    ],
    checklist: ['§3 procurement tender → bid → appoint'],
    uiShots: ['07-procurement-rfp-list'],
  },
  {
    id: 'P8',
    title: 'Root handover to Congress',
    summary:
      'Founder transfers root authority to Congress; founder loses direct configure powers.',
    actions: [
      'transfer_root(Congress).',
      'Verify configureGates denied for founder afterward.',
    ],
    checklist: ['§3 founder handover', '§3 ex-founder demoted'],
    uiShots: ['08-post-handover-realm-settings'],
  },
  {
    id: 'P9',
    title: 'Congress advances to beta',
    summary:
      'Congress sets stage beta; deposits lock, membership tax invoices generated.',
    actions: [
      'set_realm_stage(beta) as Congress member.',
      'Verify deposits_locked + tax invoices.',
      'Browser: beta realm_settings + voting filters.',
    ],
    checklist: ['§3 reach critical mass → beta', '§3 deposits locked', '§3 tax invoices'],
    uiShots: ['09-beta-realm-settings', '09-beta-voting-filters', '09-beta-vault-taxes'],
  },
  {
    id: 'P10',
    title: 'Real identity submission & review',
    summary:
      'Sample citizens submit passport identity; Congress registrar approves attestation.',
    actions: [
      'submitIdentity for 5 citizens.',
      'reviewIdentity(Congress, approve).',
    ],
    checklist: ['§3 identity submission + approval'],
    uiShots: ['10-identity-submission', '10-registrar-queue'],
  },
  {
    id: 'P11',
    title: 'Citizen pays tax invoice',
    summary:
      'Mint test tokens (when TOKEN_CANISTER_ID set) and pay pending membership_tax invoice.',
    actions: ['Find pending tax invoice → mint → icrc1_transfer → mark paid.'],
    checklist: ['§3 member pays tax', '§3 treasury balance increases'],
    uiShots: ['11-vault-tax-payment'],
  },
  {
    id: 'P12',
    title: 'Beta→production via Congress vote',
    summary:
      'Production blocked until vote + proving period; Congress approves; realm goes live.',
    actions: [
      'Blocked premature production advance.',
      'approveStage(production) proposal + force-finalize in test mode.',
      'Wait proving period; set_realm_stage(production).',
    ],
    checklist: ['§4 production blocked pre-vote', '§4 Congress approval', '§4 stage = production'],
    uiShots: ['12-production-realm-settings', '12-production-voting-history'],
  },
];

export const AGORA_PHASES = SYNTROPIA_PHASES.map((p) => ({
  ...p,
  summary: p.summary.replace(/Syntropia/g, 'Agora').replace(/open registration/g, 'invitation-only registration'),
}));

export function phasesForCodex(codex) {
  return codex === 'agora' ? AGORA_PHASES : SYNTROPIA_PHASES;
}
