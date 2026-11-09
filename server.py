"""Local command center: real core APIs and the compiled Astro frontend.

Run one process with ``python server.py`` after ``npm --prefix web run build``.
SSH credentials and live-execution gates remain owned by core.transports.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.engines.huawei_service_v import (
    _parse_domains, _sanitize_identifier, _sanitize_rg_sid,
    generate_huawei_mml_script, generate_rollback_script,
)
from core.models.payload import ProvisioningPayload
from core.parsers.ciq_parser import (
    generate_batch_zip, generate_combined_script_txt, get_sample_ciq_csv,
    map_ciq_dataframe, process_ciq_batch,
)
from core.services.audit_service import build_audit_log, load_history, save_history, redact_secrets
from core.services.audit_archive_service import HistoryChangedError, archive_and_reset, archive_path, storage_info
from core.transports.ssh_gateway import execute_to_testbed

ROOT = Path(__file__).resolve().parent
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_audit_lock = threading.RLock()
logger = logging.getLogger(__name__)
app = FastAPI(title="RELPOOL Core Command Center", version="2.2.0")


@app.middleware("http")
async def frontend_cache_control(request: Request, call_next):
    response = await call_next(request)
    asset = request.url.path
    if response.status_code == 200 and asset.startswith(("/assets/", "/_astro/")) and asset.endswith((".js", ".mjs")):
        # Browser scripts must never depend on Windows registry MIME associations.
        response.headers["Content-Type"] = "text/javascript; charset=utf-8"
    if response.headers.get("content-type", "").startswith("text/html") or asset.startswith(("/api/", "/assets/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    # Never echo credentials or raw CLI tokens through validation errors.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]})


@app.exception_handler(ValueError)
async def value_error(_request: Request, exc: ValueError):
    if isinstance(exc, ValidationError):
        fields = ", ".join(".".join(map(str, e["loc"])) or "payload" for e in exc.errors())
        return JSONResponse(status_code=422, content={"detail": f"Invalid fields: {fields}"})
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(OSError)
async def storage_error(_request: Request, exc: OSError):
    logger.error("Command center storage failure: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Storage unavailable. Check audit/configuration storage before retrying."})


def record_event(**kwargs: Any) -> dict:
    # Serialize this process's read/modify/write calls to the legacy snapshot API.
    # As with Streamlit, use a single process with the JSON audit store.
    with _audit_lock:
        history = load_history()
        entry = build_audit_log(history_count=len(history), **kwargs)
        save_history([entry, *history])
        return entry


def read_nodes() -> tuple[dict, list[dict]]:
    configuration = yaml.safe_load((ROOT / "configs" / "nodes.yaml").read_text(encoding="utf-8"))
    clusters = configuration.get("clusters", {})
    nodes = [{**node, "cluster": key, "region": cluster.get("region", "")}
             for key, cluster in clusters.items() for node in cluster.get("nodes", [])]
    return clusters, nodes


def hierarchy(payload: dict) -> dict:
    apn = _sanitize_identifier(payload["apn_name"])
    application = _sanitize_identifier(payload["app_name"])
    rg = _sanitize_rg_sid(payload["rg_val"], "11010")
    sid = _sanitize_rg_sid(payload["sid_val"], "11001000")
    domains = _parse_domains(payload["app_domain"], application)
    suffixes = [f"_{index}" for index in range(1, len(domains) + 1)] if len(domains) > 1 else [""]
    revamp = "_v2" if payload["product_type"] == "Revamp" else ""
    return {
        "apn_profile": f"crbn_{apn}_sy", "rule_name": f"r_{application}{revamp}_{rg}_{sid}",
        "filter_group": f"fg_gaspol_{application}", "category_group": f"catg_{rg}_{sid}",
        "hosts": [f"h_{application}{suffix}" for suffix in suffixes],
        "filters": [f"f_{application}{suffix}" for suffix in suffixes], "domains": domains,
        "charging_ids": [f"cbbid_on_{rg}", f"cbbid_off_{rg}_{sid}"],
        "product_type": payload["product_type"],
    }


@app.get("/api/system-info")
def system_info():
    clusters, nodes = read_nodes()
    with _audit_lock:
        history = load_history()
    today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    def is_today(entry):
        try:
            timestamp = datetime.fromisoformat(entry.get("Timestamp", "").replace("Z", "+00:00"))
            return timestamp.astimezone(ZoneInfo("Asia/Jakarta")).date() == today
        except (ValueError, TypeError):
            return False
    stats = {
        "total_wo": len({row.get("WO ID", row.get("Event ID", str(i))) for i, row in enumerate(history)}),
        "wo_today": len({row.get("WO ID", str(i)) for i, row in enumerate(history) if is_today(row)}),
        "generated_count": sum(row.get("Action") in {"GENERATE MML", "BATCH_MML_GEN"} for row in history),
        "executed_count": sum(row.get("Action") == "TESTBED_PUSH" and row.get("Status") in {"SUCCESS", "SENT_UNVERIFIED"} for row in history),
    }
    return {"clusters": clusters, "nodes": nodes, "statistics": stats,
            "engine": {"version": "v2.2-modular", "vendor": "Huawei UPCC", "architecture": "Service-V CLI"},
            "live_enabled": os.getenv("RELPOOL_ENABLE_LIVE", "").lower() == "true",
            "gateway_status": "LIVE ENABLED" if os.getenv("RELPOOL_ENABLE_LIVE", "").lower() == "true" else "SIMULATION",
            "timezone": "Asia/Jakarta"}


@app.post("/api/preview")
def preview(payload: ProvisioningPayload):
    normalized = payload.to_dict()
    if normalized["product_type"] != "Revamp" and not normalized["app_domain"]:
        raise ValueError("Explicit target domains are required; domains cannot be inferred from an application name")
    return {"hierarchy_preview": hierarchy(normalized), "payload": redact_secrets(normalized)}


@app.post("/api/generate")
def generate(payload: ProvisioningPayload):
    normalized = payload.to_dict()
    mml = generate_huawei_mml_script(normalized)
    rollback = generate_rollback_script(normalized)
    entry = record_event(action="GENERATE MML", apn=normalized["apn_name"], app=normalized["app_name"], payload=normalized)
    return {"mml_script": mml, "rollback_script": rollback, "payload": redact_secrets(normalized),
            "hierarchy_preview": hierarchy(normalized), "audit_entry": entry}


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mml_script: str = Field(min_length=1, max_length=2_000_000)
    is_live: bool = False
    apn_name: str
    app_name: str
    payload: ProvisioningPayload
    host: str | None = None


@app.post("/api/ssh/execute")
def execute(body: ExecutionRequest):
    normalized = body.payload.to_dict()
    clean_cmds = [line.strip() for line in body.mml_script.splitlines()
                  if line.strip() and not line.lstrip().startswith("//")]
    if not clean_cmds or len(clean_cmds) > 10_000:
        raise HTTPException(422, "Provide 1–10000 active commands")
    if body.is_live:
        _, nodes = read_nodes()
        if body.host not in {node["ip"] for node in nodes}:
            raise HTTPException(422, "Select a configured cluster node")
        # A caller cannot attach arbitrary commands to an unrelated CIQ audit payload.
        expected = [line.strip() for line in generate_huawei_mml_script(normalized).splitlines()
                    if line.strip() and not line.lstrip().startswith("//")]
        if clean_cmds != expected:
            raise HTTPException(422, "Script differs from the validated CIQ. Generate it again before live execution.")
    # Verify persistence before performing a network side effect.
    attempt = record_event(action="TESTBED_ATTEMPT", apn=normalized["apn_name"], app=normalized["app_name"],
                           payload=normalized, target_node=body.host or "LOCAL_SIMULATION", status="PENDING")
    results = execute_to_testbed(clean_cmds, is_live=body.is_live, host=body.host)
    results = [re.sub(r"(header-enrichment\s+key\s+)\S+(\s+cipher\s+)\S+",
                      r"\1[REDACTED]\2[REDACTED]", line, flags=re.IGNORECASE) for line in results]
    status = "SIMULATED" if not body.is_live else "UNKNOWN"
    for candidate in ("FAILED", "PARTIAL_FAILED", "UNKNOWN", "SENT_UNVERIFIED"):
        if any(f"[{candidate}]" in line for line in results):
            status = candidate
            break
    entry = record_event(action="TESTBED_PUSH", apn=normalized["apn_name"], app=normalized["app_name"],
                         payload=normalized, target_node=body.host or "LOCAL_SIMULATION", status=status,
                         work_order_id=attempt["WO ID"], metadata={"command_count": len(clean_cmds), "is_live": body.is_live})
    return {"logs": results, "command_count": len(clean_cmds), "audit_entry": entry, "status": status}


@app.get("/api/batch/sample")
def batch_sample():
    return Response(get_sample_ciq_csv(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="TEMPLATE_CIQ_STANDARD.csv"'})


@app.post("/api/batch/process")
def batch_process(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(415, "Upload a CSV, XLSX or XLS file")
    try:
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        file.file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Upload limit is 10 MB")
    try:
        stream = io.BytesIO(content)
        if extension == ".csv":
            df = pd.read_csv(stream, dtype=str, keep_default_na=False, nrows=1001)
        else:
            df = pd.read_excel(stream, dtype=str, keep_default_na=False, nrows=1001,
                               engine="xlrd" if extension == ".xls" else "openpyxl")
    except ImportError:
        raise HTTPException(503, "Spreadsheet reader unavailable. Install requirements.txt.") from None
    except Exception:
        raise HTTPException(422, "Cannot read this file. Check the encoding and spreadsheet format.") from None
    mapped, report = map_ciq_dataframe(df)
    results = process_ciq_batch(mapped)
    combined = generate_combined_script_txt(results)
    archive = generate_batch_zip(results)
    entry = record_event(action="BATCH_MML_GEN", apn=", ".join(sorted({r["apn_name"] for r in results})),
                         app=f"{len(results)} applications", payload={"rows": [r["payload"] for r in results]},
                         status="BATCH_SUCCESS", metadata={"filename": Path(file.filename).name, "row_count": len(results)})
    # The raw preview must not expose HE keys/ciphers under aliased column names.
    from core.parsers.ciq_parser import COLUMN_ALIASES, clean_header_name
    secret_aliases = {clean_header_name(alias) for field in ("he_key", "he_cipher") for alias in COLUMN_ALIASES[field]}
    safe_columns = [column for column in df.columns if clean_header_name(column) not in secret_aliases]
    safe_results = [{**row, "payload": redact_secrets(row["payload"])} for row in results]
    return {"raw_preview": df[safe_columns].head(50).fillna("").to_dict(orient="records"),
            "mapping_report": report, "batch_results": safe_results, "combined_txt": combined,
            "zip_base64": base64.b64encode(archive).decode("ascii"), "audit_entry": entry}


@app.get("/api/audit")
def audit():
    with _audit_lock:
        return load_history()


def filtered_audit(entries: list[dict], action: str, search: str) -> list[dict]:
    needle = search.strip().casefold()
    return [entry for entry in entries if (action == "All" or entry.get("Action") == action)
            and (not needle or needle in json_audit_text(entry))]


def json_audit_text(entry: dict) -> str:
    import json
    return json.dumps(entry, ensure_ascii=False).casefold()


@app.get("/api/audit/page")
def audit_page(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
               action: str = "All", search: str = Query("", max_length=500)):
    with _audit_lock:
        entries = load_history()
        rows = filtered_audit(entries, action, search)
        return {"entries": rows[offset:offset + limit], "total": len(entries), "filtered_total": len(rows),
                "offset": offset, "limit": limit, "storage": storage_info(entries)}


@app.get("/api/audit/export")
def export_audit(action: str = "All", search: str = Query("", max_length=500)):
    import csv
    import json
    with _audit_lock:
        entries = filtered_audit(load_history(), action, search)
    output = io.StringIO()
    fields = ["Timestamp", "WO ID", "Action", "Target Node", "APN", "App Target", "Status", "Payload"]
    writer = csv.writer(output)
    writer.writerow(fields)
    for entry in entries:
        cells = []
        for field in fields:
            value = entry.get(field, "")
            value = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            cells.append("'" + value if re.match(r"^\s*[=+@-]", value) else value)
        writer.writerow(cells)
    return Response("\ufeff" + output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="RELPOOL_AUDIT.csv"'})


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["ARCHIVE_AND_RESET"]
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


@app.post("/api/audit/archive")
def archive_audit(body: ArchiveRequest):
    with _audit_lock:
        try:
            return archive_and_reset(body.expected_revision)
        except HistoryChangedError as exc:
            raise HTTPException(409, str(exc)) from None


@app.get("/api/audit/archives/{filename}")
def download_audit_archive(filename: str):
    try:
        path = archive_path(filename)
    except FileNotFoundError:
        raise HTTPException(404, "Unknown audit archive") from None
    return FileResponse(path, media_type="application/gzip", filename=filename)


# Keep API misses as JSON and mount the static frontend after all API routes.
@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def unknown_api(path: str):
    raise HTTPException(404, "Unknown API endpoint")


DIST = ROOT / "web" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="command-center")
else:
    @app.get("/", include_in_schema=False)
    def build_required():
        return JSONResponse(status_code=503, content={"detail": "Build the frontend: npm --prefix web ci && npm --prefix web run build"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
