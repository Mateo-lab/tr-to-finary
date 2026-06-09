"""Track which transactions have been synced to avoid duplicates."""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime


STATE_FILE = ".sync_state.json"


@dataclass
class SyncState:
    synced_transaction_ids: set[str] = field(default_factory=set)
    last_sync: str | None = None
    finary_account: str | None = None

    def has_transaction(self, transaction_id: str) -> bool:
        return transaction_id in self.synced_transaction_ids

    def mark_synced(self, transaction_id: str):
        self.synced_transaction_ids.add(transaction_id)

    def mark_batch_synced(self, transaction_ids: list[str]):
        self.synced_transaction_ids.update(transaction_ids)


def load_state(directory: str | Path = ".") -> SyncState:
    path = Path(directory) / STATE_FILE
    if not path.exists():
        return SyncState()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return SyncState(
        synced_transaction_ids=set(data.get("synced_transaction_ids", [])),
        last_sync=data.get("last_sync"),
        finary_account=data.get("finary_account"),
    )


def save_state(state: SyncState, directory: str | Path = "."):
    path = Path(directory) / STATE_FILE
    data = {
        "synced_transaction_ids": sorted(state.synced_transaction_ids),
        "last_sync": datetime.now().isoformat(),
        "finary_account": state.finary_account,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
