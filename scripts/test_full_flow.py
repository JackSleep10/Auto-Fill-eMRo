import asyncio
import datetime
from scraper.config import Config
from scraper.emro_scraper import eMROScraper
from sheets.google_sheets import GoogleSheetsClient

async def test_single_cycle():
    scraper = eMROScraper()
    sheets = GoogleSheetsClient()
    
    print("[Full Flow Test] Initializing scraper...")
    await scraper.initialize()
    
    print("[Full Flow Test] Running ensure_authenticated()...")
    await scraper.ensure_authenticated()
    
    print(f"[Full Flow Test] Querying transactions for location {Config.MONITOR_LOCATION}...")
    transactions = await scraper.query_inventory_transactions(Config.MONITOR_LOCATION)
    
    print(f"[Full Flow Test] Extracted {len(transactions)} transactions.")
    if transactions:
        print("[Full Flow Test] Sample 1st transaction:", transactions[0])
        if sheets.is_configured:
            print("[Full Flow Test] Syncing to Google Sheets...")
            success = sheets.update_live_sheet(transactions)
            print(f"[Full Flow Test] Google Sheets sync result: {success}")
        else:
            print("[Full Flow Test] Google Sheets not configured.")
    else:
        print("[Full Flow Test] Warning: 0 transactions returned.")
        
    await scraper.close()
    print("[Full Flow Test] Completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_single_cycle())
