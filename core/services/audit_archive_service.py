"""Reversible audit rotation: preserve a compressed snapshot before clearing active history."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.services import audit_service as audit

ARCHIVE_NAME = re.compile(r"^audit_(\d{8}T\d{12}Z)_(\d+)_([0-9a-f]{32})\.json\.gz$")


class HistoryChangedError(ValueError):
    pass


def history_revision(entries: list[dict]) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def archive_directory() -> Path:
    return Path(audit._get_history_file_path()).parent / "archives"


def storage_info(entries: list[dict]) -> dict:
    active = Path(audit._get_history_file_path())
    archives = []
    directory = archive_directory()
    if directory.is_dir():
        for path in sorted(directory.iterdir(), reverse=True):
            match = ARCHIVE_NAME.fullmatch(path.name)
            if match and path.is_file() and not path.is_symlink():
                archives.append({"filename": path.name, "event_count": int(match[2]),
                                 "bytes": path.stat().st_size, "created_at": datetime.strptime(match[1], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc).isoformat()})
    return {"active_bytes": active.stat().st_size if active.is_file() else 0,
            "active_count": len(entries), "revision": history_revision(entries),
            "archive_count": len(archives), "archived_bytes": sum(item["bytes"] for item in archives), "archives": archives}


def archive_and_reset(expected_revision: str) -> dict:
    # Share the core file lock with Streamlit's in-process atomic appends.
    with audit._file_lock:
        path = audit._get_history_file_path()
        entries = audit._load_unlocked(path)
        if history_revision(entries) != expected_revision:
            raise HistoryChangedError("History changed. Refresh and review the latest event count before archiving.")
        if not entries:
            raise HistoryChangedError("Active history is already empty.")
        directory = archive_directory()
        directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        name = f"audit_{now.strftime('%Y%m%dT%H%M%S%fZ')}_{len(entries)}_{uuid4().hex}.json.gz"
        target = directory / name
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                snapshot = {"schema_version": 1, "archived_at": now.isoformat(), "event_count": len(entries), "entries": entries}
                with gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as compressed:
                    compressed.write(json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            # Clearing happens only after the complete, durable archive exists.
            audit._save_unlocked(path, [])
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        return {"filename": name, "archived_count": len(entries), "bytes": target.stat().st_size,
                "download_url": f"/api/audit/archives/{name}"}


def archive_path(filename: str) -> Path:
    if not ARCHIVE_NAME.fullmatch(filename):
        raise FileNotFoundError("Unknown archive")
    directory = archive_directory().resolve()
    target = directory / filename
    if target.is_symlink() or target.resolve().parent != directory or not target.is_file():
        raise FileNotFoundError("Unknown archive")
    return target
