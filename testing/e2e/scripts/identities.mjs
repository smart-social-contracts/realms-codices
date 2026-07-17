/**
 * Deterministic test identities for II-bypass staging realms.
 *
 * Mirrors src/realm_frontend/src/lib/test-identities.js exactly:
 * 32-byte Ed25519 seed = [0xED, 0x57, index (4 bytes LE), 0, …].
 * Indices 0–255 are byte-identical to the original 1-byte layout, so
 * the browser picker's Identity 1–4 map to indices 0–3 here.
 *
 * Roster convention used by the lifecycle suites:
 *   0                      — founder / creator
 *   ADMIN_INDEX_OFFSET+i   — department admins / civil servants (default 10+)
 *   CITIZEN_INDEX_OFFSET+i — bulk citizens (default 1000+)
 */
import { Ed25519KeyIdentity } from '@dfinity/identity';

export const TEST_IDENTITY_MAGIC = [0xed, 0x57];

export function testIdentitySeed(index) {
  if (!Number.isInteger(index) || index < 0 || index > 0xffffffff) {
    throw new Error(`identity index out of range: ${index}`);
  }
  const seed = new Uint8Array(32);
  seed[0] = TEST_IDENTITY_MAGIC[0];
  seed[1] = TEST_IDENTITY_MAGIC[1];
  seed[2] = index & 0xff;
  seed[3] = (index >>> 8) & 0xff;
  seed[4] = (index >>> 16) & 0xff;
  seed[5] = (index >>> 24) & 0xff;
  return seed;
}

const cache = new Map();

/** @returns {Ed25519KeyIdentity} */
export function testIdentity(index) {
  if (!cache.has(index)) {
    cache.set(index, Ed25519KeyIdentity.generate(testIdentitySeed(index)));
  }
  return cache.get(index);
}

export function testPrincipal(index) {
  return testIdentity(index).getPrincipal().toText();
}
