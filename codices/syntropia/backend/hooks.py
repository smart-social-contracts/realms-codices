"""Syntropia: a greenfield smart city built from scratch.

New citizens pay a deposit (a house in a zone) and submit Know-Your-Citizen data before go-live, which the
Citizenship & Identity department reviews. Joiners are placed in the least populated quarter.

No step depends on an outside service: a ZK passport verifier is an extension a realm may add, not a door every
citizen must pass through. The realm itself does not gate membership on any of these steps; they are what the city
asks of its citizens.
"""

from ggg_sdk import hook, realm

NAME = "Syntropia"
DASHBOARD = "/extensions/member_dashboard"


@hook
def init(args):
    """Enforce the codex's registration policy, then seed departments, positions and courts (idempotent)."""
    wanted = {"open_registration": realm.setting("onboarding.registration.open_registration", True)}
    if not realm.info.get("name"):
        wanted["name"] = NAME
    if any(realm.info.get(k) != v for k, v in wanted.items()):
        realm.configure(**wanted)
    realm.seed()
    return {"codex": "syntropia"}


@hook
def on_user_register(args):
    """The deposit invoice and the steps to citizenship."""
    user = args["user"]
    deposit = realm.setting("fees.deposit", realm.setting("lifecycle.deposit_amount", 0.01))
    label = realm.setting("lifecycle.deposit_label", "a house in a zone")
    invoice = realm.invoice(user, deposit, "deposit", realm.setting("membership.invoice_validity_days", 30))
    realm.notify(user, "Welcome to %s!" % NAME,
                 "Welcome to **%s**, a brand-new sovereign smart city. To become an active citizen, complete "
                 "two steps:\n\n1. **Pay your deposit** (%s): `%s %s` from the *Invoices* section\n2. **Submit "
                 "your Know-Your-Citizen data** before the city goes live: enter it on your *Account* page and "
                 "share it with the *Citizenship & Identity* department, which reviews it\n\nIf this city offers *Passport Verification*, "
                 "you can also prove your identity there with a ZK passport. The **AI Assistant** can guide you "
                 "through every step." % (NAME, label, deposit, realm.currency), "welcome", DASHBOARD)
    return {"invoice": invoice["invoice"]}


@hook
def on_stage_change(args):
    """Entering beta: membership invoices, payroll, and every citizen is asked for their real identity."""
    if args.get("stage") != "beta":
        return {"skipped": args.get("stage")}
    fee = realm.setting("fees.monthly_membership") or realm.setting("fees.registration", 0)
    billed = 0
    if fee > 0:
        billed = realm.bill_members(fee, "membership", "Tax / membership fee due",
                                    "The city has entered **beta**: taxes and fees are now active. Please settle "
                                    "your membership invoice (`%s %s`) in the *Invoices* section."
                                    % (fee, realm.currency))
    realm.run_payroll("beta")
    asked = 0
    for u in realm.members():
        realm.notify(u["id"], "Submit your identity",
                     "**%s** has entered **beta**. Citizens must now submit their actual identity (name and "
                     "document reference) to the *Citizenship & Identity* department, even if you proved it "
                     "anonymously with a ZK passport." % NAME, "identity", DASHBOARD)
        asked += 1
    return {"invoiced": billed, "identity_requests": asked}


@hook
def assign_quarter(args):
    """The home quarter of a joiner: the preferred one if it has room, else the least populated one.

    args: {user, preferred, quarters: [{id, name, population}]}; `quarter.max_population` 0 means unlimited.
    """
    quarters, wanted, cap = args["quarters"], args.get("preferred"), realm.setting("quarter.max_population", 0)
    chosen = [q for q in quarters if wanted and wanted in (q["id"], q.get("name"))]
    if wanted and not chosen:
        raise ValueError("quarter '%s' is not among the active quarters" % wanted)
    q = chosen[0] if chosen else min(quarters, key=lambda q: q.get("population", 0))
    if cap and q.get("population", 0) >= cap:
        raise ValueError("quarter '%s' is full (%d/%d)" % (q.get("name") or q["id"], q["population"], cap))
    return {"quarter": q["id"]}
