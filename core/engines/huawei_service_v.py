import re
from typing import List, Dict, Any
from .base import BaseRuleEngine
from core.models.payload import ProvisioningPayload


# =============================================================================
# INPUT SANITIZATION HELPERS
# =============================================================================

def _sanitize_identifier(raw: str, default: str = "unknown") -> str:
    """
    Normalisasi nama identifier untuk APN / App:
      • Lowercase seluruhnya
      • Spasi, tanda hubung, dan titik → underscore
      • Buang karakter yang bukan [a-z0-9_]
      • Potong underscore ganda berulang
    """
    if not raw or not str(raw).strip():
        return default
    s = str(raw).strip().lower()
    s = re.sub(r"[\s\-\.]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s or default


def _sanitize_domain(raw_domain: str) -> str:
    """
    Bersihkan satu entri domain:
      • Buang prefix http:// atau https://
      • Buang trailing slash (/) dan spasi
      • Normalkan ke lowercase
    """
    d = str(raw_domain).strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.rstrip("/").strip()
    return d


def _parse_domains(domain_raw: str, app_fallback: str) -> List[str]:
    """
    Pisahkan input domain (bisa multi-line atau comma-separated) menjadi
    list domain yang sudah bersih.
    """
    raw = str(domain_raw).strip() if domain_raw else ""
    if not raw:
        return [f"*.{app_fallback}.com"]

    normalized = raw.replace("\r\n", ",").replace("\n", ",").replace("\t", ",")
    parts = normalized.split(",")

    cleaned: List[str] = []
    for part in parts:
        d = _sanitize_domain(part)
        if d:
            cleaned.append(d)

    return cleaned if cleaned else [f"*.{app_fallback}.com"]


def _sanitize_rg_sid(value: str, default: str) -> str:
    """Pastikan RG/SID hanya berisi digit. Handle float Excel seperti 11010.0."""
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s if s.isdigit() else default


def _build_domain_comment(domains: List[str]) -> str:
    lines = [f"// Domain Target ({len(domains)} entries):"]
    for d in domains:
        lines.append(f"//   {d}")
    return "\n".join(lines)


def _build_dpi_blocks(domains: List[str], app: str):
    host_lines: List[str] = []
    filter_lines: List[str] = []
    fg_bind_lines: List[str] = []
    multi = len(domains) > 1

    for idx, dom in enumerate(domains, start=1):
        h_name = f"h_{app}_{idx}" if multi else f"h_{app}"
        f_name = f"f_{app}_{idx}" if multi else f"f_{app}"

        host_lines.append(f"host {h_name} domain {dom} sequence 65535")
        filter_lines.append(f"filter {f_name} l34-protocol any host {h_name}")
        fg_bind_lines.append(f"filter-group fg_gaspol_{app} filter {f_name}")

    return (
        "\n".join(host_lines),
        "\n".join(filter_lines),
        "\n".join(fg_bind_lines),
    )


def _build_he_block(he_required: str, he_key: str, he_cipher: str) -> str:
    if he_required != "Yes" or not he_key:
        return ""
    return (
        "\n"
        "// HEADER ENRICHMENT SECURITY\n"
        f"header-enrichment key {he_key.strip()} cipher {he_cipher.strip()}"
    )


def _build_pcrf_block(qci_val: str, speed_limit: str, capping: str) -> str:
    sep = "-" * 50
    return (
        f"\n// {sep}\n"
        f"// PCRF UPCC SERVICE PLAN & QOS PROFILE\n"
        f"// QCI Assignment   : {qci_val}\n"
        f"// Speed Limitation : {speed_limit}\n"
        f"// Capping Limit    : {capping}\n"
        f"// {sep}"
    )


# =============================================================================
# HUAWEI SERVICE-V ENGINE CLASS
# =============================================================================

class HuaweiServiceVEngine(BaseRuleEngine):
    """
    Engine generator spesialis Huawei PCEF Service-V MML & PCRF UPCC.
    Mendukung skenario: New Product (Full Provisioning), Revamp (Cutover v2),
    dan Reguler Update (Delta Patch).
    """

    def generate_provisioning(self, payload: Dict[str, Any]) -> str:
        payload = ProvisioningPayload.model_validate(payload).to_dict()
        if payload["product_type"] != "Revamp" and not payload["app_domain"]:
            raise ValueError("Explicit target domains are required; domains cannot be inferred from an application name")
        req_type = str(payload.get("product_type", "New Product")).strip()
        apn = _sanitize_identifier(payload.get("apn_name", "internet_im3"), "internet_im3")
        app = _sanitize_identifier(payload.get("app_name", "app"), "app")

        rg = _sanitize_rg_sid(payload.get("rg_val", "11010"), "11010")
        sid = _sanitize_rg_sid(payload.get("sid_val", "11001000"), "11001000")
        capping = str(payload.get("capping_option", "No Capping")).strip()

        he_required = str(payload.get("header_enrichment", "No")).strip()
        he_key = str(payload.get("he_key", "")).strip()
        he_cipher = str(payload.get("he_cipher", "")).strip()

        speed_limit = str(payload.get("speed_limit", "Full Speed")).strip()
        qci_val = str(payload.get("qci_val", "9 (Default Internet)")).strip()

        app_cat = str(payload.get("app_category", "Well Known Apps")).strip()
        domain_raw = payload.get("app_domain", "")

        domains = _parse_domains(domain_raw, app)
        hosts_str, filters_str, fg_binds_str = _build_dpi_blocks(domains, app)
        he_block = _build_he_block(he_required, he_key, he_cipher)
        pcrf_block = _build_pcrf_block(qci_val, speed_limit, capping)
        domain_comment = _build_domain_comment(domains)

        # LOGIKA 1: REGULER UPDATE (DELTA PATCH)
        if req_type == "Reguler Update":
            return (
                f"// HUAWEI SERVICE-V MML SCRIPT - REGULER UPDATE (DELTA PATCH)\n"
                f"// Target APN : {apn}\n"
                f"// App Target : {app}  |  RG: {rg}\n"
                f"{domain_comment}\n"
                f"\n"
                f"sys\n"
                f"service-v\n"
                f"\n"
                f"{hosts_str}\n"
                f"{filters_str}\n"
                f"\n"
                f"{fg_binds_str}\n"
                f"\n"
                f"q\n"
                f"q\n"
                f"save\n"
                f"Y"
                f"{pcrf_block}"
            )

        # LOGIKA 2: PRODUCT REVAMP (VERSIONING CUTOVER)
        elif req_type == "Revamp":
            return (
                f"// HUAWEI SERVICE-V MML SCRIPT - PRODUCT REVAMP (VERSIONING CUTOVER)\n"
                f"// Target APN : {apn}\n"
                f"// App Target : {app}  |  RG: {rg}  |  SID: {sid}\n"
                f"{domain_comment}\n"
                f"\n"
                f"sys\n"
                f"service-v\n"
                f"\n"
                f"// 1. New Version Rule Definition (v2)\n"
                f"rule r_{app}_v2_{rg}_{sid}"
                f" filter-group fg_gaspol_{app}"
                f" service-category-group catg_{rg}_{sid}"
                f" priority 27000\n"
                f"\n"
                f"// 2. Cutover Rule Binding in User Profile\n"
                f"user-profile crbn_{apn}_sy\n"
                f"rule-binding r_{app}_v2_{rg}_{sid} priority 27000\n"
                f"undo rule-binding r_{app}_v1_{rg}_{sid}\n"
                f"q\n"
                f"\n"
                f"// 3. Retain the old rule (v1) for rollback; cleanup requires separate verification.\n"
                f"\n"
                f"q\n"
                f"q\n"
                f"save\n"
                f"Y"
                f"{pcrf_block}"
            )

        # LOGIKA 3: NEW PRODUCT (FULL PROVISIONING)
        else:
            return (
                f"// HUAWEI SERVICE-V MML SCRIPT - NEW PRODUCT PROVISIONING\n"
                f"// Target APN : {apn}  |  Category: {app_cat}\n"
                f"// App Target : {app}  |  RG: {rg}  |  SID: {sid}  |  Capping: {capping}\n"
                f"{domain_comment}\n"
                f"\n"
                f"sys\n"
                f"service-v\n"
                f"\n"
                f"{hosts_str}\n"
                f"{filters_str}\n"
                f"\n"
                f"{fg_binds_str}\n"
                f"\n"
                f"cbb-id cbbid_on_{rg} charge-method online rg {rg} metering volume\n"
                f"cbb-id cbbid_off_{rg}_{sid} charge-method offline rg {rg} sid {sid} metering volume\n"
                f"charge-property cp_{rg}_{sid}"
                f" up-initial offline cbbid_off_{rg}_{sid} online cbbid_on_{rg}"
                f" down-initial offline cbbid_off_{rg}_{sid} online cbbid_on_{rg}\n"
                f"category-group catg_{rg}_{sid} charge-property cp_{rg}_{sid}\n"
                f"\n"
                f"rule r_{app}_{rg}_{sid}"
                f" filter-group fg_gaspol_{app}"
                f" service-category-group catg_{rg}_{sid}"
                f" priority 27000\n"
                f"\n"
                f"user-profile crbn_{apn}_sy\n"
                f"rule-binding r_{app}_{rg}_{sid} priority 27000\n"
                f"rule-binding rule_def_dns_q1 priority 41\n"
                f"free-service online disable\n"
                f"ddos-check enable\n"
                f"quota-application-action buffer\n"
                f"ctx-start-requested-rating catg_{rg}_{sid}"
                f"{he_block}\n"
                f"q\n"
                f"refre\n"
                f"q\n"
                f"q\n"
                f"save\n"
                f"Y"
                f"{pcrf_block}"
            )

    def generate_rollback(self, payload: Dict[str, Any]) -> str:
        payload = ProvisioningPayload.model_validate(payload).to_dict()
        req_type = str(payload.get("product_type", "New Product")).strip()
        apn = _sanitize_identifier(payload.get("apn_name", "internet_im3"), "internet_im3")
        app = _sanitize_identifier(payload.get("app_name", "app"), "app")
        rg = _sanitize_rg_sid(payload.get("rg_val", "11010"), "11010")
        sid = _sanitize_rg_sid(payload.get("sid_val", "11001000"), "11001000")

        if req_type == "Reguler Update":
            return (
                f"// ROLLBACK DRAFT - DELTA PATCH ROLLBACK\n"
                f"// Target APN : {apn}  |  App: {app}\n"
                f"// BLOCKED: an actual pre-change snapshot is required.\n"
                f"// Deleting the entire filter-group can remove pre-existing traffic matches.\n"
                f"// No executable rollback is emitted for a delta patch without that snapshot.\n"
            )

        elif req_type == "Revamp":
            return (
                f"// ROLLBACK DRAFT - REVAMP ROLLBACK (REVERT TO V1)\n"
                f"// Target APN : {apn}  |  App: {app}  |  RG: {rg}  |  SID: {sid}\n"
                f"\n"
                f"sys\n"
                f"service-v\n"
                f"\n"
                f"user-profile crbn_{apn}_sy\n"
                f"rule-binding r_{app}_v1_{rg}_{sid} priority 27000\n"
                f"undo rule-binding r_{app}_v2_{rg}_{sid}\n"
                f"q\n"
                f"\n"
                f"undo rule r_{app}_v2_{rg}_{sid}\n"
                f"\n"
                f"q\n"
                f"q\n"
                f"save\n"
                f"Y"
            )

        else:
            return (
                f"// ROLLBACK DRAFT - NEW PRODUCT FULL ROLLBACK\n"
                f"// Target APN : {apn}  |  App: {app}  |  RG: {rg}  |  SID: {sid}\n"
                f"\n"
                f"sys\n"
                f"service-v\n"
                f"\n"
                f"user-profile crbn_{apn}_sy\n"
                f"undo rule-binding r_{app}_{rg}_{sid}\n"
                f"q\n"
                f"\n"
                f"undo rule r_{app}_{rg}_{sid}\n"
                f"undo category-group catg_{rg}_{sid}\n"
                f"undo charge-property cp_{rg}_{sid}\n"
                f"undo cbb-id cbbid_off_{rg}_{sid}\n"
                f"undo cbb-id cbbid_on_{rg}\n"
                f"undo filter-group fg_gaspol_{app}\n"
                f"\n"
                f"q\n"
                f"q\n"
                f"save\n"
                f"Y"
            )


# Instansiasi default singleton
_huawei_engine = HuaweiServiceVEngine()

def generate_huawei_mml_script(payload: dict) -> str:
    """Wrapper fungsi publik untuk generasi script MML Huawei."""
    return _huawei_engine.generate_provisioning(payload)

def generate_rollback_script(payload: dict) -> str:
    """Wrapper fungsi publik untuk generasi script Rollback Huawei."""
    return _huawei_engine.generate_rollback(payload)
