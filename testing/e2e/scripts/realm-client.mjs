/**
 * Node-side client for realm backend canisters (lifecycle E2E, issue #253).
 *
 * Uses the generated candid bindings from src/declarations/realm_backend so
 * update calls (join_realm, extension_sync_call, refresh_invoice) are signed
 * with the deterministic test identities from ./identities.mjs.
 */
import { createHash } from 'node:crypto';
import { HttpAgent, Actor } from '@dfinity/agent';
import { Principal } from '@dfinity/principal';
import { idlFactory as realmIdl } from '../../../../src/declarations/realm_backend/realm_backend.did.js';

const HOST = process.env.IC_HOST || 'https://icp0.io';

export function sha256Hex(text) {
  return createHash('sha256').update(text).digest('hex');
}

export async function realmActor(canisterId, identity) {
  const agent = await HttpAgent.create({ host: HOST, identity });
  return Actor.createActor(realmIdl, {
    agent,
    canisterId: Principal.fromText(canisterId),
  });
}

// Minimal ICRC-1 + test-mode mint interface of ic-tokens token_backend.
const tokenIdl = ({ IDL }) => {
  const Account = IDL.Record({
    owner: IDL.Principal,
    subaccount: IDL.Opt(IDL.Vec(IDL.Nat8)),
  });
  return IDL.Service({
    icrc1_balance_of: IDL.Func([Account], [IDL.Nat], ['query']),
    icrc1_decimals: IDL.Func([], [IDL.Nat8], ['query']),
    icrc1_fee: IDL.Func([], [IDL.Nat], ['query']),
    mint: IDL.Func(
      [IDL.Record({ to: Account, amount: IDL.Nat })],
      [
        IDL.Record({
          success: IDL.Bool,
          new_balance: IDL.Opt(IDL.Nat),
          error: IDL.Opt(IDL.Text),
          block_index: IDL.Opt(IDL.Nat),
        }),
      ],
      [],
    ),
    icrc1_transfer: IDL.Func(
      [
        IDL.Record({
          from_subaccount: IDL.Opt(IDL.Vec(IDL.Nat8)),
          to: Account,
          amount: IDL.Nat,
          fee: IDL.Opt(IDL.Nat),
          memo: IDL.Opt(IDL.Vec(IDL.Nat8)),
          created_at_time: IDL.Opt(IDL.Nat),
        }),
      ],
      [
        IDL.Record({
          success: IDL.Bool,
          block_index: IDL.Opt(IDL.Nat),
          error: IDL.Opt(IDL.Text),
        }),
      ],
      [],
    ),
  });
};

export async function tokenActor(canisterId, identity) {
  const agent = await HttpAgent.create({ host: HOST, identity });
  return Actor.createActor(tokenIdl, {
    agent,
    canisterId: Principal.fromText(canisterId),
  });
}

function tryJson(raw) {
  if (typeof raw !== 'string') return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

/** extension_sync_call wrapper — returns the parsed extension response. */
export async function extCall(actor, extension, method, args = {}) {
  const res = await actor.extension_sync_call(
    extension,
    method,
    typeof args === 'string' ? args : JSON.stringify(args),
  );
  if (!res.success) {
    return { success: false, error: String(res.response) };
  }
  const parsed = tryJson(res.response);
  return typeof parsed === 'object' && parsed !== null
    ? parsed
    : { success: true, raw: parsed };
}

/** Realm status() — returns the StatusRecord or throws. */
export async function realmStatus(actor) {
  const res = await actor.status();
  if (!res.success || !('status' in res.data)) {
    throw new Error(`status() failed: ${JSON.stringify(res.data)}`);
  }
  return res.data.status;
}

/**
 * join_realm as the actor's identity.
 * inviteCode is the *plaintext* code (or test-mode literal like "admin");
 * pass '' for codeless open registration.
 * Returns {ok, alreadyMember, error, raw}.
 */
export async function joinRealm(actor, inviteCode = '', preferredQuarter = '') {
  const checksum = inviteCode ? sha256Hex(inviteCode) : '';
  const res = await actor.join_realm('', preferredQuarter, checksum);
  if (res.success) return { ok: true, raw: res.data };
  const error =
    'error' in res.data ? String(res.data.error) : JSON.stringify(res.data);
  const alreadyMember = /already/i.test(error);
  return { ok: alreadyMember, alreadyMember, error, raw: res.data };
}

/** get_my_invoices as the actor's identity — array of invoice objects. */
export async function myInvoices(actor) {
  const res = await actor.get_my_invoices();
  if (!res.success || !('objectsList' in res.data)) return [];
  return res.data.objectsList.objects.map(tryJson);
}
