"""
User Registration Hook Codex
Overrides user_register_posthook to add custom logic after user registration.
Creates a 1 satoshi invoice expiring in 1 day for new users.
"""

from kybra import ic
from ggg import Invoice, Notification
from datetime import datetime, timedelta

def user_register_posthook(user):
    """Custom user registration hook - creates welcome invoice."""
    try:
        # Calculate expiry time (1 day from now)
        expiry_time = datetime.now() + timedelta(days=1)
        due_date = expiry_time.isoformat()
        
        # Create 1 satoshi invoice and 1 REALMS invoice for the new user

        invoice_ckbtc = Invoice(
            amount=0.00000001,  # 1 satoshi
            currency="ckBTC",
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - 1 satoshi invoice"
        )

        invoice_realms = Invoice(
            amount=1,  # 1 REALMS
            currency="REALMS",
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - 1 REALMS invoice"
        )
        
        # Get the deposit address info
        vault_principal = ic.id().to_str()
        subaccount_hex_ckbtc = invoice_ckbtc.get_subaccount_hex()
        subaccount_hex_realms = invoice_realms.get_subaccount_hex()
        
        ic.print(f"✅ Created welcome invoices {invoice_ckbtc.id} and {invoice_realms.id} for user {user.id}")

        ic.print(f"   Deposit to: {vault_principal} (subaccount: {subaccount_hex_ckbtc[:16]}...)")
        ic.print(f"   Amount: 1 satoshi, expires in 1 day")
        
        ic.print(f"   Deposit to: {vault_principal} (subaccount: {subaccount_hex_realms[:16]}...)")
        ic.print(f"   Amount: 1 REALMS, expires in 1 day")
        

        # Notify the user about their welcome invoice
        Notification(
            topic="welcome",
            title="Welcome! Please complete your registration",
            message=f"Please pay any of the invoices to complete your registration."
            + f"Deposit {invoice_ckbtc.amount} ckBTC to: {vault_principal} (subaccount: {subaccount_hex_ckbtc[:16]}...)."
            + f"Deposit {invoice_realms.amount} REALMS to: {vault_principal} (subaccount: {subaccount_hex_realms[:16]}...)."
            + "Expires in 1 day.",
            user=user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard#my_taxes",
            color="green",
            metadata=f"invoice_id:{invoice_ckbtc.id}, invoice_id:{invoice_realms.id}"
        )
        
    except Exception as e:
        ic.print(f"❌ Error creating invoice: {e}")
    
    return
