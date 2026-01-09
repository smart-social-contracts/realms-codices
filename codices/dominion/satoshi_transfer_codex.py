"""
Satoshi Transfer Codex
Sends 1 satoshi to a configured target principal every execution.

This codex is designed to run as a scheduled task.
Note: Use 'logger' (provided in execution namespace) for logs to be captured
in TaskExecution records, not ic.print() which only goes to canister stdout.
"""

from kybra import ic
from ggg import Transfer
import json

# Default target principal
DEFAULT_TARGET_PRINCIPAL = "64fpo-jgpms-fpewi-hrskb-f3n6u-3z5fy-bv25f-zxjzg-q5m55-xmfpq-hqe"
AMOUNT_SATOSHIS = 1


def async_task():
    """
    Main entry point for scheduled task.
    Sends 1 satoshi to the target principal.
    """
    logger.info("💸 Satoshi Transfer Task starting...")
    
    target = DEFAULT_TARGET_PRINCIPAL
    amount = AMOUNT_SATOSHIS
    
    logger.info(f"📍 Target principal: {target}")
    logger.info(f"💰 Amount: {amount} satoshi(s)")
    
    try:
        # Get the vault/canister principal as source
        source_principal = ic.id().to_str()
        logger.info(f"📤 Source: {source_principal}")
        
        # Create a transfer record
        transfer = Transfer(
            id=f"satoshi_transfer_{int(ic.time())}",
            principal_from=source_principal,
            principal_to=target,
            instrument="ckBTC",
            amount=amount,
            timestamp=str(ic.time()),
            status="pending",
            tags="scheduled,satoshi_transfer"
        )
        
        logger.info(f"📝 Created transfer record: {transfer.id}")
        
        # Execute the transfer (uses vault extension if installed)
        try:
            yield transfer.execute()
            transfer.status = "completed"
            logger.info("✅ Transfer completed successfully!")
        except NotImplementedError:
            logger.warning("⚠️ Transfer.execute() not implemented - vault extension may not be installed")
            transfer.status = "recorded_only"
        except Exception as exec_error:
            logger.error(f"❌ Transfer execution failed: {exec_error}")
            transfer.status = "failed"
        
        return json.dumps({
            "success": True,
            "transfer_id": transfer.id,
            "status": transfer.status
        })
        
    except Exception as e:
        logger.error(f"❌ Error in satoshi transfer: {e}")
        return json.dumps({"success": False, "error": str(e)})
