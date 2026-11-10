import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from cryptography.fernet import Fernet
from pydantic import ValidationError

from core.engines.huawei_service_v import generate_huawei_mml_script, generate_rollback_script
from core.models.payload import ProvisioningPayload
from core.parsers.ciq_parser import get_sample_ciq_csv, map_ciq_dataframe, process_ciq_batch
from core.services import audit_service as audit
from core.services.risk_service import assess_change, export_feature_jsonl
from core.transports.crypto import decrypt_password, encrypt_password
from core.transports.ssh_gateway import _drain_channel_buffer, execute_script


PAYLOAD = {"apn_name": "internet_im3", "app_name": "TikTok", "rg_val": "11010",
           "sid_val": "11001000", "app_domain": "*.tiktok.com"}


class ValidationTests(unittest.TestCase):
    def test_engine_rejects_unsafe_inputs(self):
        for change in (
            {"rg_val": "invalid"}, {"sid_val": "4294967296"}, {"rg_val": "１２３"},
            {"app_name": "x\nsave"}, {"app_domain": "*.example.com;save"},
            {"app_domain": "example.com/path"}, {"app_domain": "*.com"},
            {"app_domain": "999.999.999.999"}, {"app_domain": "*.10.1.1.1"},
            {"product_type": "Typo"}, {"header_enrichment": "Yes", "he_key": "x\nsave", "he_cipher": "AES"},
            {"app_domain": ""},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                generate_huawei_mml_script({**PAYLOAD, **change})

    def test_domain_and_excel_id_normalization(self):
        payload = ProvisioningPayload(**{**PAYLOAD, "rg_val": 11010.0, "app_domain": "https://API.TIKTOK.COM/, api.tiktok.com"})
        self.assertEqual(payload.rg_val, "11010")
        self.assertEqual(payload.app_domain, "api.tiktok.com")

    def test_missing_required_columns_and_cells_reject_batch(self):
        df = pd.read_csv(io.StringIO(get_sample_ciq_csv()), dtype=str)
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            process_ciq_batch(df.drop(columns=["rg_val"]))
        df.loc[0, "rg_val"] = ""
        with self.assertRaisesRegex(ValueError, "row 2.*rg_val"):
            process_ciq_batch(df)

    def test_sample_csv_preserves_both_domains(self):
        df = pd.read_csv(io.StringIO(get_sample_ciq_csv()))
        self.assertIsInstance(df.index, pd.RangeIndex)
        result = process_ciq_batch(df)
        self.assertEqual(result[0]["app_name"], "tiktok")
        self.assertIn("*.v2.tiktokcdn.com", result[0]["mml_script"])

    def test_ambiguous_alias_and_fuzzy_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, "Multiple columns"):
            map_ciq_dataframe(pd.DataFrame(columns=["apn", "apn_name"]))
        mapped, _ = map_ciq_dataframe(pd.DataFrame(columns=["unapproved_apn_name_extra"]))
        self.assertNotIn("apn_name", mapped.columns)

    def test_duplicate_target_rules_rejected(self):
        df = pd.read_csv(io.StringIO(get_sample_ciq_csv()), dtype=str)
        with self.assertRaisesRegex(ValueError, "Duplicate target rule"):
            process_ciq_batch(pd.concat([df.iloc[[0]], df.iloc[[0]]], ignore_index=True))

    def test_conflicting_shared_application_domains_rejected(self):
        df = pd.read_csv(io.StringIO(get_sample_ciq_csv()), dtype=str).iloc[[0]].copy()
        conflicting = df.copy()
        conflicting["sid_val"] = "11001001"
        conflicting["app_domain"] = "*.example.com"
        with self.assertRaisesRegex(ValueError, "Conflicting domains"):
            process_ciq_batch(pd.concat([df, conflicting], ignore_index=True))

    def test_revamp_preserves_prior_rule_and_delta_does_not_delete_group(self):
        revamp = generate_huawei_mml_script({**PAYLOAD, "product_type": "Revamp"})
        self.assertNotIn("undo rule r_tiktok_v1_", revamp)
        rollback = generate_rollback_script({**PAYLOAD, "product_type": "Reguler Update"})
        self.assertNotIn("undo filter-group", rollback)
        self.assertIn("BLOCKED", rollback)


class AuditReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "audit.json"
        self.patcher = patch.object(audit, "HISTORY_FILE", str(self.path))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.directory.cleanup()

    def test_fresh_history_has_no_fake_events_or_deadlock(self):
        self.assertEqual(audit.load_history(), [])
        self.assertFalse(self.path.exists())

    def test_concurrent_append_preserves_all_events(self):
        def append(index):
            audit.append_history(audit.build_audit_log("GENERATE MML", "apn", str(index), {}))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(append, range(32)))
        history = audit.load_history()
        self.assertEqual(len(history), 32)
        self.assertEqual(len({entry["Event ID"] for entry in history}), 32)

    def test_atomic_failure_preserves_original(self):
        audit.save_history([{"Status": "ORIGINAL"}])
        before = self.path.read_bytes()
        with patch.object(audit.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                audit.append_history({"Status": "NEW"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(Path(self.directory.name).glob("*.tmp")), [])

    def test_corruption_is_visible_and_original_is_preserved(self):
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid audit history"):
            audit.load_history()
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")

    def test_history_not_trimmed_and_nested_secrets_removed(self):
        audit.save_history([{"Payload": {"safe": 1, "nested": {"password": "secret", "api_key": "secret"}}}] * 201)
        history = audit.load_history()
        self.assertEqual(len(history), 201)
        self.assertEqual(history[0]["Payload"], {"safe": 1, "nested": {}})


class ExecutionReliabilityTests(unittest.TestCase):
    def setUp(self):
        key = Fernet.generate_key().decode()
        password = Fernet(key.encode()).encrypt(b"test-password").decode()
        self.environment = patch.dict(os.environ, {
            "RELPOOL_ENABLE_LIVE": "true", "GGSN_TESTBED_HOST": "testbed.example.invalid",
            "GGSN_TESTBED_USER": "test-user", "GGSN_TESTBED_PASS": password, "SECRET_KEY": key,
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_simulation_never_connects_and_does_not_claim_validation(self):
        with patch("core.transports.ssh_gateway.paramiko.SSHClient") as factory:
            result = execute_script(["sys"])
        factory.assert_not_called()
        self.assertEqual(result.status, "SIMULATED")
        self.assertEqual(result.commands_sent, 0)
        self.assertIn("not validated", result.logs[-1])

    def test_connection_failure_is_not_success(self):
        with patch("core.transports.ssh_gateway.paramiko.SSHClient") as factory:
            factory.return_value.connect.side_effect = OSError("test-password")
            result = execute_script(["sys"], is_live=True)
        self.assertEqual(result.status, "FAILED")
        self.assertNotIn("test-password", str(result.logs))
        factory.return_value.close.assert_called_once()

    def test_device_error_stops_before_next_command(self):
        with patch("core.transports.ssh_gateway.paramiko.SSHClient") as factory, patch(
            "core.transports.ssh_gateway._drain_channel_buffer",
            side_effect=["<testbed>", "Error: unrecognized command\n[testbed]"],
        ):
            result = execute_script(["invalid", "save", "Y"], is_live=True)
        self.assertEqual(result.status, "PARTIAL_FAILED")
        self.assertEqual(result.commands_sent, 1)
        self.assertEqual(factory.return_value.invoke_shell.return_value.sendall.call_count, 1)
        factory.return_value.load_system_host_keys.assert_called_once()
        self.assertEqual(type(factory.return_value.set_missing_host_key_policy.call_args.args[0]).__name__, "RejectPolicy")

    def test_timeout_after_send_is_unknown_and_stops(self):
        with patch("core.transports.ssh_gateway.paramiko.SSHClient") as factory, patch(
            "core.transports.ssh_gateway._drain_channel_buffer", side_effect=["<testbed>", TimeoutError()]
        ):
            result = execute_script(["sys", "save"], is_live=True)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.commands_sent, 1)
        self.assertEqual(factory.return_value.invoke_shell.return_value.sendall.call_count, 1)

    def test_all_prompts_still_require_post_change_verification(self):
        with patch("core.transports.ssh_gateway.paramiko.SSHClient"), patch(
            "core.transports.ssh_gateway._drain_channel_buffer", side_effect=["<testbed>", "[testbed]"]
        ):
            result = execute_script(["sys"], is_live=True)
        self.assertEqual(result.status, "SENT_UNVERIFIED")
        self.assertEqual(result.commands_acknowledged, 1)

    def test_empty_or_multiline_commands_rejected_before_connection(self):
        for commands in ([], ["sys\nsave"], [""]):
            with patch("core.transports.ssh_gateway.paramiko.SSHClient") as factory:
                result = execute_script(commands, is_live=True)
            self.assertEqual(result.status, "FAILED")
            factory.assert_not_called()

    def test_missing_live_opt_in_rejects_connection(self):
        with patch.dict(os.environ, {"RELPOOL_ENABLE_LIVE": "false"}), patch("core.transports.ssh_gateway.paramiko.SSHClient") as factory:
            result = execute_script(["sys"], is_live=True)
        self.assertEqual(result.status, "FAILED")
        factory.assert_not_called()

    def test_prompt_reader_accumulates_chunks_and_rejects_silence(self):
        shell = MagicMock()
        shell.recv_ready.return_value = True
        shell.recv.side_effect = [b"command output\n", b"[testbed]\n"]
        self.assertEqual(_drain_channel_buffer(shell, timeout=1), "command output\n[testbed]")
        with self.assertRaises(TimeoutError):
            _drain_channel_buffer(shell, timeout=0)

    def test_log_redacts_enrichment_key(self):
        result = execute_script(["header-enrichment key SECRET-VALUE cipher AES256"])
        self.assertNotIn("SECRET-VALUE", str(result.logs))

    def test_crypto_rejects_missing_key_and_wrong_decryption_key(self):
        with patch.dict(os.environ, {"SECRET_KEY": ""}):
            with self.assertRaises(ValueError):
                encrypt_password("password")
        token = encrypt_password("password")
        with patch.dict(os.environ, {"SECRET_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(ValueError):
                decrypt_password(token)


class RiskDatasetTests(unittest.TestCase):
    def test_legacy_invalid_metadata_is_skipped(self):
        self.assertEqual(export_feature_jsonl([{"Metadata": None}, {"Metadata": {"assessment": None}}]), "")

    def test_unimplemented_policy_is_explained_and_blocks_live(self):
        payload = {**PAYLOAD, "speed_limit": "Throttle 128kbps"}
        assessment = assess_change(payload, generate_huawei_mml_script(payload))
        self.assertTrue(assessment["live_blockers"])
        self.assertTrue(any("comments" in reason for reason in assessment["reasons"]))

    def test_export_uses_allowlist_and_never_converts_status_to_risk_label(self):
        script = generate_huawei_mml_script(PAYLOAD)
        assessment = assess_change(PAYLOAD, script)
        assessment["features"]["injected_password"] = "DO-NOT-EXPORT"
        entry = audit.build_audit_log("TESTBED_PUSH", "internal_apn", "app", {"he_key": "DO-NOT-EXPORT"},
                                     status="SUCCESS", metadata={"assessment": assessment, "execution_mode": "simulation"})
        text = export_feature_jsonl([entry, {"Payload": PAYLOAD, "Status": "SUCCESS"}])
        lines = text.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertNotIn("DO-NOT-EXPORT", text)
        self.assertNotIn("internal_apn", text)
        row = json.loads(lines[0])
        self.assertIsNone(row["observation"]["risk_label"])
        self.assertEqual(row["observation"]["execution_mode"], "simulation")
        self.assertNotIn("status", row["features"])


if __name__ == "__main__":
    unittest.main()
