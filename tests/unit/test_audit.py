import unittest
from core.services.audit_service import build_audit_log, load_history, save_history


class TestAuditService(unittest.TestCase):
    def test_build_audit_log_format_and_security(self):
        payload = {
            "apn_name": "test_apn",
            "app_name": "test_app",
            "he_key": "PRIVATE_SECRET_KEY",
            "he_cipher": "AES256",
            "rg_val": "11010"
        }
        log = build_audit_log(
            action="GENERATE MML",
            apn="test_apn",
            app="test_app",
            payload=payload,
            history_count=9
        )
        self.assertIn("WO-RELPOOL", log["WO ID"])
        self.assertIn("Event ID", log)
        self.assertNotEqual(log["WO ID"], build_audit_log("GENERATE MML", "test_apn", "test_app", payload)["WO ID"])
        # Security: private keys must be purged from audit payload
        self.assertNotIn("he_key", log["Payload"])
        self.assertNotIn("he_cipher", log["Payload"])
        self.assertEqual(log["Payload"]["rg_val"], "11010")

    def test_load_history_returns_list(self):
        hist = load_history()
        self.assertIsInstance(hist, list)


if __name__ == "__main__":
    unittest.main()
