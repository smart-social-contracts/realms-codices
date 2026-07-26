import json

from ggg import extension_call as extension_async_call

from ic_python_logging import get_logger

logger = get_logger("entity.treasury.sendhook")

def send_hook(treasury, to_principal: str, amount: int) -> Async[str]:
    """Send tokens from treasury to a principal using embedded vault extension"""

    logger.info(f"Treasury send hook called for '{treasury.name}' sending {amount} tokens to {to_principal}")

    # Use already imported extension_async_call
    # Use embedded vault extension API
    args = json.dumps(
        {
            "to_principal": to_principal,
            "amount": amount,
        }
    )

    result = yield extension_async_call("vault", "transfer", args)
    return result