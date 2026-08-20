"""Agora organization seeding (issue #241).

Seeds the template org chart from ``data/departments.json`` as real
Department organizations — policy defaults, a Fund budget envelope,
permissions, staff profiles, Position seats (headcount + salary line),
extension access grants (``extensions``), sidebar hide rules
(``hidden_extensions``), and one multi-use invite code per position so civil
servants can be onboarded with a URL and appointed to their seat on
redemption.

Idempotent: existing departments/profiles/codes are left alone, so re-running
(upgrade, reinstall, admin re-seed) never duplicates or resets creator edits.
"""

from _cdk import ic

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


def _position_specs(spec):
    """Position specs for one department, with legacy ``profiles`` fallback.

    New schema: ``positions: [{title, profile, headcount, salary_amount}]``.
    Old schema: ``profiles: ["judge", ...]`` → one seat per profile.
    """
    positions = spec.get("positions")
    if positions:
        return [
            {
                "title": (p.get("title") or p.get("profile") or "").strip(),
                "profile": (p.get("profile") or p.get("title") or "").strip(),
                "headcount": int(p.get("headcount", 1) or 1),
                "salary_amount": int(p.get("salary_amount", 0) or 0),
                "salary_period": p.get("salary_period", "monthly"),
                "inherit_from_capital": bool(p.get("inherit_from_capital", True)),
            }
            for p in positions
            if (p.get("title") or p.get("profile"))
        ]
    return [
        {
            "title": p,
            "profile": p,
            "headcount": 1,
            "salary_amount": 0,
            "salary_period": "monthly",
            "inherit_from_capital": True,
        }
        for p in spec.get("profiles", [])
    ]


def _apply_target_policy(dept, spec, *, is_new: bool) -> None:
    """Persist ``target_policy`` on Department (issue #301). Never touches live ``policy_*``."""
    target = spec.get("target_policy")
    if not target:
        return
    m = int(target.get("threshold_m", 0) or 0)
    n = int(target.get("threshold_n", 0) or 0)
    q = int(target.get("quorum_percent", 0) or 0)
    if is_new:
        dept.target_policy_threshold_m = m
        dept.target_policy_threshold_n = n
        dept.target_policy_quorum_percent = q
        return
    if not int(getattr(dept, "target_policy_threshold_m", 0) or 0):
        dept.target_policy_threshold_m = m
    if not int(getattr(dept, "target_policy_threshold_n", 0) or 0):
        dept.target_policy_threshold_n = n
    if not int(getattr(dept, "target_policy_quorum_percent", 0) or 0):
        dept.target_policy_quorum_percent = q


def seed_organizations(dept_data, realm):
    """Create Department orgs, funds, permissions, profiles, positions, and invite codes."""
    from ggg import (
        Department,
        Fund,
        FundType,
        Permission,
        RegistrationCode,
        UserProfile,
    )

    # Position entity may be missing on older backends — degrade gracefully.
    try:
        from ggg import Position
    except ImportError:
        Position = None

    # Root org first (idempotent) so authority grants have a grantor.
    try:
        from ggg import ensure_root_org

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
    existing_invites = {}
    for c in RegistrationCode.instances():
        if getattr(c, "department", ""):
            existing_invites[(c.department, c.profile)] = c

    # Existing (extension, department) hide rules — for idempotency.
    existing_hide_rules = set()
    try:
        from ggg import MenuDepartmentVisibility

        for r in MenuDepartmentVisibility.instances():
            dept_name = r.department.name if r.department else ""
            existing_hide_rules.add((r.extension_name, dept_name))
    except ImportError:
        MenuDepartmentVisibility = None

    n_depts = n_profiles = n_positions = n_codes = n_ext_grants = n_hide_rules = 0

    for spec in dept_data.get("departments", []):
        name = (spec.get("name") or "").strip()
        if not name:
            continue

        position_specs = _position_specs(spec)

        # 1. Staff profiles (skip platform-default ones like "admin").
        for pspec in position_specs:
            pname = pspec["profile"]
            if not UserProfile[pname]:
                UserProfile(
                    name=pname,
                    allowed_to=baseline,
                    description=f"{name} staff profile (Agora codex)",
                )
                n_profiles += 1

        # 2. Department org with policy defaults.
        dept = Department[name]
        is_new_dept = not dept
        if is_new_dept:
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
        _apply_target_policy(dept, spec, is_new=is_new_dept)

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

        # 5. Position seats: title + profile + headcount + salary line
        #    (personnel budget planning = headcount x salary_amount).
        for pspec in position_specs:
            if Position is None:
                break
            key = f"{name}/{pspec['title']}"
            existing_pos = Position[key]
            if not existing_pos:
                Position(
                    key=key,
                    title=pspec["title"],
                    description=f"{pspec['title']} at {name} (Agora codex)",
                    department=dept,
                    profile=UserProfile[pspec["profile"]],
                    headcount=pspec["headcount"],
                    salary_amount=pspec["salary_amount"],
                    salary_period=pspec["salary_period"],
                    inherit_from_capital=pspec.get("inherit_from_capital", True),
                    status="open",
                )
                n_positions += 1
            elif getattr(existing_pos, "inherit_from_capital", None) is None:
                existing_pos.inherit_from_capital = pspec.get("inherit_from_capital", True)

        # 6. One multi-use staff invite per position. Redeeming appoints the
        #    redeemer to the seat (join_realm side effect). Pre-existing
        #    (department, profile) invites are kept and backfilled with the
        #    position key so upgrades never invalidate distributed URLs.
        for pspec in position_specs:
            pname = pspec["profile"]
            key = f"{name}/{pspec['title']}"
            existing = existing_invites.get((name, pname))
            if existing is not None:
                if not getattr(existing, "position", ""):
                    existing.position = key
                continue
            RegistrationCode.create(
                user_id="",
                created_by="codex:agora",
                frontend_url=frontend_url,
                expires_in_hours=invite_hours,
                profile=pname,
                max_uses=invite_max_uses,
                department=name,
                position=key,
            )
            n_codes += 1

        # 7. Extension access template (``extensions`` in departments.json):
        #    grant this department's staff access to its domain extensions
        #    via Extension.departments. Grants are additive — admins can
        #    extend or revoke them later in Department Management.
        try:
            from ggg import Extension

            for ext_id in spec.get("extensions", []):
                ext = Extension[ext_id]
                if ext and not any(d.name == name for d in ext.departments):
                    ext.departments.add(dept)
                    n_ext_grants += 1
        except Exception as e:
            ic.print(f"⚠️  extension access seeding failed for {name}: {e}")

        # 8. Sidebar hide rules (``hidden_extensions`` in departments.json):
        #    explicit per-department hide entries (MenuDepartmentVisibility,
        #    visible=False). Default stays visible; only hide rules are seeded.
        if MenuDepartmentVisibility is not None:
            for ext_id in spec.get("hidden_extensions", []):
                if (ext_id, name) in existing_hide_rules:
                    continue
                MenuDepartmentVisibility(
                    extension_name=ext_id, department=dept, visible=False
                )
                n_hide_rules += 1

    # Root gets default manage authority over the freshly seeded orgs.
    try:
        from ggg import grant_root_authority_over_local_orgs

        grant_root_authority_over_local_orgs()
    except Exception as e:
        ic.print(f"⚠️  grant_root_authority_over_local_orgs unavailable: {e}")

    ic.print(
        f"✅ Agora organizations seeded: {n_depts} departments, "
        f"{n_profiles} profiles, {n_positions} positions, {n_codes} invite codes, "
        f"{n_ext_grants} extension grants, {n_hide_rules} hide rules"
    )
