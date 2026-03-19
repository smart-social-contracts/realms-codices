# Quick diagnostic
from ggg import User
u = User(id="diag_001", name="Diagnostic")
print("USER_CREATED:" + u.id)

# Try codex import
try:
    from codices.syntropia.membership_codex import finalize_membership
    print("IMPORT:codices.syntropia OK")
except Exception as e:
    print("IMPORT:codices.syntropia FAIL:" + str(e))

try:
    from membership_codex import finalize_membership
    print("IMPORT:membership_codex OK")
except Exception as e:
    print("IMPORT:membership_codex FAIL:" + str(e))

try:
    import membership_codex
    print("IMPORT:membership_codex module OK")
except Exception as e:
    print("IMPORT:membership_codex module FAIL:" + str(e))
