"""Dominion: a direct democracy with taxation, in its own currency (DOM).

Every newcomer receives a registration invoice. Dominion installs no identity verifier: a realm that wants ZK
passport proofs adds the passport_verification extension, and the welcome notice mentions it only as an option.
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
                 "Welcome to **%s**! To become an active citizen, **pay your registration invoice**: `%s %s` "
                 "from the *Invoices* section.\n\n"
                 "If this realm offers *Passport Verification*, you can also prove your identity there with a ZK "
                 "passport. The **AI Assistant** knows everything about this realm and can guide you."
                 % (NAME, fee, realm.currency), "welcome", "/extensions/member_dashboard")
    return {"invoice": invoice["invoice"]}
