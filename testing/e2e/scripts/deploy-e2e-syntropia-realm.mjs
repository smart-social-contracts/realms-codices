#!/usr/bin/env node
/**
 * Queue a fresh Syntropia staging realm for lifecycle E2E (II bypass on).
 * Prints JSON with backend_canister_id and realm_path on success.
 */
import { execSync } from 'node:child_process';
import fs from 'node:fs';

const REGISTRY = process.env.REGISTRY_CANISTER || '7wzxh-wyaaa-aaaau-aggyq-cai';
const INSTALLER = process.env.INSTALLER_CANISTER || 'lusjm-wqaaa-aaaau-ago7q-cai';
const REALMS_DIR = process.env.REALMS_DIR || '/srv/dev/realms';

const stamp = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
const realmName = process.env.E2E_REALM_NAME || `E2E-Syntropia-${stamp}`;
const slug = realmName.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 48);

const manifest = {
  name: realmName,
  network: 'staging',
  deploy_mode: 'install',
  deploy_scope: 'both',
  deploy_version: 'main',
  realm: {
    name: realmName,
    display_name: realmName,
    manifesto: `Automated lifecycle E2E realm (${stamp})`,
    welcome_message: `Welcome to ${realmName}`,
    open_registration: true,
    extensions: [],
    codex: { package: 'syntropia', version: 'latest' },
    config_overrides: {
      lifecycle: { critical_mass: 25, population_target: 25 },
      governance: { voting_window_days: 0.001 },
    },
  },
  casals: {
    section: 'Deployments',
    stand: slug,
    backend_wasm_key: 'realm-backend',
    frontend_wasm_key: 'realm-assets',
  },
  infra: {
    file_registry_canister_id: 'iebdk-kqaaa-aaaau-agoxq-cai',
    marketplace_canister_id: 'jji3o-uyaaa-aaaah-qreja-cai',
    ii_derivation_origin: 'https://staging.gos.earth',
  },
  test_flags: {
    test_mode: true,
    user_self_registration: true,
    demo_data: false,
    ii_bypass: true,
    skip_terms: true,
    skip_passport_zkproof: true,
  },
  federation: {
    slug,
    portal_url: `https://staging.gos.earth/r/${slug}`,
  },
};

function dfxCall(canister, method, argJson) {
  const env = { ...process.env, TERM: 'xterm', DFX_WARNING: '-mainnet_plaintext_identity' };
  const py = `
import json, subprocess, sys
arg = json.dumps(${JSON.stringify(argJson)})
subprocess.run(
    ['dfx','canister','--network','ic','call',${JSON.stringify(canister)},${JSON.stringify(method)}, f'({arg})'],
    cwd=${JSON.stringify(REALMS_DIR)}, check=True, env={**dict(__import__('os').environ), 'TERM':'xterm', 'DFX_WARNING':'-mainnet_plaintext_identity'}
)
`;
  return execSync(`python3 -c ${JSON.stringify(py)}`, { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });
}

function parseOkJson(stdout) {
  const ok = stdout.match(/Ok = "(.*)"\s*\n\s*\}/s);
  if (ok) return JSON.parse(ok[1].replace(/\\"/g, '"'));
  const plain = stdout.match(/\(\s*"(\\{.*\\})"\s*,?\s*\)/s) || stdout.match(/\(\s*"(\{.*\})"\s*,?\s*\)/s);
  if (plain) {
    const raw = plain[1].replace(/\\"/g, '"');
    return JSON.parse(raw);
  }
  throw new Error(`Cannot parse:\n${stdout.slice(0, 800)}`);
}

function parseJobStatus(stdout) {
  try {
    return parseOkJson(stdout);
  } catch {
    const pick = (key) => {
      const m = stdout.match(new RegExp(`${key} = "([^"]*)"`));
      return m ? m[1] : '';
    };
    return {
      success: /variant \{\s*Ok/.test(stdout) || stdout.includes('status ='),
      status: pick('status'),
      backend_canister_id: pick('backend_canister_id'),
      frontend_canister_id: pick('frontend_canister_id'),
      realm_name: pick('realm_name'),
      error: pick('error'),
      job_id: pick('job_id'),
    };
  }
}

function callJobStatus(jobId) {
  const env = { ...process.env, TERM: 'xterm', DFX_WARNING: '-mainnet_plaintext_identity' };
  const out = execSync(
    `dfx canister --network ic call ${INSTALLER} get_deployment_job_status '${`("${jobId}")`}'`,
    { cwd: REALMS_DIR, encoding: 'utf8', env, maxBuffer: 10 * 1024 * 1024 },
  );
  return parseJobStatus(out);
}

console.error(`Queueing realm deploy: ${realmName}`);
const manifestJson = JSON.stringify(manifest).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
const env = { ...process.env, TERM: 'xterm', DFX_WARNING: '-mainnet_plaintext_identity' };
const deployOut = execSync(
  `dfx canister --network ic call ${REGISTRY} request_deployment '${`("${manifestJson}")`}'`,
  { cwd: REALMS_DIR, encoding: 'utf8', env, maxBuffer: 10 * 1024 * 1024 },
);
const deployRes = parseOkJson(deployOut);
if (!deployRes?.success) {
  console.error(JSON.stringify(deployRes));
  process.exit(1);
}
const jobId = deployRes.job_id;
console.error(`Job queued: ${jobId}`);

const deadline = Date.now() + parseInt(process.env.DEPLOY_MAX_WAIT || '900', 10) * 1000;
let info = null;
while (Date.now() < deadline) {
  info = callJobStatus(jobId);
  console.error(`  status: ${info?.status}`);
  if (['completed', 'failed', 'failed_verification', 'cancelled'].includes(info?.status)) break;
  execSync('sleep 15');
}

if (info?.status !== 'completed') {
  console.error(JSON.stringify(info, null, 2));
  process.exit(1);
}

const out = {
  job_id: jobId,
  realm_name: realmName,
  slug,
  backend_canister_id: info.backend_canister_id || info.realm_backend_id,
  frontend_canister_id: info.frontend_canister_id,
  realm_path: `/r/${slug}`,
  portal_url: manifest.federation.portal_url,
};
fs.writeFileSync('/tmp/e2e-syntropia-realm.json', JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
