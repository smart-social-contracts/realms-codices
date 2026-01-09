from kybra import ic
from ggg import Realm, Treasury, UserProfile, User, Codex, Instrument, Transfer
import json
import os

# Update Realm with manifest_data containing entity method overrides
realm = list(Realm.instances())[0] if Realm.instances() else None
if realm:
    # Load manifest.json from the realm directory
    manifest_path = os.path.join(os.path.dirname(__file__), 'manifest.json')
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Only keep entity_method_overrides for realm.manifest_data
        realm_manifest = {
            "entity_method_overrides": manifest.get("entity_method_overrides", [])
        }
        
        realm.manifest_data = json.dumps(realm_manifest)
        
        # Update realm name if present in manifest
        if "name" in manifest:
            realm.name = manifest["name"]
            ic.print(f"✅ Realm name set to: {manifest['name']}")
        
        # Update realm description if present in manifest
        if "description" in manifest:
            realm.description = manifest["description"]
            ic.print(f"✅ Realm description set to: {manifest['description'][:50]}...")
        
        # Update realm logo if present in manifest
        if "logo" in manifest:
            realm.logo = manifest["logo"]
            ic.print(f"✅ Realm logo set to: {manifest['logo']}")
        
        # Update realm welcome_image if present in manifest
        if "welcome_image" in manifest:
            realm.welcome_image = manifest["welcome_image"]
            ic.print(f"✅ Realm welcome_image set to: {manifest['welcome_image']}")
        
        # Update realm welcome_message if present in manifest
        if "welcome_message" in manifest:
            realm.welcome_message = manifest["welcome_message"]
            ic.print(f"✅ Realm welcome_message set to: {manifest['welcome_message'][:50]}...")
        
        ic.print(f"✅ Realm.manifest_data updated with entity method overrides from manifest.json")
    except FileNotFoundError:
        ic.print(f"⚠️  manifest.json not found at {manifest_path}, skipping manifest update")
    except Exception as e:
        ic.print(f"❌ Error loading manifest.json: {e}")
else:
    ic.print("❌ No Realm found")

# Print entity counts
ic.print("len(Realm.instances()) = %d" % len(Realm.instances()))
ic.print("len(Treasury.instances()) = %d" % len(Treasury.instances()))
ic.print("len(UserProfile.instances()) = %d" % len(UserProfile.instances()))
ic.print("len(User.instances()) = %d" % len(User.instances()))
ic.print("len(Codex.instances()) = %d" % len(Codex.instances()))
ic.print("len(Instrument.instances()) = %d" % len(Instrument.instances()))
ic.print("len(Transfer.instances()) = %d" % len(Transfer.instances()))

for codex in Codex.instances():
    ic.print(f"{codex.name}: {len(codex.code)}")
