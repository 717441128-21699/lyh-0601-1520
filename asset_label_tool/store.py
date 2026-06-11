import json
import os
from typing import List, Optional, Dict
from .models import Asset, BatchRecord, PrintTask, InventoryBatch


class Store:
    def __init__(self, data_dir: str = ".asset_data"):
        self.data_dir = data_dir
        self.assets_file = os.path.join(data_dir, "assets.json")
        self.batches_file = os.path.join(data_dir, "batches.json")
        self.tasks_file = os.path.join(data_dir, "tasks.json")
        self.inventories_file = os.path.join(data_dir, "inventories.json")
        self._assets: Dict[str, Asset] = {}
        self._batches: List[BatchRecord] = []
        self._tasks: Dict[str, PrintTask] = {}
        self._inventories: Dict[str, InventoryBatch] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.assets_file):
            with open(self.assets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._assets = {a["asset_id"]: Asset.from_dict(a) for a in data}
        if os.path.exists(self.batches_file):
            with open(self.batches_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._batches = [BatchRecord.from_dict(b) for b in data]
        if os.path.exists(self.tasks_file):
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._tasks = {t["name"]: PrintTask.from_dict(t) for t in data}
        if os.path.exists(self.inventories_file):
            with open(self.inventories_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._inventories = {inv["name"]: InventoryBatch.from_dict(inv) for inv in data}

    def _save_assets(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.assets_file, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in self._assets.values()], f, ensure_ascii=False, indent=2)

    def _save_batches(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.batches_file, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self._batches], f, ensure_ascii=False, indent=2)

    def add_assets(self, assets: List[Asset], skip_duplicates: bool = True) -> dict:
        added, skipped, duplicates = [], [], []
        for asset in assets:
            if asset.asset_id in self._assets:
                if skip_duplicates:
                    duplicates.append(asset.asset_id)
                    continue
                else:
                    self._assets[asset.asset_id] = asset
                    skipped.append(asset.asset_id)
            else:
                self._assets[asset.asset_id] = asset
                added.append(asset.asset_id)
        self._save_assets()
        return {"added": added, "skipped": skipped, "duplicates": duplicates}

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        return self._assets.get(asset_id)

    def get_all_assets(self) -> List[Asset]:
        return list(self._assets.values())

    def get_assets_by_category(self, category: str) -> List[Asset]:
        return [a for a in self._assets.values() if a.category == category]

    def get_unprinted_assets(self) -> List[Asset]:
        return [a for a in self._assets.values() if not a.printed]

    def get_categories(self) -> List[str]:
        cats = set(a.category for a in self._assets.values() if a.category)
        return sorted(cats)

    def update_asset(self, asset: Asset):
        self._assets[asset.asset_id] = asset
        self._save_assets()

    def mark_printed(self, asset_ids: List[str], batch_id: str):
        for aid in asset_ids:
            if aid in self._assets:
                self._assets[aid].printed = True
                self._assets[aid].print_batch = batch_id
        self._save_assets()

    def add_batch(self, batch: BatchRecord):
        self._batches.append(batch)
        self._save_batches()

    def get_batches(self) -> List[BatchRecord]:
        return list(self._batches)

    def get_batch(self, batch_id: str) -> Optional[BatchRecord]:
        for b in self._batches:
            if b.batch_id == batch_id:
                return b
        return None

    def get_assets_by_batch(self, batch_id: str) -> List[Asset]:
        batch = self.get_batch(batch_id)
        if not batch:
            return []
        return [self._assets[aid] for aid in batch.asset_ids if aid in self._assets]

    def get_next_sequential_id(self, prefix: str = "AST") -> str:
        num = self.get_next_sequential_number(prefix)
        return f"{prefix}{num:06d}"

    def get_next_sequential_number(self, prefix: str = "AST") -> int:
        existing = [a.asset_id for a in self._assets.values() if a.asset_id.startswith(prefix)]
        max_num = 0
        for eid in existing:
            try:
                num = int(eid[len(prefix):])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
        return max_num + 1

    def filter_assets(self, category: Optional[str] = None,
                      location: Optional[str] = None,
                      responsible: Optional[str] = None,
                      unprinted_only: bool = False) -> List[Asset]:
        results = list(self._assets.values())
        if category:
            results = [a for a in results if a.category == category]
        if location:
            results = [a for a in results if location in a.location]
        if responsible:
            results = [a for a in results if responsible in a.responsible]
        if unprinted_only:
            results = [a for a in results if not a.printed]
        return results

    def get_locations(self) -> List[str]:
        locs = set(a.location for a in self._assets.values() if a.location)
        return sorted(locs)

    def get_responsibles(self) -> List[str]:
        resps = set(a.responsible for a in self._assets.values() if a.responsible)
        return sorted(resps)

    def _save_tasks(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.tasks_file, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self._tasks.values()], f, ensure_ascii=False, indent=2)

    def save_task(self, task: PrintTask):
        self._tasks[task.name] = task
        self._save_tasks()

    def get_task(self, name: str) -> Optional[PrintTask]:
        return self._tasks.get(name)

    def get_all_tasks(self) -> List[PrintTask]:
        return list(self._tasks.values())

    def delete_task(self, name: str) -> bool:
        if name in self._tasks:
            del self._tasks[name]
            self._save_tasks()
            return True
        return False

    def _save_inventories(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.inventories_file, "w", encoding="utf-8") as f:
            json.dump([inv.to_dict() for inv in self._inventories.values()], f, ensure_ascii=False, indent=2)

    def save_inventory(self, inv: InventoryBatch):
        self._inventories[inv.name] = inv
        self._save_inventories()

    def get_inventory(self, name: str) -> Optional[InventoryBatch]:
        return self._inventories.get(name)

    def get_all_inventories(self) -> List[InventoryBatch]:
        return list(self._inventories.values())

    def delete_inventory(self, name: str) -> bool:
        if name in self._inventories:
            del self._inventories[name]
            self._save_inventories()
            return True
        return False

    def get_inventory_progress(self, name: str) -> Optional[dict]:
        inv = self.get_inventory(name)
        if not inv:
            return None
        total = len(inv.asset_ids)
        checked_set = set(inv.checked_ids)
        extraneous_set = set(inv.extraneous_ids)

        printed_ids = []
        printed_not_checked = []
        unprinted_ids = []
        checked_ids = []
        for aid in inv.asset_ids:
            asset = self.get_asset(aid)
            is_printed = bool(asset and asset.printed)
            is_checked = aid in checked_set
            if is_printed:
                printed_ids.append(aid)
            else:
                unprinted_ids.append(aid)
            if is_checked:
                checked_ids.append(aid)
            if is_printed and not is_checked:
                printed_not_checked.append(aid)

        not_checked = [aid for aid in inv.asset_ids if aid not in checked_set]
        unprinted_not_checked = [aid for aid in not_checked if aid in unprinted_ids]

        return {
            "name": name,
            "group_by": inv.group_by,
            "group_value": inv.group_value,
            "total": total,
            "printed_count": len(printed_ids),
            "unprinted_count": len(unprinted_ids),
            "checked_count": len(checked_ids),
            "not_checked_count": len(not_checked),
            "printed_not_checked_count": len(printed_not_checked),
            "unprinted_not_checked_count": len(unprinted_not_checked),
            "extraneous_count": len(extraneous_set),
            "all_ids": inv.asset_ids,
            "printed_ids": printed_ids,
            "unprinted_ids": unprinted_ids,
            "checked_ids": inv.checked_ids,
            "printed_not_checked_ids": printed_not_checked,
            "unprinted_not_checked_ids": unprinted_not_checked,
            "extraneous_ids": list(extraneous_set),
            "created_at": inv.created_at,
        }

    def add_scan_results(self, inv_name: str, scan_ids: List[str]) -> dict:
        inv = self.get_inventory(inv_name)
        if not inv:
            return {"error": f"盘点批次 '{inv_name}' 不存在"}

        in_batch = set(inv.asset_ids)
        checked_set = set(inv.checked_ids)
        extraneous_set = set(inv.extraneous_ids)

        new_checked = []
        new_extraneous = []
        for sid in scan_ids:
            sid = sid.strip()
            if not sid:
                continue
            if sid in in_batch:
                if sid not in checked_set:
                    checked_set.add(sid)
                    new_checked.append(sid)
            else:
                if sid not in extraneous_set:
                    extraneous_set.add(sid)
                    new_extraneous.append(sid)

        inv.checked_ids = sorted(checked_set)
        inv.extraneous_ids = sorted(extraneous_set)
        self.save_inventory(inv)

        return {
            "new_checked": new_checked,
            "new_extraneous": new_extraneous,
            "duplicate_checked": [sid for sid in scan_ids
                                   if sid.strip() in in_batch and sid.strip() in set(inv.checked_ids) - set(new_checked)],
        }
