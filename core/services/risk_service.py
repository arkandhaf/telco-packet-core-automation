"""Explainable rule checks and an allowlisted dataset for future anomaly models.

No trained model is loaded. Scores are review priorities, not probabilities.
"""
import hashlib
import json
from typing import Any, Dict, List

from core.models.payload import ProvisioningPayload
from core.parsers.mml_parser import parse_mml_script_commands

FEATURE_VERSION = 1
POLICY_VERSION = "rules-v1"


def extract_features(payload: Dict[str, Any], script: str) -> Dict[str, Any]:
    data = ProvisioningPayload.model_validate(payload).to_dict()
    domains = [domain.strip() for domain in data["app_domain"].split(",") if domain.strip()]
    commands = parse_mml_script_commands(script)
    return {
        "product_type": data["product_type"],
        "user_profile": data["user_profile"],
        "charging_type": data["charging_type"],
        "domain_count": len(domains),
        "wildcard_count": sum(domain.startswith("*.") for domain in domains),
        "command_count": len(commands),
        "undo_command_count": sum(command.startswith("undo ") for command in commands),
        "header_enrichment_enabled": data["header_enrichment"] == "Yes",
        "qci": int(data["qci_val"].split()[0]),
        "throttled": data["speed_limit"] != "Full Speed",
        "capping_requested": data["capping_option"] not in {"No Capping", "Custom / No Capping"},
    }


def assess_change(payload: Dict[str, Any], script: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = ProvisioningPayload.model_validate(payload).to_dict()
    features = extract_features(data, script)
    reasons = []
    score = 0
    if data["product_type"] in {"Revamp", "Reguler Update"}:
        score += 40
        reasons.append("Existing configuration changes require an actual pre-change snapshot for rollback.")
    if features["undo_command_count"]:
        score += 25
        reasons.append("Provisioning removes existing bindings or objects.")
    if features["wildcard_count"]:
        score += 10
        reasons.append("Wildcard domains broaden traffic matching; review the intended scope.")
    if features["domain_count"] > 10:
        score += 15
        reasons.append("More than ten domains increases the matching scope.")
    if features["header_enrichment_enabled"]:
        score += 15
        reasons.append("Header enrichment changes sensitive traffic handling.")
    unsupported = features["qci"] != 9 or features["throttled"] or features["capping_requested"]
    if unsupported:
        score += 30
        reasons.append("QCI, speed and capping choices appear only in comments; this engine does not provision those policies.")
    prior = next((entry.get("Payload", {}) for entry in (history or [])
                  if entry.get("Action") == "GENERATE MML"
                  and isinstance(entry.get("Payload"), dict)
                  and entry.get("Payload", {}).get("apn_name") == data["apn_name"]
                  and entry.get("Payload", {}).get("app_name") == data["app_name"]), None)
    if prior and any(str(prior.get(key)) != data[key] for key in ("rg_val", "sid_val")):
        score += 20
        reasons.append("RG/SID differ from the latest generated request for this APN and application; this is not a device baseline.")
    score = min(score, 100)
    blockers = ["Live execution requires device pre-checks, shared-object ownership checks and a tested snapshot rollback; these are not implemented."]
    if unsupported:
        blockers.append("Requested QoS/capping policies are not implemented in the generator.")
    return {
        "policy_version": POLICY_VERSION, "feature_version": FEATURE_VERSION,
        "score": score, "level": "HIGH" if score >= 50 else "MEDIUM" if score >= 20 else "LOW",
        "reasons": reasons, "live_blockers": blockers, "features": features,
        # Fingerprint only for artifacts/correlation; never use as a predictive feature.
        "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
    }


def export_feature_jsonl(history: List[Dict[str, Any]]) -> str:
    """Export captured pre-execution features, not payloads, raw logs or secrets.

    Legacy records without versioned features are skipped. Status is metadata,
    never a configuration-risk label. Simulation is explicitly separated.
    """
    rows = []
    for entry in history:
        metadata = entry.get("Metadata", {})
        if not isinstance(metadata, dict):
            continue
        assessment = metadata.get("assessment", {})
        if not isinstance(assessment, dict):
            continue
        features = assessment.get("features")
        if not isinstance(features, dict) or assessment.get("feature_version") != FEATURE_VERSION:
            continue
        allowed = {
            key: features[key] for key in (
                "product_type", "user_profile", "charging_type", "domain_count", "wildcard_count",
                "command_count", "undo_command_count", "header_enrichment_enabled", "qci", "throttled", "capping_requested"
            ) if key in features
        }
        rows.append(json.dumps({
            "event_id": entry.get("Event ID"), "work_order_id": entry.get("WO ID"),
            "timestamp": entry.get("Timestamp"), "action": entry.get("Action"),
            "engine_version": entry.get("Engine Version"), "policy_version": assessment.get("policy_version"),
            "feature_version": FEATURE_VERSION, "features": allowed,
            "observation": {"execution_mode": metadata.get("execution_mode", "generation"),
                            "status": entry.get("Status"), "risk_label": None},
        }, ensure_ascii=False, allow_nan=False))
    return "\n".join(rows) + ("\n" if rows else "")
