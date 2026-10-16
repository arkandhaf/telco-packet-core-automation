import io
import re
import zipfile
import pandas as pd
from typing import Dict, List, Any, Tuple
from core.engines.huawei_service_v import generate_huawei_mml_script, generate_rollback_script
from core.models.payload import ProvisioningPayload

REQUIRED_COLUMNS = {"product_type", "apn_name", "app_name", "rg_val", "sid_val"}
MAX_BATCH_ROWS = 1000

# =============================================================================
# COLUMN ALIASES MAPPING DICTIONARY
# =============================================================================
COLUMN_ALIASES: Dict[str, List[str]] = {
    "product_type": [
        "product_type", "product_requirement", "tipe_produk", "jenis_produk",
        "req_type", "requirement_type", "product_requirement_type"
    ],
    "user_profile": [
        "user_profile", "profile", "tipe_profile", "user_profile_type",
        "profile_type"
    ],
    "apn_name": [
        "apn_name", "apn", "nama_apn", "access_point_name", "apn_id",
        "target_apn"
    ],
    "charging_type": [
        "charging_type", "charging_profile", "tipe_charging", "billing_type",
        "charging", "charging_method"
    ],
    "rg_val": [
        "rg_val", "rg", "rg_id", "rating_group", "rating_group_id", "rating_group_val"
    ],
    "sid_val": [
        "sid_val", "sid", "sid_id", "service_id", "service_id_val"
    ],
    "capping_option": [
        "capping_option", "capping", "capping_limit", "kuota_capping",
        "zero_rating_capping", "capping_allocation"
    ],
    "header_enrichment": [
        "header_enrichment", "he", "he_required", "header_enrichment_required",
        "is_header_enrichment_required"
    ],
    "he_key": [
        "he_key", "header_enrichment_key", "key_he"
    ],
    "he_cipher": [
        "he_cipher", "header_enrichment_cipher", "cipher_he"
    ],
    "speed_limit": [
        "speed_limit", "speed", "kecepatan", "speed_limitation", "bandwidth",
        "qos_speed", "speed_limitation_policy"
    ],
    "qci_val": [
        "qci_val", "qci", "qci_profile", "qci_assignment", "qci_value"
    ],
    "app_category": [
        "app_category", "kategori_aplikasi", "category", "app_cat", "apps_category"
    ],
    "app_name": [
        "app_name", "nama_aplikasi", "app", "application", "aplikasi_target",
        "apps_target_name", "target_app"
    ],
    "app_domain": [
        "app_domain", "domain", "url", "target_domain", "domain_details",
        "domain_ip", "domain_ip_target_details"
    ],
}

DEFAULT_PAYLOAD_VALUES: Dict[str, str] = {
    "product_type": "New Product",
    "user_profile": "New",
    "apn_name": "internet_im3",
    "charging_type": "Zero Rating",
    "rg_val": "11010",
    "sid_val": "11001000",
    "capping_option": "No Capping",
    "header_enrichment": "No",
    "he_key": "",
    "he_cipher": "",
    "speed_limit": "Full Speed",
    "qci_val": "9 (Default Internet)",
    "app_category": "Well Known Apps",
    "app_name": "app",
    "app_domain": "",
}


