from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
import uuid


@dataclass
class Asset:
    asset_id: str
    name: str = ""
    location: str = ""
    responsible: str = ""
    category: str = ""
    printed: bool = False
    print_batch: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    REQUIRED_FIELDS = ("asset_id", "name", "location", "responsible")

    def missing_fields(self) -> List[str]:
        missing = []
        for f in self.REQUIRED_FIELDS:
            if not getattr(self, f, "").strip():
                missing.append(f)
        return missing

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        return cls(
            asset_id=d.get("asset_id", ""),
            name=d.get("name", ""),
            location=d.get("location", ""),
            responsible=d.get("responsible", ""),
            category=d.get("category", ""),
            printed=d.get("printed", False),
            print_batch=d.get("print_batch"),
            created_at=d.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


@dataclass
class BatchRecord:
    batch_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    asset_ids: List[str] = field(default_factory=list)
    label_size: str = "medium"
    code_style: str = "barcode"
    output_path: str = ""
    count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BatchRecord":
        return cls(
            batch_id=d.get("batch_id", uuid.uuid4().hex[:8]),
            timestamp=d.get("timestamp", ""),
            asset_ids=d.get("asset_ids", []),
            label_size=d.get("label_size", "medium"),
            code_style=d.get("code_style", "barcode"),
            output_path=d.get("output_path", ""),
            count=d.get("count", 0),
        )


LABEL_SIZES = {
    "small": {"width": 200, "height": 100, "cols": 1},
    "medium": {"width": 300, "height": 150, "cols": 1},
    "large": {"width": 400, "height": 200, "cols": 1},
}

CODE_STYLES = ("barcode", "qrcode")
