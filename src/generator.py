"""
Backward compatibility bridge for src.generator.
Canonical implementation now lives in core.engines.huawei_service_v.
"""
from core.engines.huawei_service_v import (
    HuaweiServiceVEngine,
    generate_huawei_mml_script,
    generate_rollback_script,
    _sanitize_identifier,
    _sanitize_domain,
    _parse_domains,
    _sanitize_rg_sid
)

__all__ = [
    "HuaweiServiceVEngine",
    "generate_huawei_mml_script",
    "generate_rollback_script",
    "_sanitize_identifier",
    "_sanitize_domain",
    "_parse_domains",
    "_sanitize_rg_sid"
]
