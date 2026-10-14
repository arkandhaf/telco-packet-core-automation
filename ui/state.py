"""Presentation helpers with consistent event counts and Jakarta dates."""
from datetime import datetime, timedelta, timezone

JAKARTA = timezone(timedelta(hours=7), "Asia/Jakarta")
GENERATION_ACTIONS = {"GENERATE MML", "BATCH_ROW_GENERATED"}
EXECUTION_ACTIONS = {"TESTBED_PUSH", "EXECUTION"}


def history_summary(history):
    today = datetime.now(JAKARTA).date()
    today_count = 0
    for entry in history:
        try:
            timestamp = datetime.fromisoformat(entry.get("Timestamp", ""))
            # Legacy timestamps have no timezone; treat them as Jakarta local time.
            timestamp = timestamp.replace(tzinfo=JAKARTA) if timestamp.tzinfo is None else timestamp.astimezone(JAKARTA)
            today_count += timestamp.date() == today
        except (ValueError, TypeError):
            continue
    return {
        "events": len(history),
        "work_orders": len({entry.get("WO ID") for entry in history if entry.get("WO ID")}),
        "today": today_count,
        "generated": sum(entry.get("Action") in GENERATION_ACTIONS for entry in history),
        "live_attempts": sum(entry.get("Action") in EXECUTION_ACTIONS
                             and entry.get("Status") != "SIMULATED"
                             and entry.get("Metadata", {}).get("execution_mode", "live") == "live"
                             for entry in history),
        "failures": sum(entry.get("Status") in {"FAILED", "PARTIAL_FAILED", "UNKNOWN"} for entry in history),
        "simulations": sum(entry.get("Status") == "SIMULATED" for entry in history),
    }
