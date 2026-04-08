import os
import sys
import time
import requests
import urllib.parse
import asyncio
from dotenv import load_dotenv

# Zorg dat we Python laten weten waar onze "src" folder staat
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.layer4_execution.auth import fetch_topstepx_jwt

def test_raw_topstep_chart_data():
    load_dotenv()
    
    print("--------------------------------------------------")
    print("TopstepX Verbinding Test - Modular Trading Engine")
    print("--------------------------------------------------")
    
    # Check of token lokaal is ingevuld (waarschijnlijk leeg gelaten door jou)
    jwt_token = os.environ.get("TOPSTEPX_AUTH_TOKEN")
    
    # Als hij handmatig leeg is gelaten, start de headless browser heist
    if not jwt_token:
        print("Geen TOPSTEPX_AUTH_TOKEN ingevuld.")
        print("Start automatische Headless Auth via Playwright / Chromium...")
        jwt_token = asyncio.run(fetch_topstepx_jwt())
        
    if not jwt_token:
        print("❌ FOUT: Auto-login mislukt. Controleer TOPSTEPX_USERNAME en PASSWORD in je .env.")
        return

    print("🔑 JWT Token buitgemaakt! Data ophalen via beveiligde REST API...\n")

    # Pak de data van de laatste 30 minuten
    end_time_sec = int(time.time())
    start_time_sec = end_time_sec - (30 * 60) 
    
    params = {
        "Symbol": "/NQ",
        "Resolution": "1",
        "From": start_time_sec,
        "To": end_time_sec
    }
    
    url = f"https://chartapi.topstepx.com/History/v2?{urllib.parse.urlencode(params)}"
    
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Origin": "https://www.topstepx.com",
        "x-app-type": "web",
        "x-app-version": "1.22.50",
        "Accept": "application/json"
    }

    try:
        print(f"🔗 Ophalen: {url}")
        res = requests.get(url, headers=headers)
        
        if not res.ok:
            print(f"❌ MISLUKT. HTTP Status Code: {res.status_code}")
            print(f"Foutmelding: {res.text}")
            return
            
        data = res.json()
        print("\n✅ API VERBINDING SUCCESVOL!")
        
        bars = data.get("bars", [])
        print(f"Aantal 1-minuut candles ontvangen: {len(bars)}")
        
        print("\nRAUWE TopStep Data Format (Eerste 2 candles direct uit de bron):")
        import json
        print(json.dumps(bars[:2], indent=4))
        
    except Exception as e:
        print(f"❌ Crash tijdens verbinding: {e}")

if __name__ == "__main__":
    test_raw_topstep_chart_data()
