import os
from typing import List


def parse_mml_script_commands(script_content: str) -> List[str]:
    """
    Membersihkan isi string script MML menjadi baris perintah CLI bersih
    (tanpa komentar // dan tanpa baris kosong).
    """
    clean_commands: List[str] = []
    for line in script_content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("//"):
            clean_commands.append(stripped)
    return clean_commands


def read_mml_file(filepath: str) -> List[str]:
    """
    Membaca file skrip MML eksternal dan mengembalikan baris perintah aktif.
    """
    if not os.path.exists(filepath):
        return []

    clean_commands: List[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("//"):
                clean_commands.append(stripped)
    return clean_commands
