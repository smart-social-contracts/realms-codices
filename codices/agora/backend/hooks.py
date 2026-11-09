"""Agora: an existing public administration moving its IT to Realms 1-to-1.

Citizens are imported or join with a registration code and are members at once (no ZK passport).
Nothing is billed during the migration (alpha); money starts flowing at beta.
"""

from ggg_sdk import hook, realm

NAME = "Agora"
BILLING = ("beta", "production")
DASHBOARD = "/extensions/member_dashboard"


@hook
def init(args):
    """Enforce the codex's registration policy, then seed departments, positions and courts (idempotent)."""
    wanted = {"open_registration": realm.setting("onboarding.registration.open_registration", False)}
    if not realm.info.get("name"):
        wanted["name"] = NAME
    if any(realm.info.get(k) != v for k, v in wanted.items()):
        realm.configure(**wanted)
    realm.seed()
    return {"codex": "agora"}


@hook
def on_user_register(args):
    """A registration invoice once the realm bills; before that, a welcome that says nothing is due."""
    user, fee, stage = args["user"], realm.setting("fees.registration", 0), realm.stage
    if stage in BILLING and fee > 0:
        invoice = realm.invoice(user, fee, "registration", realm.setting("membership.invoice_validity_days", 30))
        realm.notify(user, "Welcome to " + NAME,
                     "Your account has been migrated into **%s**. Please settle your registration invoice "
                     "(`%s %s`) in the *Invoices* section. The **AI Assistant** can help you at any time."
                     % (NAME, fee, realm.currency), "welcome", DASHBOARD)
        return {"invoice": invoice["invoice"]}
    realm.notify(user, "Welcome to " + NAME,
                 "Your account has been migrated into **%s** during the **%s** phase. **Nothing to pay for now.** "
                 "Your member dashboard shows your declaration and any *potential future* tax deadlines so you "
                 "can prepare ahead of the beta transition. Questions? Ask the **AI Assistant**." % (NAME, stage),
                 "welcome", DASHBOARD)
    return {"stage": stage}


@hook
def on_stage_change(args):
    """Entering beta: every citizen gets a membership invoice and payroll starts."""
    if args.get("stage") != "beta":
        return {"skipped": args.get("stage")}
    fee = realm.setting("fees.monthly_membership") or realm.setting("fees.registration", 0)
    billed = 0
    if fee > 0:
        billed = realm.bill_members(fee, "membership", "Tax / membership fee due",
                                    "The realm has entered **beta**: taxes and fees are now active. Please settle "
                                    "your membership invoice (`%s %s`) in the *Invoices* section."
                                    % (fee, realm.currency))
    realm.run_payroll("beta")
    return {"invoiced": billed}
