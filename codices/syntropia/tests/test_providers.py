# Test: Service Providers
# Covers: license issuance, compliance check, bill submission & payment,
#         license renewal & revocation
import licensing_codex
from ggg import License, LicenseType

ts = "p" + str(id(object()))[-6:]

# ── TEST 1: License Issuance ─────────────────────────────────────────────
print("=== TEST 1: LICENSE ISSUANCE ===")
hospital_lic = licensing_codex.issue_provider_license(
    ts + "_City Hospital", LicenseType.HEALTH,
    description="Primary healthcare provider for the central district",
    issuing_authority="Health Ministry",
)
assert "error" not in hospital_lic, "License should be issued: " + str(hospital_lic)
print("Hospital license: id=" + str(hospital_lic.get("license_id")) + " status=" + str(hospital_lic.get("status")))

school_lic = licensing_codex.issue_provider_license(
    ts + "_Academy", LicenseType.EDUCATION,
    description="K-12 education provider",
)
assert "error" not in school_lic
print("School license: id=" + str(school_lic.get("license_id")))

security_lic = licensing_codex.issue_provider_license(
    ts + "_SecureGuard", LicenseType.POLICE,
    description="Community security and policing",
)
assert "error" not in security_lic
print("Security license: id=" + str(security_lic.get("license_id")))

# ── TEST 2: Compliance Check ─────────────────────────────────────────────
print("=== TEST 2: COMPLIANCE CHECK ===")
comp_result = licensing_codex.check_compliance(str(hospital_lic["license_id"]))
assert comp_result.get("compliant"), "Hospital should be compliant: " + str(comp_result)
print("Hospital compliance: " + str(comp_result.get("compliant")) + " status=" + str(comp_result.get("status")))

# ── TEST 3: Service Bill Submission & Payment ────────────────────────────
print("=== TEST 3: SERVICE BILLING ===")
bill_result = licensing_codex.submit_bill(str(hospital_lic["license_id"]), amount=5000, description="Q1 healthcare services")
assert "error" not in bill_result, "Bill should be submitted: " + str(bill_result)
print("Bill submitted: index=" + str(bill_result.get("bill_index")) + " amount=" + str(bill_result.get("amount")))

pay_result = licensing_codex.pay_bill(str(hospital_lic["license_id"]), bill_index=0)
assert pay_result.get("status") == "paid", "Bill should be paid: " + str(pay_result)
print("Bill paid: " + str(pay_result.get("amount")))

# ── TEST 4: License Renewal & Revocation ─────────────────────────────────
print("=== TEST 4: LICENSE RENEWAL & REVOCATION ===")
renew_result = licensing_codex.renew_provider_license(str(school_lic["license_id"]))
assert renew_result.get("status") == "active", "License should be renewed: " + str(renew_result)
print("School license renewed: " + str(renew_result.get("status")))

revoke_result = licensing_codex.revoke_provider_license(str(security_lic["license_id"]), reason="Compliance failure")
assert revoke_result.get("status") == "revoked"
print("Security license revoked: " + str(revoke_result.get("status")))

licenses = licensing_codex.list_licenses()
print("Active licenses: " + str(len(licenses)))

# Summary
print("=== PROVIDER TESTS PASSED ===")
print("Licenses: " + str(License.count()))
