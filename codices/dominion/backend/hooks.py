"""Dominion: a direct democracy with taxation, in its own currency (DOM).

Every newcomer receives a registration invoice and is asked to verify their identity.
"""

from ggg_sdk import hook, realm

NAME = "Dominion"


@hook
def init(args):
    if not realm.info.get("name"):
        realm.configure(name=NAME)
    return {"codex": "dominion"}


@hook
def on_user_register(args):
    user, fee = args["user"], realm.setting("fees.registration", 1)
    invoice = realm.invoice(user, fee, "registration", realm.setting("membership.invoice_validity_days", 30))
    realm.notify(user, "Welcome to %s!" % NAME,
                 "Welcome to **%s**! To become an active citizen you need to complete two steps:\n\n"
                 "- **Pay your registration invoice**: `%s %s` from the *Invoices* section\n"
                 "- **Verify your identity** via ZK Passport using the *Passport Verification* extension\n\n"
                 "The **AI Assistant** knows everything about this realm and can guide you."
                 % (NAME, fee, realm.currency), "welcome", "/extensions/member_dashboard")
    return {"invoice": invoice["invoice"]}
