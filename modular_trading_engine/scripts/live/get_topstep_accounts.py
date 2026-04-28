import asyncio
import os
import sys
import requests

# Zorg ervoor dat de root dir van het project bereikbaar is voor imports (layer4_execution)
_engine_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _engine_root not in sys.path:
    sys.path.insert(0, _engine_root)
os.chdir(_engine_root)
from src.layer4_execution.auth import fetch_topstepx_jwt

async def main():
    print("🤖 Bezig met onzichtbaar ophalen van JWT token via TopstepX login...")
    jwt_token = await fetch_topstepx_jwt()
    if not jwt_token:
        print("❌ Fout: Kon geen JWT token intercepten. Controleer TOPSTEPX_USERNAME en TOPSTEPX_PASSWORD in je .env bestand.")
        return
        
    print("🌐 JWT succesvol onderschept. Accounts opvragen bij interne ProjectX API...")
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Hit de TopstepX backend direct
    url = "https://api.topstepx.com/api/Account/search"
    payload = {"onlyActiveAccounts": False}
    
    try:
        req = requests.post(url, headers=headers, json=payload)
        if req.status_code == 200:
            data = req.json()
            accounts = data.get('accounts', [])
            
            print("\n" + "="*60)
            print(f"✅ {len(accounts)} TopstepX Accounts Gevonden:")
            print("="*60)
            for item in accounts:
                account_name = item.get('name', 'Onbekend')
                account_id = item.get('id', 'Ontbreekt')
                print(f"Naam: {account_name:<30} | Database ID: {account_id}")
            print("="*60 + "\n")
            print("💡 Kopieer het 'Database ID' naar je execution_config.json onder 'account_id'.\n")
        else:
            print(f"❌ API Fout: HTTP {req.status_code} - {req.text}")
    except Exception as e:
        print(f"❌ Kritieke fout tijdens communicatie met de API: {e}")

if __name__ == "__main__":
    asyncio.run(main())
