import io
import os
import zipfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import pandas as pd

from src.generator import (
    generate_huawei_mml_script,
    generate_rollback_script,
    _sanitize_identifier,
    _sanitize_domain,
    _parse_domains,
    _sanitize_rg_sid
)
from src.ciq_parser import (
    map_ciq_dataframe,
    process_ciq_batch,
    generate_combined_script_txt,
    generate_batch_zip,
    get_sample_ciq_csv,
    build_row_payload
)
from src.audit import build_audit_log, save_history, load_history
from src.encrypt_tool import encrypt_password, decrypt_password


class TestGeneratorSanitization(unittest.TestCase):
    def test_sanitize_identifier(self):
        self.assertEqual(_sanitize_identifier("Indosat IM3 Internet"), "indosat_im3_internet")
        self.assertEqual(_sanitize_identifier("Gojek-Driver (B2B)"), "gojek_driver_b2b")
        self.assertEqual(_sanitize_identifier("   "), "unknown")

    def test_sanitize_domain(self):
        self.assertEqual(_sanitize_domain("https://api.tiktok.com/"), "api.tiktok.com")
        self.assertEqual(_sanitize_domain("HTTP://V2.TIKTOKCDN.COM/ "), "v2.tiktokcdn.com")

    def test_parse_multi_domains(self):
        raw = "https://api.tiktok.com/,\n*.tiktokcdn.com,  v2.tiktok.com/"
        domains = _parse_domains(raw, app_fallback="tiktok")
        self.assertEqual(len(domains), 3)
        self.assertIn("api.tiktok.com", domains)
        self.assertIn("*.tiktokcdn.com", domains)
        self.assertIn("v2.tiktok.com", domains)

    def test_sanitize_rg_sid_excel_float(self):
        self.assertEqual(_sanitize_rg_sid("11010.0", default="11010"), "11010")
        self.assertEqual(_sanitize_rg_sid("20000", default="10000"), "20000")
        self.assertEqual(_sanitize_rg_sid("abc", default="10000"), "10000")


class TestMMLScriptGeneration(unittest.TestCase):
    def test_generate_new_product(self):
        payload = {
            "product_type": "New Product",
            "apn_name": "internet_im3",
            "app_name": "tiktok",
            "rg_val": "11010",
            "sid_val": "11001000",
            "app_domain": "*.tiktok.com, *.v2.tiktokcdn.com"
        }
        script = generate_huawei_mml_script(payload)
        self.assertIn("HUAWEI SERVICE-V MML SCRIPT - NEW PRODUCT PROVISIONING", script)
        self.assertIn("host h_tiktok_1 domain *.tiktok.com", script)
        self.assertIn("host h_tiktok_2 domain *.v2.tiktokcdn.com", script)
        self.assertIn("user-profile crbn_internet_im3_sy", script)
        self.assertIn("cbb-id cbbid_on_11010", script)

    def test_generate_rollback_script(self):
        payload = {
            "product_type": "New Product",
            "apn_name": "internet_im3",
            "app_name": "tiktok",
            "rg_val": "11010",
            "sid_val": "11001000"
        }
        rollback = generate_rollback_script(payload)
        self.assertIn("ROLLBACK DRAFT - NEW PRODUCT FULL ROLLBACK", rollback)
        self.assertIn("undo rule r_tiktok_11010_11001000", rollback)
        self.assertIn("undo filter-group fg_gaspol_tiktok", rollback)


class TestCIQParserAndBatch(unittest.TestCase):
    def test_sample_csv_and_mapping(self):
        csv_text = get_sample_ciq_csv()
        df = pd.read_csv(io.StringIO(csv_text))
        self.assertGreaterEqual(len(df), 3)

        mapped_df, report = map_ciq_dataframe(df)
        self.assertIn("product_type", mapped_df.columns)
        self.assertIn("apn_name", mapped_df.columns)
        self.assertIn("app_name", mapped_df.columns)

    def test_process_batch_and_zip(self):
        csv_text = get_sample_ciq_csv()
        df = pd.read_csv(io.StringIO(csv_text))
        results = process_ciq_batch(df)

        self.assertEqual(len(results), len(df))
        self.assertTrue(all("mml_script" in r for r in results))
        self.assertTrue(all("rollback_script" in r for r in results))

        # Test combined TXT
        combined_txt = generate_combined_script_txt(results)
        self.assertIn("COMBINED BATCH MML PROVISIONING SCRIPT", combined_txt)
        self.assertIn("ITEM #1", combined_txt)

        # Test ZIP generation
        zip_bytes = generate_batch_zip(results)
        self.assertIsInstance(zip_bytes, bytes)
        self.assertGreater(len(zip_bytes), 100)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            namelist = zf.namelist()
            self.assertIn("ALL_MML_SCRIPTS.txt", namelist)
            self.assertIn("BATCH_MANIFEST.csv", namelist)
            self.assertTrue(any(f.startswith("scripts/") for f in namelist))
            self.assertTrue(any(f.startswith("rollbacks/") for f in namelist))


class TestAuditAndSecurity(unittest.TestCase):
    def test_build_audit_log_sanitizes_he_keys(self):
        payload = {
            "apn_name": "test_apn",
            "he_key": "SECRET_KEY_123",
            "he_cipher": "AES256",
            "app_name": "secret_app"
        }
        log = build_audit_log(
            action="GENERATE MML",
            apn="test_apn",
            app="secret_app",
            payload=payload,
            history_count=5
        )
        self.assertTrue(log["WO ID"].startswith("WO-RELPOOL-"))
        self.assertIn("Event ID", log)
        self.assertNotIn("he_key", log["Payload"])
        self.assertNotIn("he_cipher", log["Payload"])
        self.assertEqual(log["Payload"]["app_name"], "secret_app")

    @patch.dict(os.environ, {"SECRET_KEY": Fernet.generate_key().decode("ascii")})
    def test_encrypt_decrypt_password(self):
        raw = "RelpoolSuperPass2026!"
        encrypted = encrypt_password(raw)
        decrypted = decrypt_password(encrypted)
        self.assertEqual(decrypted, raw)


if __name__ == "__main__":
    unittest.main()
