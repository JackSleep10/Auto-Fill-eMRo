import argparse
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.gse_wo_creator import GSEWorkOrderCreator

async def main():
    parser = argparse.ArgumentParser(description="eMRO GSE Batch Work Order Creator")
    parser.add_argument("--gse", nargs="+", help="One or more GSE numbers (e.g. TLM-TB-048 TLM-TB-049)")
    parser.add_argument("--file", help="Path to text or CSV file containing GSE numbers (one per line)")
    parser.add_argument("--desc", default="PM OCT", help="Description (English only, e.g. 'PM OCT', 'PM A')")
    parser.add_argument("--priority", default="SCHED", choices=["SCHED", "UNSCHED"], help="Priority (SCHED or UNSCHED)")
    parser.add_argument("--no-sync", action="store_true", help="Do not sync to Google Sheets")
    args = parser.parse_args()

    gse_list = []
    if args.gse:
        gse_list.extend(args.gse)
    if args.file:
        p = Path(args.file)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    item = line.strip().split(",")[0].strip().split("\t")[0].strip()
                    if item and not item.startswith("#"):
                        gse_list.append(item)

    if not gse_list:
        print("[!] No GSE items specified. Use --gse TLM-TB-048 ... or --file list.txt")
        sys.exit(1)

    items = [{"gse": g, "description": args.desc, "priority": args.priority} for g in gse_list]
    print(f"\n=======================================================")
    print(f"🚀 GSE WORK ORDER BATCH CREATION")
    print(f"   Total Items: {len(items)}")
    print(f"   Priority   : {args.priority}")
    print(f"   Description: {args.desc}")
    print(f"=======================================================\n")

    creator = GSEWorkOrderCreator(headless=False)
    await creator.start()

    def on_progress(curr, total, res):
        status = "SUCCESS" if res.get("success") else "FAILED"
        print(f"[{curr}/{total}] {res.get('gse')} -> W/O: {res.get('wo_number')} | S/N: {res.get('sn')} [{status}]")

    results = await creator.create_batch_wo(items, on_progress=on_progress)
    await creator.close()

    print(f"\n=======================================================")
    print(f"📊 BATCH SUMMARY")
    print(f"   Success: {len([r for r in results if r.get('success')])}/{len(results)}")
    print(f"=======================================================\n")

    wo_numbers = [r["wo_number"] for r in results if r.get("success") and r.get("wo_number")]
    print("📋 COPIABLE WORK ORDER NUMBERS:")
    for num in wo_numbers:
        print(num)

    if not args.no_sync:
        print("\n📤 Syncing to Google Sheets...")
        creator.sync_to_google_sheet(results)

if __name__ == "__main__":
    asyncio.run(main())
