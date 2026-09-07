"""Validated inputs shared by manual entry, batch ingestion and rule engines."""
import re
from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProvisioningPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    product_type: Literal["New Product", "Revamp", "Reguler Update"] = "New Product"
    user_profile: Literal["New", "Existing"] = "New"
    apn_name: str = "internet_im3"
    charging_type: Literal["Zero Rating", "Special Rate (differentiate RG)"] = "Zero Rating"
    rg_val: str = "11010"
    sid_val: str = "11001000"
    capping_option: str = "No Capping"
    header_enrichment: Literal["Yes", "No"] = "No"
    he_key: str = Field(default="", repr=False)
    he_cipher: str = ""
    speed_limit: Literal["Full Speed", "Throttle 256kbps", "Throttle 128kbps", "Throttle 64kbps"] = "Full Speed"
    qci_val: Literal["9 (Default Internet)", "4 (Dedicated)", "1 (Voice/Low Latency)"] = "9 (Default Internet)"
    app_category: str = "Well Known Apps"
    app_name: str = "app"
    app_domain: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def reject_control_characters(cls, value, info):
        if isinstance(value, str):
            # Domain lists alone may span multiple lines.
            pattern = r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]" if info.field_name == "app_domain" else r"[\x00-\x1f\x7f]"
            if re.search(pattern, value):
                raise ValueError("Control characters are not allowed")
        return value

    @field_validator("apn_name", "app_name")
    @classmethod
    def sanitize_identifier(cls, value: str) -> str:
        value = re.sub(r"[\s\-.]+", "_", value.lower())
        value = re.sub(r"[^a-z0-9_]", "", value)
        value = re.sub(r"_+", "_", value).strip("_")
        if not value or len(value) > 64:
            raise ValueError("Identifier must normalize to 1–64 ASCII characters")
        return value

    @field_validator("rg_val", "sid_val", mode="before")
    @classmethod
    def sanitize_numeric(cls, value) -> str:
        value = str(value).strip()
        if re.fullmatch(r"[0-9]+\.0", value):
            value = value[:-2]
        if not re.fullmatch(r"[0-9]{1,10}", value) or int(value) > 4294967295:
            raise ValueError("ID must be an unsigned 32-bit integer; invalid IDs are never defaulted")
        return str(int(value))

    @field_validator("app_domain")
    @classmethod
    def validate_domains(cls, value: str) -> str:
        domains = []
        for part in re.split(r"[,\r\n\t]+", value):
            domain = re.sub(r"^https?://", "", part.strip().lower()).rstrip("/")
            if not domain:
                continue
            hostname = domain[2:] if domain.startswith("*.") else domain
            if re.fullmatch(r"[0-9.]+", hostname):
                IPv4Address(hostname)
                if domain.startswith("*."):
                    raise ValueError("Wildcard IP literals are not supported")
            labels = hostname.split(".")
            if len(hostname) > 253 or len(labels) < 2 or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
            ):
                raise ValueError("Provide hostnames or IPv4 literals, without paths, ports or CLI syntax")
            if domain not in domains:
                domains.append(domain)
        if len(domains) > 100:
            raise ValueError("At most 100 domains are allowed per application")
        return ", ".join(domains)

    @field_validator("he_key", "he_cipher")
    @classmethod
    def validate_cli_token(cls, value: str) -> str:
        if value and not re.fullmatch(r"[a-zA-Z0-9_+/.=:-]{1,256}", value):
            raise ValueError("Header enrichment values must be single CLI tokens")
        return value

    @model_validator(mode="after")
    def validate_header_enrichment(self):
        if self.header_enrichment == "Yes" and (not self.he_key or not self.he_cipher):
            raise ValueError("Header enrichment requires a key and cipher")
        return self

    def to_dict(self) -> dict:
        return self.model_dump()
