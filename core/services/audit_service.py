"""Atomic audit persistence for a single application process.

Use append_history for new events so concurrent Streamlit sessions do not
overwrite stale snapshots. Multi-process deployments need a database.
"""
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_FILE = str(PROJECT_ROOT / "data" / "audit" / "audit_history.json")
MAX_HISTORY_ENTRIES = 200  # Display limit only; persistence never truncates evidence.
_file_lock = threading.Lock()


def redact_secrets(value: Any) -> Any:
    """Redact recursively before persistence or display, without modifying inputs."""
    if isinstance(value, dict):
        return {
            key: redact_secrets(item) for key, item in value.items()
            if not any(token in str(key).lower() for token in ("password", "secret", "token", "cipher", "he_key", "credential", "private_key", "api_key", "authorization"))
        }
    if isinstance(value, (list, tuple)):
        return [redact_secrets(item) for item in value]
    return value


def _get_history_file_path() -> str:
    legacy = PROJECT_ROOT / "data" / "audit_history.json"
    if HISTORY_FILE == str(PROJECT_ROOT / "data" / "audit" / "audit_history.json") and not os.path.exists(HISTORY_FILE) and legacy.exists():
        return str(legacy)
    return HISTORY_FILE


def _load_unlocked(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError("Audit history must be a list of objects")
        return redact_secrets(data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid audit history at {path}; restore or repair this file before continuing") from exc


def _save_unlocked(path: str, history: List[Dict[str, Any]]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, suffix=".tmp", delete=False) as handle:
            temp_path = handle.name
            json.dump(redact_secrets(history), handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def load_history() -> List[Dict[str, Any]]:
    with _file_lock:
        return _load_unlocked(_get_history_file_path())


def save_history(history_list: List[Dict[str, Any]]) -> None:
    """Legacy snapshot API; callers adding events should use append_history."""
    with _file_lock:
        _save_unlocked(_get_history_file_path(), history_list)


def append_history(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    return append_history_entries([entry])


def append_history_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Persist a completed batch in one atomic write."""
    with _file_lock:
        path = _get_history_file_path()
        history = _load_unlocked(path)
        history = redact_secrets(entries) + history
        _save_unlocked(path, history)
        return history


def build_audit_log(action: str, apn: str, app: str, payload: Dict[str, Any],
                    target_node: str = "LOCAL_ENGINE", status: str = "SCRIPT_GENERATED",
                    history_count: int = 0, metadata: Optional[Dict[str, Any]] = None,
                    work_order_id: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    event_id = str(uuid4())
    return {
        "Timestamp": now.isoformat(timespec="microseconds"),
        "WO ID": work_order_id or f"WO-RELPOOL-{now.strftime('%Y%m%d')}-{event_id.replace('-', '')}",
        "Event ID": event_id,
        "Schema Version": 1,
        "Engine Version": "2.3.0",
        "Action": action, "Target Node": target_node, "APN": apn,
        "App Target": app, "Status": status,
        "Payload": redact_secrets(payload),
        "Metadata": redact_secrets(metadata or {}),
    }
