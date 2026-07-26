"""Syntropia codex — hook API entry point (codex_api_version 1, issue #244).

Syntropia is a *greenfield* sovereign smart city built from scratch. New
citizens are onboarded with a ZK passport, pay a deposit (a house in a zone),
and submit Know-Your-Citizen data before go-live. Until the realm reaches
production, member voting is not executable — only admins can make
fundamental changes.

The codex integrates with the core exclusively through the hooks defined
here — no ``entity_method_overrides``, no exec'd ``init.py``.

Hooks implemented:
  get_config          — manifest config blocks (single source of realm policy),
                        with deploy-time lifecycle overrides (issue #253)
  init                — post-install realm setup: manifest_data, server-side
                        registration-policy enforcement, org seeding
  seed                — idempotent org-chart re-seed (admin re-run)
  on_user_register    — greenfield onboarding: deposit invoice + welcome steps
  on_invoice_accounting — realm-specific invoice journal policy
  on_stage_change     — beta: tax/membership invoicing starts + citizens are
                        asked to submit their actual identity (issue #253)

Extension methods (extension_sync_call "syntropia"):
  run_payroll               — record salary payments from department funds
  submit_identity           — citizen submits real identity (simple mock;
                              reviewed by the Citizenship & Identity dept)
  review_identity           — registrar approves/rejects a submission
  list_identity_attestations — registrar/admin listing
"""

import json
import os

from _cdk import ic

REALM_NAME = "Syntropia"

_DIR = os.path.dirname(__file__)

# Manifest keys that are packaging metadata, not realm configuration.
_NON_CONFIG_KEYS = {
    "id", "name", "version", "kind", "codex_api_version", "description",
    "author", "dependencies", "extension_overrides", "data_files",
    "profiles", "categories", "icon", "show_in_sidebar", "sidebar_label",
    "doc_url", "permissions", "parameters",
}


def _deep_merge(base: dict, overrides: dict) -> dict:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _manifest_overrides() -> dict:
    """Per-deployment overrides stored in ``Realm.manifest_data``.

    ``config_overrides`` holds the wizard's codex-parameter choices (issue
    #253); ``lifecycle_overrides`` is the older lifecycle-only mechanism,
    kept for realms patched before config_overrides existed.
    """
    try:
        realm = _realm()
        raw = getattr(realm, "manifest_data", "") or "{}" if realm else "{}"
        data = json.loads(raw) or {}
    except Exception as e:
        ic.print(f"⚠️  Syntropia: could not read manifest_data overrides: {e}")
        return {}
    overrides = {}
    legacy = data.get("lifecycle_overrides")
    if isinstance(legacy, dict) and legacy:
        overrides["lifecycle"] = dict(legacy)
    general = data.get("config_overrides")
    if isinstance(general, dict) and general:
        overrides = _deep_merge(overrides, general)
    return overrides


def _config() -> dict:
    """Effective codex configuration: manifest blocks with per-deployment
    overrides applied. Use this (not ``_manifest()``) wherever fees,
    lifecycle, governance, or membership values are read."""
    manifest = _manifest()
    overrides = _manifest_overrides()
    return _deep_merge(manifest, overrides) if overrides else manifest


def _manifest() -> dict:
    # Installed layout: manifest.json next to entry.py (backend/ prefix is
    # stripped at install). Source layout (local tests): one level up.
    for candidate in (
        os.path.join(_DIR, "manifest.json"),
        os.path.join(os.path.dirname(_DIR), "manifest.json"),
    ):
        try:
            with open(candidate, "r") as f:
                return json.loads(f.read())
        except FileNotFoundError:
            continue
        except Exception as e:
            ic.print(f"⚠️  Syntropia: could not load manifest.json: {e}")
            return {}
    ic.print("⚠️  Syntropia: manifest.json not found")
    return {}


def _load_data(filename):
    path = os.path.join(_DIR, filename)
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except Exception as e:
        ic.print(f"⚠️  Syntropia: could not load {filename}: {e}")
        return None


def _realm():
    from ggg import Realm

    realms = Realm.instances()
    return realms[0] if realms else None


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------