def clean_header_name(header: str) -> str:
    s = str(header).strip().lower()
    s = re.sub(r"[\s\-\.]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s.strip("_")


def map_ciq_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    mapped_df = df.copy()
    raw_cols = list(mapped_df.columns)
    mapping_report: Dict[str, str] = {}
    rename_dict: Dict[str, str] = {}

    cleaned_names = [clean_header_name(c) for c in raw_cols]
    if len(set(cleaned_names)) != len(cleaned_names):
        raise ValueError("Duplicate or ambiguous column names; use one column per parameter")
    cleaned_raw_map = dict(zip(cleaned_names, raw_cols))

    for canonical_key, aliases in COLUMN_ALIASES.items():
        candidates = [original for cleaned, original in cleaned_raw_map.items()
                      if cleaned in {clean_header_name(alias) for alias in aliases}]
        if len(candidates) > 1:
            raise ValueError(f"Multiple columns map to {canonical_key}: {candidates}")
        found_col = candidates[0] if candidates else None

        if found_col:
            rename_dict[found_col] = canonical_key
            mapping_report[canonical_key] = f"Mapped from '{found_col}'"
        if canonical_key not in mapping_report:
            mapping_report[canonical_key] = "REQUIRED: missing column" if canonical_key in REQUIRED_COLUMNS else f"Default: {DEFAULT_PAYLOAD_VALUES.get(canonical_key, '')}"

    mapped_df.rename(columns=rename_dict, inplace=True)
    return mapped_df, mapping_report


def sanitize_value(val: Any, default: str = "") -> str:
    if pd.isna(val) or val is None:
        return default
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return default
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def build_row_payload(row: pd.Series) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, def_val in DEFAULT_PAYLOAD_VALUES.items():
        if key in REQUIRED_COLUMNS and (key not in row.index or not sanitize_value(row[key])):
            raise ValueError(f"Missing required value: {key}")
        if key in row.index:
            payload[key] = sanitize_value(row[key], default=def_val)
        else:
            payload[key] = def_val
    return ProvisioningPayload.model_validate(payload).to_dict()


def process_ciq_batch(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df.empty or len(df) > MAX_BATCH_ROWS:
        raise ValueError(f"Batch must contain 1–{MAX_BATCH_ROWS} rows")
    mapped_df, _ = map_ciq_dataframe(df)
    missing = REQUIRED_COLUMNS - set(mapped_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    results: List[Dict[str, Any]] = []
    seen_rules = set()
    app_domains = {}

    for idx, (_, row) in enumerate(mapped_df.iterrows(), start=1):
        try:
            payload = build_row_payload(row)
            rule_key = (payload["apn_name"], payload["app_name"], payload["rg_val"], payload["sid_val"])
            if rule_key in seen_rules:
                raise ValueError("Duplicate target rule in the same batch")
            seen_rules.add(rule_key)
            domain_definition = tuple(sorted(domain.strip() for domain in payload["app_domain"].split(",") if domain.strip()))
            if payload["app_name"] in app_domains and app_domains[payload["app_name"]] != domain_definition:
                raise ValueError("Conflicting domains for shared application objects in the same batch")
            app_domains[payload["app_name"]] = domain_definition
            mml_script = generate_huawei_mml_script(payload)
            rollback_script = generate_rollback_script(payload)
        except ValueError as exc:
            # Pydantic error text includes input values, which may be secrets.
            if hasattr(exc, "errors"):
                fields = ", ".join(".".join(map(str, error["loc"])) or "payload" for error in exc.errors())
                raise ValueError(f"CIQ row {idx + 1}: invalid fields: {fields}") from None
            raise ValueError(f"CIQ row {idx + 1}: {exc}") from None

        apn_clean = payload["apn_name"].replace(" ", "_")
        app_clean = payload["app_name"].replace(" ", "_")
        row_id = f"ROW_{idx:03d}_{apn_clean}_{app_clean}"

        results.append({
            "index": idx,
            "row_id": row_id,
            "apn_name": payload["apn_name"],
            "app_name": payload["app_name"],
            "product_type": payload["product_type"],
            "charging_type": payload["charging_type"],
            "rg_val": payload["rg_val"],
            "sid_val": payload["sid_val"],
            "speed_limit": payload["speed_limit"],
            "qci_val": payload["qci_val"],
            "mml_script": mml_script,
            "rollback_script": rollback_script,
            "mml_filename": f"MML_{row_id}.txt",
            "rollback_filename": f"ROLLBACK_{row_id}.txt",
            "payload": payload,
        })

    return results


def generate_combined_script_txt(batch_results: List[Dict[str, Any]]) -> str:
    lines: List[str] = [
        "// ============================================================================",
        "// RELPOOL ENGINE - COMBINED BATCH MML PROVISIONING SCRIPT",
        f"// Total Commands in Batch : {len(batch_results)} Items",
        "// Target Nodes Architecture: HUAWEI SERVICE-V & UPCC",
        "// ============================================================================\n"
    ]

    for item in batch_results:
        sep = "=" * 70
        lines.append(f"// {sep}")
        lines.append(f"// ITEM #{item['index']} | APN: {item['apn_name']} | APP: {item['app_name']} | TYPE: {item['product_type']}")
        lines.append(f"// {sep}\n")
        lines.append(item["mml_script"])
        lines.append("\n\n")

    return "\n".join(lines)


def generate_batch_zip(batch_results: List[Dict[str, Any]]) -> bytes:
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in batch_results:
            zf.writestr(f"scripts/{item['mml_filename']}", item["mml_script"])
            zf.writestr(f"rollbacks/{item['rollback_filename']}", item["rollback_script"])

        combined_txt = generate_combined_script_txt(batch_results)
        zf.writestr("ALL_MML_SCRIPTS.txt", combined_txt)

        manifest_rows = [
            {
                "No": item["index"],
                "Row_ID": item["row_id"],
                "APN_Name": item["apn_name"],
                "App_Name": item["app_name"],
                "Product_Type": item["product_type"],
                "Rating_Group": item["rg_val"],
                "Service_ID": item["sid_val"],
                "QoS_Speed": item["speed_limit"],
                "QCI": item["qci_val"],
                "MML_File": f"scripts/{item['mml_filename']}",
                "Rollback_File": f"rollbacks/{item['rollback_filename']}",
            }
            for item in batch_results
        ]
        manifest_df = pd.DataFrame(manifest_rows)
        manifest_csv = manifest_df.to_csv(index=False)
        zf.writestr("BATCH_MANIFEST.csv", manifest_csv)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def get_sample_ciq_csv() -> str:
    return """product_type,user_profile,apn_name,charging_type,rg_val,sid_val,capping_option,header_enrichment,speed_limit,qci_val,app_category,app_name,app_domain
New Product,New,internet_im3,Zero Rating,11010,11001000,20 MB/day,No,Full Speed,9 (Default Internet),Well Known Apps,TikTok,"*.tiktok.com, *.v2.tiktokcdn.com"
New Product,Existing,b2b_corporate,Special Rate (differentiate RG),20000,20001000,No Capping,No,Full Speed,9 (Default Internet),Local Apps,Gojek Driver,"*.gojek.com, *.driver.gojek.co.id"
New Product,New,internet_im3,Zero Rating,30000,30001000,No Capping,No,Full Speed,1 (Voice/Low Latency),Well Known Apps,Mobile Legends,"*.mobilelegends.com, *.moonton.com"
Reguler Update,Existing,internet_im3,Zero Rating,11010,11001000,No Capping,No,Full Speed,9 (Default Internet),Well Known Apps,YouTube,"*.youtube.com, *.googlevideo.com"
"""
