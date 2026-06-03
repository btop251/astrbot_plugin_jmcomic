from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JmTaskRecord:
    task_id: str
    task_type: str
    target_id: str
    requested_by: str
    request_origin: str
    output_format: str = ""
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at: str = ""
    finished_at: str = ""
    save_dir: str = ""
    uploaded: bool = False
    cancel_requested: bool = False
    summary: str = ""
    error_type: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JmTaskRecord":
        known_fields = cls.__dataclass_fields__.keys()
        filtered = {key: value for key, value in data.items() if key in known_fields}
        return cls(**filtered)
