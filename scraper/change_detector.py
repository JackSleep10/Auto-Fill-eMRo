import json
from pathlib import Path
from typing import List, Dict, Tuple
from scraper.config import Config

class ChangeDetector:
    def __init__(self, cache_file: Path = Config.CACHE_FILE):
        self.cache_file = cache_file
        self.cached_transactions: Dict[str, Dict] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {item.get("transaction_no", ""): item for item in data if item.get("transaction_no")}
            except Exception as e:
                print(f"[ChangeDetector] Error loading cache: {e}")
        return {}

    def save_cache(self, transactions: List[Dict]):
        try:
            # Update cache map
            for item in transactions:
                t_no = item.get("transaction_no")
                if t_no:
                    self.cached_transactions[t_no] = item
            
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(list(self.cached_transactions.values()), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ChangeDetector] Error saving cache: {e}")

    def compare(self, latest_transactions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Compares latest transactions with cached transactions.
        Returns:
            new_records: Transactions that were never seen before.
            updated_records: Transactions whose status or details changed.
        """
        new_records = []
        updated_records = []

        for item in latest_transactions:
            t_no = item.get("transaction_no")
            if not t_no:
                continue

            if t_no not in self.cached_transactions:
                new_records.append(item)
            else:
                old_item = self.cached_transactions[t_no]
                # Check for updates in status, quantity, etc.
                if (old_item.get("status") != item.get("status") or 
                    old_item.get("qty") != item.get("qty")):
                    updated_records.append(item)

        # Update cache after detection
        if new_records or updated_records:
            self.save_cache(latest_transactions)

        return new_records, updated_records
