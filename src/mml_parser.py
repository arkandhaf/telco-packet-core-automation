"""
Backward compatibility bridge for src.mml_parser.
Canonical implementation now lives in core.parsers.mml_parser.
"""
from core.parsers.mml_parser import parse_mml_script_commands, read_mml_file

__all__ = ["parse_mml_script_commands", "read_mml_file"]