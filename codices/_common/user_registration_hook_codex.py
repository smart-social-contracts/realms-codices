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
        
        # Create 1 satoshi invoice for the new user
        # Invoice ID is auto-generated and used to derive a unique subaccount
        invoice = Invoice(
            amount=0.00000001,  # 1 satoshi
            currency="ckBTC",
            due_date=due_date,
            status="Pending",
            user=user,
            metadata="Welcome fee - 1 satoshi invoice"
        )
        
        # Get the deposit address info
        vault_principal = ic.id().to_str()
        subaccount_hex = invoice.get_subaccount_hex()
        
        ic.print(f"✅ Created welcome invoice {invoice.id} for user {user.id}")
        ic.print(f"   Deposit to: {vault_principal} (subaccount: {subaccount_hex[:16]}...)")
        ic.print(f"   Amount: 1 satoshi, expires in 1 day")
        
        # Notify the user about their welcome invoice
        Notification(
            topic="welcome",
            title="Welcome! Please complete your registration",
            message=f"A 1 satoshi welcome invoice has been created. Deposit to: {vault_principal} (subaccount: {subaccount_hex[:16]}...). Expires in 1 day.",
            user=user,
            read=False,
            icon="wallet",
            href="/extensions/member_dashboard#my_taxes",
            color="green",
            metadata=f"invoice_id:{invoice.id}"
        )
        
    except Exception as e:
        ic.print(f"❌ Error creating invoice: {e}")
    
    return
