import os
import asyncio
import logging
from playwright.async_api import async_playwright
from dotenv import load_dotenv

logger = logging.getLogger("HeadlessAuth")

async def fetch_topstepx_jwt() -> str:
    """
    Start een onzichtbare Chromium browser, logt in op TopstepX als een mens,
    en grist razendsnel het JWT token ('eyJ...') uit het netwerkverkeer (Authorization header).
    """
    load_dotenv()
    username = os.getenv("TOPSTEPX_USERNAME")
    password = os.getenv("TOPSTEPX_PASSWORD")
    
    if not username or not password:
        logger.error("TOPSTEPX_USERNAME en TOPSTEPX_PASSWORD ontbreken in de .env file!")
        return None

    jwt_token = None
    
    async with async_playwright() as p:
        logger.info("🤖 Start onzichtbare browser (Headless) met anti-bot omzeiling...")
        browser = await p.chromium.launch(
            headless=True, 
            args=['--disable-blink-features=AutomationControlled']
        )
        # We maken de bot realistisch door een standaard User-Agent mee te geven
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        async def handle_request(route, request):
            nonlocal jwt_token
            headers = request.headers
            # Intercept: we zoeken de Authorization header die met 'Bearer ey' begint (JWT signature)
            if 'authorization' in headers and 'Bearer ey' in headers['authorization']:
                token = headers['authorization'].split('Bearer ')[1]
                if len(token) > 100:  # Zeker weten dat het een volle JWT is
                    jwt_token = token
            # Laat het verzoek gewoon door gaan
            await route.continue_()
            
        async def log_frame(ws):
            logger.info(f"🌐 WebSocket Intercepted: {ws.url}")
            ws.on("framesent", lambda payload: logger.debug(f"-> WS SEND: {str(payload)[:200]}"))
            
        await page.route("**/*", handle_request)
        page.on("websocket", log_frame)
        
        logger.info("🌐 Navigeren naar https://topstepx.com/login...")
        try:
            await page.goto("https://topstepx.com/login", timeout=30000)
            
            # Formulier met data invullen
            logger.info("Muur doorbroken. Aanmeldformulier invullen...")
            
            # Let op: de selectors die TSX gebruikt zijn name="userName" en name="password"
            await page.wait_for_selector('input[name="userName"]', timeout=15000)
            await page.fill('input[name="userName"]', username)
            
            await page.wait_for_selector('input[name="password"]', timeout=15000)
            await page.fill('input[name="password"]', password)
            
            logger.info("👆 Klikken op Inloggen...")
            # Vaak werkt een ENTER op het wachtwoord veld het best
            await page.press('input[name="password"]', 'Enter')
            
            logger.info("🕵️ Netwerkverkeer monitoren voor de JWT interceptie...")
            # We proberen 15 seconden het token te vangen via de netwerk inspector
            for _ in range(15):
                if jwt_token:
                    break
                await asyncio.sleep(1)
                
            if jwt_token:
                logger.info("✅ HEIST SUCCESVOL: Token in the pocket!")
            else:
                logger.error("❌ Mislukt: Geen JWT token binnen 15s interceptie window.")
                
        except Exception as e:
            logger.error(f"⚠️ Fout tijdens de Headless Auth procedure: {e}")
            
        finally:
            logger.info("Sporen uitwissen: de browser is netjes afgesloten.")
            await browser.close()
            
    return jwt_token

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # Quick test
    asyncio.run(fetch_topstepx_jwt())
