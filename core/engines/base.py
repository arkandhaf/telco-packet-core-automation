from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseRuleEngine(ABC):
    """
    Abstract interface untuk generator rule provisioning dan rollback.
    Memungkinkan RELPOOL mendukung arsitektur multi-vendor (Huawei, Cisco, Ericsson).
    """

    @abstractmethod
    def generate_provisioning(self, payload: Dict[str, Any]) -> str:
        """Hasilkan command script provisioning konfigurasi node."""
        pass

    @abstractmethod
    def generate_rollback(self, payload: Dict[str, Any]) -> str:
        """Hasilkan command script safe rollback inverse."""
        pass