def get_config(args: str) -> str:
    """Realm configuration blocks declared by this codex.

    Deploy/test-time parameterization (issue #253): per-deployment values —
    the wizard's codex-parameter choices in ``config_overrides`` or an
    admin's legacy ``lifecycle_overrides`` patch (via realm_settings
    ``patch_manifest_data``) — are applied over the codex-declared blocks,
    so e.g. ``critical_mass``, ``beta_proving_days``, or governance fees can
    be tuned per realm without republishing the codex.
    """
    config = {k: v for k, v in _config().items() if k not in _NON_CONFIG_KEYS}
    return json.dumps(config)


def init(args: str) -> str:
    """Post-install realm setup (idempotent).

    Writes the lean config summary into ``Realm.manifest_data`` (legacy
    readers), enforces the codex's registration policy server-side, fills
    empty identity fields, and seeds the org chart.
    """
    realm = _realm()
    if not realm:
        return json.dumps({"success": False, "error": "No Realm found"})

    manifest = _manifest()
    departments = _load_data(
        manifest.get("data_files", {}).get("departments", "data/departments.json")
    )

    # Lifecycle: seed the metrics the public dashboard reads
    # (countdown, citizen counter, critical-mass threshold).
    lifecycle = dict(manifest.get("lifecycle", {}))
    lifecycle.setdefault("total_deposits", 0)
    lifecycle.setdefault("deposits_locked", False)
    lifecycle.setdefault("land_acquired", False)
    lifecycle.setdefault("infrastructure_ready", False)
    lifecycle.setdefault("providers_ready", False)

    # Keep manifest_data lean (Realm.manifest_data is capped at 4096 chars).
    department_names = [
        d.get("name", "") for d in (departments or {}).get("departments", [])
    ]

    realm_manifest = {
        "onboarding": manifest.get("onboarding", {}),
        "lifecycle": lifecycle,
        "dashboard": manifest.get("dashboard", {}),
        "dependencies": manifest.get("dependencies", []),
        "governance": manifest.get("governance", {}),
        "departments": department_names,
    }
    # Preserve runtime keys that don't belong to the codex (per-deployment
    # parameter overrides, casals autoscale config) — init may re-run after
    # they were written.
    try:
        existing = json.loads(getattr(realm, "manifest_data", "") or "{}") or {}
        for key in ("config_overrides", "lifecycle_overrides", "casals"):
            if key in existing and key not in realm_manifest:
                realm_manifest[key] = existing[key]
    except Exception:
        pass
    realm.manifest_data = json.dumps(realm_manifest)

    # Greenfield realms begin in alpha (gathering founding citizens).
    if not getattr(realm, "status", None):
        realm.status = "alpha"

    # The registration model is part of the codex's governance design —
    # enforce it server-side so a stale or broken wizard can never produce
    # a realm that contradicts its codex (issue #244).
    registration = (manifest.get("onboarding", {}) or {}).get("registration", {}) or {}
    if "open_registration" in registration:
        realm.open_registration = bool(registration["open_registration"])
        ic.print(
            f"✅ Registration policy enforced: open_registration={realm.open_registration}"
        )

    # Identity fields are the creator's, not the codex's: fill them only
    # when the wizard left them empty — never overwrite a chosen realm name.
    if manifest.get("name") and not getattr(realm, "name", ""):
        realm.name = manifest["name"]
    if manifest.get("manifesto") and not getattr(realm, "manifesto", ""):
        realm.manifesto = manifest["manifesto"]
    if manifest.get("welcome_message") and not getattr(realm, "welcome_message", ""):
        realm.welcome_message = manifest["welcome_message"]

    seed_result = json.loads(seed(args))
    justice_result = json.loads(seed_justice(args))

    ic.print("✅ Syntropia (greenfield) init complete")
    return json.dumps({
        "success": True,
        "codex": "syntropia",
        "seeded": seed_result.get("success", False),
        "justice_seeded": justice_result.get("success", False),
    })


def seed(args: str) -> str:
    """Seed the org chart as real organizations (idempotent, issues #241/#244)."""
    realm = _realm()
    if not realm:
        return json.dumps({"success": False, "error": "No Realm found"})

    manifest = _manifest()
    departments = _load_data(
        manifest.get("data_files", {}).get("departments", "data/departments.json")
    )
    if not departments:
        return json.dumps({"success": False, "error": "departments data file missing"})

    try:
        try:
            from .org_seeding import seed_organizations  # installed (package)
        except ImportError:
            from org_seeding import seed_organizations  # local test (flat path)

        seed_organizations(departments, realm)
        return json.dumps({"success": True})
    except Exception as e:
        import traceback

        ic.print(f"❌ Organization seeding failed: {e}\n{traceback.format_exc()}")
        return json.dumps({"success": False, "error": str(e)})


