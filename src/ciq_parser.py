"""
Backward compatibility bridge for src.ciq_parser.
Canonical implementation now lives in core.parsers.ciq_parser.
"""
from core.parsers.ciq_parser import (
    COLUMN_ALIASES,
    DEFAULT_PAYLOAD_VALUES,
    clean_header_name,
    map_ciq_dataframe,
    sanitize_value,
    build_row_payload,
    process_ciq_batch,
    generate_combined_script_txt,
    generate_batch_zip,
    get_sample_ciq_csv
)

__all__ = [
    "COLUMN_ALIASES",
    "DEFAULT_PAYLOAD_VALUES",
    "clean_header_name",
    "map_ciq_dataframe",
    "sanitize_value",
    "build_row_payload",
    "process_ciq_batch",
    "generate_combined_script_txt",
    "generate_batch_zip",
    "get_sample_ciq_csv"
]
