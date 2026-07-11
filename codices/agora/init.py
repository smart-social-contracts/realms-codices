"""Agora codex initialization.

Agora is an *incumbent migration*: an existing public administration replacing
its IT with Realms GOS. Onboarding is by registration code / bulk import (no ZK
passport). This init:

1. Writes the codex configuration into ``Realm.manifest_data`` so the backend
   and the (input-driven) public dashboard can read it.
2. Seeds the template org chart from ``departments.json`` as **real
   Department organizations** — policy defaults, a Fund budget envelope,
   permissions, staff profiles, and one multi-use invite code per
   (department, profile) so civil servants can be onboarded with a URL
   (issue #241).

Seeding is idempotent: existing departments/profiles/codes are left alone, so
re-running init (upgrade, reinstall) never duplicates or resets creator edits.

Zone and License entity creation is intentionally deferred (creator-triggered)
to avoid hitting the IC 40B-instruction per-message limit on canisters with
large amounts of existing state.
"""

from _cdk import ic
from ggg import Realm
import json
import os

_DIR = os.path.dirname(__file__)


def _load_json(filename):
    path = os.path.join(_DIR, filename)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        ic.print(f"⚠️  Could not load {filename}: {e}")
        return None


# Baseline operations for seeded staff profiles (literal Operations values —
# stable platform strings). Domain powers (member.import, treasury.send, …)
# live on the Department as Permission grants; the profile only needs
# self-service + extension access.
_STAFF_BASELINE_OPS = [
    "self.join",
    "self.update_public_profile",
    "self.update_private_data",
    "self.change_quarter",
    "extension.sync_call",
    "extension.async_call",
]


def seed_organizations(dept_data, realm):
    """Create Department orgs, funds, permissions, profiles, and invite codes."""
    from ggg import (
        Department,
        Fund,
        FundType,
        Permission,
        RegistrationCode,
        UserProfile,
    )

    # Root org first (idempotent) so authority grants have a grantor.
    try:
        from core.org_policy import ensure_root_org

        ensure_root_org()
    except Exception as e:
        ic.print(f"⚠️  ensure_root_org unavailable: {e}")

    invite_cfg = dept_data.get("invite", {}) or {}
    invite_hours = int(invite_cfg.get("expires_in_hours", 720))
    invite_max_uses = int(invite_cfg.get("max_uses", 100))

    frontend_id = getattr(realm, "frontend_canister_id", "") or ""
    frontend_url = f"https://{frontend_id}.icp0.io" if frontend_id else ""

    baseline = ",".join(_STAFF_BASELINE_OPS)

    # Existing (department, profile) invite pairs — for idempotency.
    existing_invites = set()
    for c in RegistrationCode.instances():
        if getattr(c, "department", ""):
            existing_invites.add((c.department, c.profile))

    n_depts = n_profiles = n_codes = 0

    for spec in dept_data.get("departments", []):
        name = (spec.get("name") or "").strip()
        if not name:
            continue

        # 1. Staff profiles (skip platform-default ones like "admin").
        for pname in spec.get("profiles", []):
            if not UserProfile[pname]:
                UserProfile(
                    name=pname,
                    allowed_to=baseline,
                    description=f"{name} staff profile (Agora codex)",
                )
                n_profiles += 1

        # 2. Department org with policy defaults.
        dept = Department[name]
        if not dept:
            policy = spec.get("policy", {}) or {}
            dept = Department(
                name=name,
                description=spec.get("description", ""),
                is_root=False,
                policy_threshold_m=int(policy.get("threshold_m", 1)),
                policy_threshold_n=int(policy.get("threshold_n", 1)),
                policy_quorum_percent=int(policy.get("quorum_percent", 0)),
            )
            n_depts += 1

        # 3. Budget envelope (Fund link).
        fund_code = (spec.get("fund_code") or "").strip()
        if fund_code and not dept.fund:
            fund = Fund[fund_code[:16]]
            if not fund:
                fund = Fund(
                    code=fund_code[:16],
                    name=f"{name} Fund",
                    fund_type=FundType.SPECIAL_REVENUE,
                    description=f"Budget envelope for {name} (Agora codex)",
                )
            dept.fund = fund

        # 4. Department permissions.
        have = {p.name for p in dept.permissions}
        for perm_name in spec.get("permissions", []):
            if perm_name in have:
                continue
            perm = Permission[perm_name]
            if not perm:
                perm = Permission(name=perm_name)
            dept.permissions.add(perm)

        # 5. One multi-use staff invite per (department, profile).
        for pname in spec.get("profiles", []):
            if (name, pname) in existing_invites:
                continue
            RegistrationCode.create(
                user_id="",
                created_by="codex:agora",
                frontend_url=frontend_url,
                expires_in_hours=invite_hours,
                profile=pname,
                max_uses=invite_max_uses,
                department=name,
            )
            n_codes += 1

        # 6. Department staff see the migration console in their sidebar
        #    (extension installed beforehand via codex dependencies).
        try:
            from ggg import Extension

            console_ext = Extension["migration_console"]
            if console_ext and not any(
                d.name == name for d in console_ext.departments
            ):
                console_ext.departments.add(dept)
        except Exception:
            pass

    # Root gets default manage authority over the freshly seeded orgs.
    try:
        from core.org_policy import grant_root_authority_over_local_orgs

        grant_root_authority_over_local_orgs()
    except Exception as e:
        ic.print(f"⚠️  grant_root_authority_over_local_orgs unavailable: {e}")

    ic.print(
        f"✅ Agora organizations seeded: {n_depts} departments, "
        f"{n_profiles} profiles, {n_codes} invite codes"
    )


realm = list(Realm.instances())[0] if Realm.instances() else None
if realm:
    manifest = _load_json("manifest.json") or {}

    # Reference data files (JSON) shipped with the codex.
    departments = _load_json(manifest.get("data_files", {}).get("departments", "departments.json"))

    # Lifecycle metrics consumed by the public dashboard.
    lifecycle = dict(manifest.get("lifecycle", {}))
    population_target = lifecycle.get("population_target", 0)
    lifecycle.setdefault("critical_mass", population_target)

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars).
    # Store only what the backend and public dashboard read.
    department_names = [d.get("name", "") for d in (departments or {}).get("departments", [])]

    realm_manifest = {
        "entity_method_overrides": manifest.get("entity_method_overrides", []),
        "onboarding": manifest.get("onboarding", {}),
        "lifecycle": lifecycle,
        "dashboard": manifest.get("dashboard", {}),
        "dependencies": manifest.get("dependencies", []),
        "departments": department_names,
    }

    realm.manifest_data = json.dumps(realm_manifest)

    if manifest.get("name"):
        realm.name = manifest["name"]
    if manifest.get("manifesto"):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message"):
        realm.welcome_message = manifest["welcome_message"]

    # Seed the org chart as real organizations (issue #241).
    if departments:
        try:
            seed_organizations(departments, realm)
        except Exception as e:
            import traceback

            ic.print(f"❌ Organization seeding failed: {e}\n{traceback.format_exc()}")

    ic.print("✅ Agora (incumbent) manifest_data written")
else:
    ic.print("❌ No Realm found")
