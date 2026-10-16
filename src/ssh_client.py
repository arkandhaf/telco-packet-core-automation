"""
Backward compatibility bridge for src.ssh_client.
Canonical implementation now lives in core.transports.ssh_gateway.
"""
from core.transports.ssh_gateway import execute_to_testbed

__all__ = ["execute_to_testbed"]