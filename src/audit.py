"""
Backward compatibility bridge for src.audit.
Canonical implementation now lives in core.services.audit_service.
"""
from core.services.audit_service import (
    load_history,
    save_history,
    build_audit_log,
    HISTORY_FILE,
    MAX_HISTORY_ENTRIES
)

__all__ = [
    "load_history",
    "save_history",
    "build_audit_log",
    "HISTORY_FILE",
    "MAX_HISTORY_ENTRIES"
]