def seed_justice(args: str) -> str:
    """Seed the template court hierarchy + justice license (idempotent).

    Quarter-scoped courts are created on every canister; capital-scoped ones
    only on the capital (quarter self-bootstrap re-runs this via codex init).
    """
    realm = _realm()
    if not realm:
        return json.dumps({"success": False, "error": "No Realm found"})

    manifest = _manifest()
    data_files = manifest.get("data_files", {})
    template = _load_data(data_files.get("justice", "data/justice.json"))
    if not template:
        return json.dumps({"success": False, "error": "justice data file missing"})
    license_data = _load_data(
        data_files.get("justice_license", "data/justice_license.json")
    )

    try:
        from ggg import seed_justice_template
    except ImportError:
        # Older realm backend without the seeding helper: degrade gracefully
        # so init still succeeds (courts can be created via justice_litigation).
        ic.print("⚠️  Syntropia: backend has no seed_justice_template, skipping court seeding")
        return json.dumps({"success": False, "error": "seed_justice_template unavailable"})

    try:
        result = seed_justice_template(template, license_data=license_data, realm=realm)
        ic.print(f"✅ Justice seeding: {result}")
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        import traceback

        ic.print(f"❌ Justice seeding failed: {e}\n{traceback.format_exc()}")
        return json.dumps({"success": False, "error": str(e)})


def on_user_register(args: str) -> str:
    """Greenfield onboarding — deposit invoice (*a house in a zone*) plus the
    three-step welcome message (passport, deposit, Know-Your-Citizen)."""
    from ggg import Invoice, Notification, User
    from ic_basilisk_toolkit.date_utils import epoch_to_datetime_str, ic_time_to_epoch

    try:
        params = json.loads(args) if args else {}
        user = User[params.get("user_id", "")]
        if not user:
            return json.dumps({"success": False, "error": "user not found"})

        manifest = _config()
        from invoice_currency import invoice_currency

        currency = invoice_currency(manifest)
        lifecycle = manifest.get("lifecycle", {})
        deposit = manifest.get("fees", {}).get(
            "deposit", lifecycle.get("deposit_amount", 0.01)
        )
        deposit_label = lifecycle.get("deposit_label", "a house in a zone")
        validity_days = manifest.get("membership", {}).get("invoice_validity_days", 30)

        now_epoch = ic_time_to_epoch(ic.time())
        due_date = epoch_to_datetime_str(
            now_epoch + validity_days * 86400
        ).replace(" ", "T")

        # Deposit invoice — secures the citizen's house in a zone.
        invoice = Invoice(
            amount=deposit,
            currency=currency,
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="deposit invoice - a house in a zone",
        )

        Notification(
            topic="welcome",
            title=f"Welcome to {REALM_NAME}!",
            message=(
                f"Welcome to **{REALM_NAME}**, a brand-new sovereign smart city. "
                f"To become an active citizen, complete three steps:\n\n"
                f"1. **Verify your identity** via ZK Passport (*Passport Verification* extension)\n"
                f"2. **Pay your deposit** — {deposit_label} — `{deposit} {currency}` from the *Invoices* section\n"
                f"3. **Submit your Know-Your-Citizen data** before the city goes live\n\n"
                f"The **AI Assistant** can guide you through every step."
            ),
            sender="Administration",
            recipient=user.id,
            user=user,
            read=False,
            icon="shield_check",
            href="/extensions/member_dashboard",
            color="green",
            metadata=f"invoice_id:{invoice.id}",
            timestamp_created=epoch_to_datetime_str(now_epoch)[:16],
        )

        ic.print(
            f"Syntropia: created deposit invoice #{invoice.id} "
            f"({deposit} {currency}) for new citizen {user.id}"
        )
        return json.dumps({"success": True, "invoice_id": invoice.id})

    except Exception as e:
        ic.print(f"Error in Syntropia on_user_register: {e}")
        return json.dumps({"success": False, "error": str(e)})


