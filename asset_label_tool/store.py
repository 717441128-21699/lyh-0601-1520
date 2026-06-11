import json
import os
from typing import List, Optional, Dict
from .models import Asset, BatchRecord, PrintTask


class Store:
    def __init__(self, data_dir: str = ".asset_data"):
        self.data_dir = data_dir
        self.assets_file = os.path.join(data_dir, "assets.json")
        self.batches_file = os.path.join(data_dir, "batches.json")
        self.tasks_file = os.path.join(data_dir, "tasks.json")
        self._assets: Dict[str, Asset] = {}
        self._batches: List[BatchRecord] = []
        self._tasks: Dict[str, PrintTask] = {}
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
