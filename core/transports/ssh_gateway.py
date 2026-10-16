"""Bounded SSH execution with explicit, unverified outcomes."""
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

import paramiko
from dotenv import load_dotenv

from .crypto import decrypt_password

load_dotenv()
PROMPT_PATTERN = r"(?m)^\s*(?:<[^<>\r\n]+>|\[[^\[\]\r\n]+\])\s*$"
ERROR_PATTERN = re.compile(r"(?im)^\s*(?:error\s*:|failure\s*:|failed\b|%\s*(?:error|unrecognized|invalid|incomplete|ambiguous))")
MAX_RESPONSE_BYTES = 1024 * 1024


@dataclass
class ExecutionResult:
    status: str
    logs: List[str] = field(default_factory=list)
    commands_sent: int = 0
    commands_acknowledged: int = 0
    duration_ms: int = 0
    error_type: Optional[str] = None
    is_live: bool = False
    target_host: Optional[str] = None

    @property
    def failed(self) -> bool:
        return self.status in {"FAILED", "PARTIAL_FAILED", "UNKNOWN"}


def _safe_log(text: str) -> str:
    return re.sub(r"(header-enrichment\s+key\s+)\S+", r"\1[REDACTED]", text, flags=re.IGNORECASE)


def _drain_channel_buffer(shell, timeout: float = 3.0) -> str:
    """Wait for a terminal prompt. Silence is never treated as acknowledgement."""
    output = bytearray()
    deadline = time.monotonic() + timeout
    prompt = re.compile(os.getenv("GGSN_PROMPT_REGEX", PROMPT_PATTERN))
    while time.monotonic() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(4096)
            if not chunk:
                raise ConnectionError("SSH channel closed")
            output.extend(chunk)
            if len(output) > MAX_RESPONSE_BYTES:
                raise ValueError("SSH response exceeded size limit")
            decoded = output.decode("utf-8", errors="replace")
            last_line = decoded.rstrip().split("\n")[-1]
            if prompt.fullmatch(last_line):
                return decoded.strip()
        elif getattr(shell, "closed", False):
            raise ConnectionError("SSH channel closed")
        else:
            time.sleep(0.05)
    raise TimeoutError("No terminal prompt received before deadline")


def execute_script(commands: List[str], is_live: bool = False, host: Optional[str] = None) -> ExecutionResult:
    start = time.monotonic()
    result = ExecutionResult(status="FAILED", is_live=is_live, target_host=host or os.getenv("GGSN_TESTBED_HOST"))
    client = None
    try:
        if not commands or len(commands) > 10000 or any(
            not isinstance(command, str) or not command.strip() or re.search(r"[\x00-\x1f\x7f]", command)
            for command in commands
        ):
            raise ValueError("Provide 1–10000 nonempty, single-line commands")
        if not is_live:
            result.status = "SIMULATED"
            result.logs = [_safe_log(f"[SIMULATION #{i:02d}] Would send: {command}") for i, command in enumerate(commands, 1)]
            result.logs.append(f"[SIMULATION COMPLETED] {len(commands)} commands listed; device syntax and impact are not validated.")
            return result
        if os.getenv("RELPOOL_ENABLE_LIVE", "").lower() != "true":
            raise PermissionError("Live execution is disabled")
        if not result.target_host:
            raise ValueError("GGSN_TESTBED_HOST must be explicitly configured")
        port = int(os.getenv("GGSN_TESTBED_PORT", "22"))
        user = os.getenv("GGSN_TESTBED_USER")
        password = decrypt_password(os.getenv("GGSN_TESTBED_PASS", ""))
        if not user or not password:
            raise ValueError("Explicit SSH credentials are required")
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        known_hosts = os.getenv("GGSN_KNOWN_HOSTS")
        if known_hosts:
            client.load_host_keys(known_hosts)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(result.target_host, port=port, username=user, password=password,
                       timeout=10, banner_timeout=10, auth_timeout=10,
                       allow_agent=False, look_for_keys=False)
        shell = client.invoke_shell()
        shell.settimeout(10)
        _drain_channel_buffer(shell, timeout=10)
        for index, command in enumerate(commands, 1):
            # A failed send may still have partially reached the device.
            result.commands_sent += 1
            shell.sendall(command + "\n")
            response = _drain_channel_buffer(shell, timeout=10)
            result.logs.append(_safe_log(f"[{index:02d}] {command} -> {response}"))
            if ERROR_PATTERN.search(response):
                result.status = "PARTIAL_FAILED"
                result.error_type = "DeviceCommandError"
                result.logs.append("[STOPPED] Device reported a command error; verify device state before retrying.")
                return result
            result.commands_acknowledged += 1
        result.status = "SENT_UNVERIFIED"
        result.logs.append("[SENT_UNVERIFIED] Prompts received; post-change configuration and service health still need verification.")
    except Exception as exc:
        result.error_type = type(exc).__name__
        result.status = "UNKNOWN" if result.commands_sent else "FAILED"
        result.logs.append(f"[{result.status}] {result.error_type}; execution stopped. Check configuration, host trust and device state before retrying.")
    finally:
        if client:
            try:
                client.close()
            except Exception:
                result.logs.append("[WARNING] SSH cleanup failed; verify the session has closed.")
        result.duration_ms = round((time.monotonic() - start) * 1000)
    return result


def execute_to_testbed(commands: List[str], is_live: bool = False, host: Optional[str] = None) -> List[str]:
    """Compatibility wrapper. New callers should inspect execute_script().status."""
    return execute_script(commands, is_live=is_live, host=host).logs