def on_invoice_accounting(args: str) -> str:
    """Book an invoice event according to Syntropia's accounting policy."""
    try:
        params = json.loads(args) if args else {}
        invoice_id = (params.get("invoice_id") or "").strip()
        event = (params.get("event") or "").strip().lower()
        if not invoice_id:
            return json.dumps({"success": False, "error": "invoice_id is required"})

        try:
            from .invoice_accounting import book_invoice_event
        except ImportError:
            from invoice_accounting import book_invoice_event

        return json.dumps(book_invoice_event(invoice_id, event))
    except Exception as e:
        ic.print(f"Error in Syntropia on_invoice_accounting: {e}")
        return json.dumps({"success": False, "error": str(e)})


def on_federation_message(args: str) -> str:
    """Handle non-reserved federation topics (realms issue #263).

    Args JSON: ``{topic, source, body}`` — ``source`` is the sending canister
    id, already authenticated by core as a federation member. Value never
    moves through these messages; they carry claims/orders/receipts verified
    against the shared ICRC-1 ledgers.

    Topics:
      ping       liveness echo proving codex-level dispatch works end-to-end
      tax.remit  a quarter reports a tax remittance it paid on the ledger to
                 the capital treasury; the capital records the receipt
    """
    try:
        params = json.loads(args) if args else {}
        topic = (params.get("topic") or "").strip()
        source = (params.get("source") or "").strip()
        body = params.get("body") or {}

        if topic == "ping":
            return json.dumps({"success": True, "pong": REALM_NAME})

        if topic == "tax.remit":
            return json.dumps(_handle_tax_remit(source, body))

        return json.dumps({
            "success": False,
            "error": f"Syntropia: no handler for federation topic '{topic}'",
        })
    except Exception as e:
        ic.print(f"Error in Syntropia on_federation_message: {e}")
        return json.dumps({"success": False, "error": str(e)})


