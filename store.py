import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


JOURNAL_PATH = Path(__file__).resolve().parent / "trade_history.jsonl"


def append_trade_record(record: Dict[str, Any]) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with JOURNAL_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_trade_records(limit: int = 100) -> List[Dict[str, Any]]:
    if not JOURNAL_PATH.exists():
        return []

    records: List[Dict[str, Any]] = []
    with JOURNAL_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records[-limit:]


def today_realized_pnl_usdt(records: List[Dict[str, Any]]) -> float:
    today_prefix = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    for record in records:
        timestamp = str(record.get("timestamp", ""))
        if not timestamp.startswith(today_prefix):
            continue
        try:
            total += float(record.get("realized_pnl_usdt", 0.0))
        except (TypeError, ValueError):
            continue
    return total