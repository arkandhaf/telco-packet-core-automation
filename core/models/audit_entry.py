from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditLogEntry(BaseModel):
    """
    Schema resmi untuk catatan transaksi Work Order audit trail.
    """
    Timestamp: str = Field(description="Waktu pembuatan entri YYYY-MM-DD HH:MM")
    WO_ID: str = Field(alias="WO ID", description="Nomor Work Order terstandardisasi")
    Action: str = Field(description="Aksi yang dilakukan: GENERATE MML, TESTBED_PUSH, BATCH_MML_GEN")
    Target_Node: str = Field(alias="Target Node", default="LOCAL_ENGINE", description="Node tujuan eksekusi")
    APN: str = Field(description="APN target")
    App_Target: str = Field(alias="App Target", description="Nama aplikasi target")
    Status: str = Field(description="Status akhir: SUCCESS, SCRIPT_GENERATED, SIMULATED, dll")
    Payload: Dict[str, Any] = Field(default_factory=dict, description="Metadata payload CIQ lengkap tersanitasi")
    Event_ID: Optional[str] = Field(alias="Event ID", default=None)
    Schema_Version: int = Field(alias="Schema Version", default=1)
    Engine_Version: Optional[str] = Field(alias="Engine Version", default=None)
    Metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