def _handle_tax_remit(source: str, body: dict) -> dict:
    """Record a quarter's tax remittance receipt on the capital.

    Record-only: the actual value moved on the shared ledger (quarter treasury
    → capital treasury); this books the claim so consolidated reporting can
    reconcile it against the ledger indexer.
    """
    realm = _realm()
    if realm is None or bool(getattr(realm, "is_quarter", False)):
        return {"success": False, "error": "tax.remit is handled by the capital only"}

    tx_id = (str(body.get("tx_id") or "")).strip()
    period = (str(body.get("period") or "")).strip()
    instrument = (str(body.get("instrument") or "")).strip()
    try:
        amount = int(body.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    if not tx_id or amount <= 0:
        return {"success": False, "error": "tax.remit requires tx_id and a positive amount"}

    from ggg import Transfer

    receipt_id = f"fedtax-{source}-{tx_id}"
    if Transfer[receipt_id] is not None:
        return {"success": True, "receipt": receipt_id, "duplicate": True}

    Transfer(
        id=receipt_id,
        principal_from=source,
        principal_to=str(ic.id()),
        instrument=instrument,
        amount=amount,
        status="reported",
        tags=f"federation:tax_remit,period:{period}" if period else "federation:tax_remit",
    )
    ic.print(f"✅ Syntropia: recorded tax remittance {receipt_id} ({amount} {instrument})")
    return {"success": True, "receipt": receipt_id, "amount": amount}


# ---------------------------------------------------------------------------
# Beta transition: billing, payroll, real-identity submission (issue #253)
# ---------------------------------------------------------------------------


def _lifecycle_billing():
    # Prefer the top-level sibling module — the runtime loader only preloads
    # backend/*.py, not backend/modules/*.py (see runtime_extensions._load_module).
    try:
        from . import lifecycle_billing  # installed (package sibling)
    except ImportError:
        try:
            import lifecycle_billing  # local test (flat path)
        except ImportError:
            from modules import lifecycle_billing  # source-tree fallback
    return lifecycle_billing


def on_stage_change(args: str) -> str:
    """React to lifecycle transitions (issue #253).

    Entering **beta** starts the money flow (tax/membership invoices,
    payroll baseline) and asks every citizen to submit their *actual*
    identity — beyond the anonymous ZK passport proof — to the
    Citizenship & Identity department.
    """
    try:
        params = json.loads(args) if args else {}
        to_stage = (params.get("to_stage") or "").strip().lower()
        if to_stage != "beta":
            return json.dumps({"success": True, "skipped": f"no action for {to_stage}"})

        manifest = _config()
        billing = _lifecycle_billing()
        invoices = billing.issue_membership_invoices(manifest, REALM_NAME)
        payroll = billing.run_payroll(manifest, REALM_NAME)
        notified = _request_identity_submissions()

        return json.dumps({
            "success": True,
            "invoiced": invoices.get("invoiced", 0),
            "payroll_payments": len(payroll.get("payments", [])),
            "identity_requests": notified,
        })
    except Exception as e:
        ic.print(f"Error in Syntropia on_stage_change: {e}")
        return json.dumps({"success": False, "error": str(e)})


def _request_identity_submissions() -> int:
    """Notify every citizen to submit their real identity (beta requirement)."""
    from ggg import Notification
    from ic_basilisk_toolkit.date_utils import epoch_to_datetime_str, ic_time_to_epoch

    from ggg import iter_users, user_has_profile

    now_epoch = ic_time_to_epoch(ic.time())
    notified = 0
    for user in iter_users():
        if not user_has_profile(user, "member"):
            continue
        Notification(
            topic="identity",
            title="Submit your identity",
            message=(
                f"**{REALM_NAME}** has entered **beta**. Citizens must now "
                f"submit their actual identity (name + document reference) to "
                f"the *Citizenship & Identity* department — your anonymous "
                f"ZK-passport proof is no longer sufficient for this stage."
            ),
            sender="Citizenship & Identity",
            recipient=str(user.id),
            user=user,
            read=False,
            icon="identification",
            href="/extensions/member_dashboard",
            color="yellow",
            metadata="identity_submission_request",
            timestamp_created=epoch_to_datetime_str(now_epoch)[:16],
        )
        notified += 1
    ic.print(f"Syntropia: requested identity submission from {notified} citizen(s)")
    return notified


def run_payroll(args: str) -> str:
    """Record salary payments for all filled seats (admin/testing entry point,
    callable via ``extension_sync_call("syntropia", "run_payroll", "{}")``)."""
    try:
        from ggg import check_access as _check_access, Operations

        caller = ic.caller().to_str()
        if not _check_access(caller, Operations.REALM_ADMIN):
            return json.dumps({
                "success": False,
                "error": f"Access denied: {caller} is not a realm admin",
            })
    except Exception:
        pass

    try:
        result = _lifecycle_billing().run_payroll(_config(), REALM_NAME)
        return json.dumps(result)
    except Exception as e:
        ic.print(f"Error in Syntropia run_payroll: {e}")
        return json.dumps({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Real-identity attestations (mock, issue #253)
# ---------------------------------------------------------------------------
#
# A deliberately simple flow owned by the Citizenship & Identity department:
# citizens submit name + document reference; a registrar (or admin) marks the
# attestation approved/rejected. No real verification — this stands in for a
# future integration.

_IDENTITY_REVIEW_DEPARTMENT = "Citizenship & Identity"
_IdentityAttestation = None


def _identity_attestation_cls():
    global _IdentityAttestation
    if _IdentityAttestation is not None:
        return _IdentityAttestation

    from ggg import extension_entity_class as create_extension_entity_class
    from ic_python_db import Integer, String

    ExtensionEntity = create_extension_entity_class("syntropia")

    class IdentityAttestation(ExtensionEntity):
        __alias__ = "user_id"

        user_id = String(max_length=128)
        full_name = String(max_length=256)
        document_ref = String(max_length=256)
        status = String(max_length=16, default="submitted")
        reviewed_by = String(max_length=128)
        submitted_at = Integer(default=0)
        reviewed_at = Integer(default=0)

    _IdentityAttestation = IdentityAttestation
    return IdentityAttestation


def register_entities() -> None:
    """Register codex-scoped entity types (called by the extension loader)."""
    _identity_attestation_cls()


def _attestation_to_dict(att) -> dict:
    return {
        "user_id": att.user_id,
        "full_name": att.full_name or "",
        "document_ref": att.document_ref or "",
        "status": att.status or "submitted",
        "reviewed_by": att.reviewed_by or "",
        "submitted_at": int(att.submitted_at or 0),
        "reviewed_at": int(att.reviewed_at or 0),
    }


def _can_review_identity(caller: str) -> bool:
    """Registrars of Citizenship & Identity, department head, or realm admin."""
    try:
        from ggg import check_access as _check_access, Operations

        if _check_access(caller, Operations.REALM_ADMIN):
            return True
    except Exception:
        pass
    try:
        from ggg import Department, User

        from ggg import user_has_profile, user_in_department

        user = User[caller]
        dept = Department[_IDENTITY_REVIEW_DEPARTMENT]
        if user is None or dept is None:
            return False
        head = getattr(dept, "head", None)
        if head is not None and str(getattr(head, "id", "")) == caller:
            return True
        return user_in_department(user, dept) and user_has_profile(user, "registrar")
    except Exception:
        return False


def submit_identity(args: str) -> str:
    """Citizen submits their actual identity (mock — no verification).

    Args: {"full_name": "...", "document_ref": "..."}
    """
    try:
        params = json.loads(args) if args else {}
        full_name = (params.get("full_name") or "").strip()
        document_ref = (params.get("document_ref") or "").strip()
        if not full_name or not document_ref:
            return json.dumps({
                "success": False,
                "error": "full_name and document_ref are required",
            })

        caller = ic.caller().to_str()
        from ggg import User

        if User[caller] is None:
            return json.dumps({
                "success": False,
                "error": "caller is not a registered user",
            })

        IdentityAttestation = _identity_attestation_cls()
        now = int(ic.time()) // 1_000_000_000

        att = IdentityAttestation[caller]
        if att is None:
            att = IdentityAttestation(
                user_id=caller,
                full_name=full_name,
                document_ref=document_ref,
                status="submitted",
                submitted_at=now,
            )
        else:
            # Resubmission resets the review.
            att.full_name = full_name
            att.document_ref = document_ref
            att.status = "submitted"
            att.reviewed_by = ""
            att.reviewed_at = 0
            att.submitted_at = now

        ic.print(f"Syntropia: identity submitted by {caller}")
        return json.dumps({"success": True, "attestation": _attestation_to_dict(att)})
    except Exception as e:
        ic.print(f"Error in Syntropia submit_identity: {e}")
        return json.dumps({"success": False, "error": str(e)})


def review_identity(args: str) -> str:
    """Registrar approves/rejects a citizen's identity submission.

    Args: {"user_id": "...", "approve": true}
    """
    try:
        params = json.loads(args) if args else {}
        user_id = (params.get("user_id") or "").strip()
        approve = bool(params.get("approve", True))
        if not user_id:
            return json.dumps({"success": False, "error": "user_id is required"})

        caller = ic.caller().to_str()
        if not _can_review_identity(caller):
            return json.dumps({
                "success": False,
                "error": (
                    f"Access denied: {caller} is not a Citizenship & Identity "
                    f"registrar or realm admin"
                ),
            })

        IdentityAttestation = _identity_attestation_cls()
        att = IdentityAttestation[user_id]
        if att is None:
            return json.dumps({
                "success": False,
                "error": f"No identity submission found for {user_id}",
            })

        att.status = "approved" if approve else "rejected"
        att.reviewed_by = caller
        att.reviewed_at = int(ic.time()) // 1_000_000_000

        ic.print(
            f"Syntropia: identity of {user_id} "
            f"{'approved' if approve else 'rejected'} by {caller}"
        )
        return json.dumps({"success": True, "attestation": _attestation_to_dict(att)})
    except Exception as e:
        ic.print(f"Error in Syntropia review_identity: {e}")
        return json.dumps({"success": False, "error": str(e)})


def list_identity_attestations(args: str) -> str:
    """List identity submissions (reviewers only)."""
    try:
        caller = ic.caller().to_str()
        if not _can_review_identity(caller):
            return json.dumps({
                "success": False,
                "error": f"Access denied: {caller} may not list identity submissions",
            })

        IdentityAttestation = _identity_attestation_cls()
        items = [_attestation_to_dict(a) for a in IdentityAttestation.instances()]
        return json.dumps({"success": True, "attestations": items, "count": len(items)})
    except Exception as e:
        ic.print(f"Error in Syntropia list_identity_attestations: {e}")
        return json.dumps({"success": False, "error": str(e)})
