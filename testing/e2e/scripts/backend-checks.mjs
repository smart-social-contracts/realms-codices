#!/usr/bin/env node
/**
 * Backend assertions for codex E2E runs (no dfx required).
 * Usage: node scripts/backend-checks.mjs <realm_backend_canister_id>
 */
import { HttpAgent, Actor } from '@dfinity/agent';
import { IDL } from '@dfinity/candid';
import { Principal } from '@dfinity/principal';

const FILE_REGISTRY = 'iebdk-kqaaa-aaaau-agoxq-cai';
const CODEX_ID = process.env.CODEX_ID || 'agora';

const realmIdl = ({ IDL: idl }) =>
  idl.Service({
    status: idl.Func([], [idl.Text], ['query']),
    get_sidebar_manifests: idl.Func([], [idl.Text], ['query']),
    extension_sync_call: idl.Func(
      [idl.Text, idl.Text, idl.Text],
      [idl.Text],
      ['query'],
    ),
  });

const fileRegistryIdl = ({ IDL: idl }) =>
  idl.Service({
    list_codices: idl.Func([], [idl.Text], ['query']),
    get_file: idl.Func([idl.Text], [idl.Text], ['query']),
  });

async function actor(idlFactory, canisterId) {
  const agent = new HttpAgent({ host: 'https://icp0.io' });
  return Actor.createActor(idlFactory, {
    agent,
    canisterId: Principal.fromText(canisterId),
  });
}

function parseJson(raw) {
  if (typeof raw !== 'string') return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

async function fetchCodexManifest(fileActor, codexId) {
  const listing = parseJson(await fileActor.list_codices());
  const entry = Array.isArray(listing)
    ? listing.find((c) => c.codex_id === codexId)
    : null;
  if (!entry?.latest) return null;
  const resp = parseJson(
    await fileActor.get_file(
      JSON.stringify({
        namespace: `codex/${codexId}/${entry.latest}`,
        path: 'manifest.json',
      }),
    ),
  );
  if (resp?.error || !resp?.content_b64) return null;
  return JSON.parse(Buffer.from(resp.content_b64, 'base64').toString('utf8'));
}

const CORE = [
  'public_dashboard',
  'member_dashboard',
  'realm_settings',
  'extensions_manager',
  'voting',
  'census',
  'admin_dashboard',
  'vault',
  'codex_viewer',
];

async function main() {
  const backendId = process.argv[2] || '335qe-iyaaa-aaaac-bfnwa-cai';
  const realm = await actor(realmIdl, backendId);
  const files = await actor(fileRegistryIdl, FILE_REGISTRY);

  const statusWrap = parseJson(await realm.status());
  const status = statusWrap?.data?.status ?? {};
  const manifest = await fetchCodexManifest(files, CODEX_ID);

  const sidebarRaw = parseJson(await realm.get_sidebar_manifests());
  const sidebarParsed = typeof sidebarRaw === 'string' ? parseJson(sidebarRaw) : sidebarRaw;
  const manifests = sidebarParsed?.manifests ?? [];
  const installed = new Map(
    (Array.isArray(manifests) ? manifests : Object.values(manifests)).map((m) => [
      m.id || m.name,
      m.version,
    ]),
  );

  let stage = null;
  let departments = null;
  try {
    stage = parseJson(
      await realm.extension_sync_call('realm_settings', 'get_realm_stage', '{}'),
    );
  } catch (e) {
    stage = { error: String(e) };
  }
  try {
    departments = parseJson(
      await realm.extension_sync_call('access_manager', 'list_departments', '{}'),
    );
  } catch (e) {
    departments = { error: String(e) };
  }

  const deps = manifest?.dependencies ?? [];
  const missingCore = CORE.filter((id) => !installed.has(id));
  const missingDeps = deps.filter((id) => !installed.has(id));

  const report = {
    backendId,
    codex: { id: CODEX_ID, published: manifest?.version, dependencies: deps },
    realm: {
      name: status.realm_name,
      open_registration: status.open_registration,
      organizations_count: status.organizations_count,
      users_count: status.users_count,
      stage: status.realm_stage,
      manifesto: status.realm_manifesto,
      test_mode: status.test_mode,
      test_mode_ii_bypass: status.test_mode_ii_bypass,
      test_mode_user_self_registration: status.test_mode_user_self_registration,
    },
    codex_registration_policy: manifest?.onboarding?.registration?.open_registration,
    u3: {
      installed_count: installed.size,
      installed: Object.fromEntries([...installed.entries()].sort()),
      missing_core: missingCore,
      missing_deps: missingDeps,
    },
    u4_get_realm_stage: stage,
    departments: departments,
  };

  console.log(JSON.stringify(report, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
