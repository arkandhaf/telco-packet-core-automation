"""API contract and failure-path checks, isolated from the real audit store/SSH."""
import base64
import io
import gzip
import json
import csv
import tempfile
import unittest
import zipfile
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

import server
from core.services import audit_service


class CommandCenterAPITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.history_patch = patch.object(audit_service, "HISTORY_FILE", str(Path(self.directory.name) / "audit.json"))
        self.history_patch.start()
        self.client = TestClient(server.app)
        self.payload = {
            "product_type": "New Product", "user_profile": "New", "apn_name": "internet_im3",
            "charging_type": "Zero Rating", "rg_val": "11010", "sid_val": "11001000",
            "capping_option": "No Capping", "header_enrichment": "No", "he_key": "", "he_cipher": "",
            "speed_limit": "Full Speed", "qci_val": "9 (Default Internet)",
            "app_category": "Well Known Apps", "app_name": "TikTok", "app_domain": "*.tiktok.com, *.v2.tiktokcdn.com",
        }

    def tearDown(self):
        self.client.close()
        self.history_patch.stop()
        self.directory.cleanup()

    def test_generation_preview_statistics_and_audit(self):
        system = self.client.get("/api/system-info")
        self.assertEqual(system.status_code, 200)
        self.assertGreater(len(system.json()["nodes"]), 0)
        self.assertEqual(system.json()["statistics"]["total_wo"], 0)
        preview = self.client.post("/api/preview", json=self.payload)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(self.client.get("/api/audit").json(), [])
        response = self.client.post("/api/generate", json=self.payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("host h_tiktok_1 domain *.tiktok.com", data["mml_script"])
        self.assertIn("undo rule r_tiktok_11010_11001000", data["rollback_script"])
        self.assertEqual(data["hierarchy_preview"]["hosts"], ["h_tiktok_1", "h_tiktok_2"])
        self.assertEqual(data["hierarchy_preview"], preview.json()["hierarchy_preview"])
        history = self.client.get("/api/audit")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["Action"], "GENERATE MML")
        stats = self.client.get("/api/system-info").json()["statistics"]
        self.assertEqual(stats["generated_count"], 1)
        self.assertEqual(stats["wo_today"], 1)

    def test_real_simulation_ignores_comments_and_persists_truthful_status(self):
        script = self.client.post("/api/generate", json=self.payload).json()["mml_script"]
        response = self.client.post("/api/ssh/execute", json={
            "mml_script": script, "is_live": False, "apn_name": "internet_im3", "app_name": "TikTok",
            "payload": self.payload,
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        commands = [line.strip() for line in script.splitlines() if line.strip() and not line.strip().startswith("//")]
        self.assertEqual(result["command_count"], len(commands))
        self.assertEqual(result["status"], "SIMULATED")
        self.assertEqual(result["audit_entry"]["Status"], "SIMULATED")
        self.assertIn("[SIMULATION #01] Would send: sys", result["logs"])
        self.assertEqual(self.client.get("/api/system-info").json()["statistics"]["executed_count"], 0)

    def test_batch_csv_and_xlsx_archives_are_real(self):
        sample = self.client.get("/api/batch/sample")
        self.assertEqual(sample.status_code, 200)
        self.assertIn("TEMPLATE_CIQ_STANDARD.csv", sample.headers["content-disposition"])
        dataframe = pd.read_csv(io.StringIO(sample.text), keep_default_na=False)
        workbook = io.BytesIO()
        dataframe.to_excel(workbook, index=False)
        for filename, content in (("ciq.csv", sample.content), ("ciq.xlsx", workbook.getvalue())):
            with self.subTest(filename=filename):
                response = self.client.post("/api/batch/process", files={"file": (filename, content)})
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                self.assertEqual(len(data["batch_results"]), 4)
                self.assertEqual(len(data["raw_preview"]), 4)
                self.assertIn("app_domain", data["mapping_report"])
                with zipfile.ZipFile(io.BytesIO(base64.b64decode(data["zip_base64"]))) as archive:
                    self.assertEqual(archive.read("ALL_MML_SCRIPTS.txt").decode(), data["combined_txt"])
                    for row in data["batch_results"]:
                        self.assertEqual(archive.read("scripts/" + row["mml_filename"]).decode(), row["mml_script"])
                        self.assertIn("rollbacks/" + row["rollback_filename"], archive.namelist())
        self.assertEqual(len(self.client.get("/api/audit").json()), 2)

    def test_invalid_input_and_file_do_not_create_audit_events(self):
        response = self.client.post("/api/generate", json={**self.payload, "rg_val": "invalid"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/api/generate", json={**self.payload, "app_domain": ""}).status_code, 422)
        self.assertEqual(self.client.post("/api/batch/process", files={"file": ("bad.txt", b"bad")}).status_code, 415)
        self.assertEqual(self.client.post("/api/batch/process", files={"file": ("bad.xlsx", b"bad")}).status_code, 422)
        self.assertEqual(self.client.post("/api/batch/process", files={"file": ("bad.csv", b"wrong\nvalue")}).status_code, 422)
        self.assertEqual(self.client.get("/api/audit").json(), [])

    def test_secret_redaction_and_validation_do_not_echo_secrets(self):
        secret_payload = {**self.payload, "header_enrichment": "Yes", "he_key": "PRIVATEKEY", "he_cipher": "PRIVATECIPHER"}
        response = self.client.post("/api/generate", json=secret_payload)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("he_key", response.json()["payload"])
        self.assertNotIn("PRIVATEKEY", self.client.get("/api/audit").text)
        rejected = self.client.post("/api/generate", json={**secret_payload, "he_key": "PRIVATEKEY\nCLI"})
        self.assertEqual(rejected.status_code, 422)
        self.assertNotIn("PRIVATEKEY", rejected.text)
        frame = pd.DataFrame([secret_payload]).rename(columns={"he_key": "key_he", "he_cipher": "cipher_he"})
        result = self.client.post("/api/batch/process", files={"file": ("secrets.csv", frame.to_csv(index=False).encode())})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("key_he", result.json()["raw_preview"][0])
        self.assertNotIn("he_key", result.json()["batch_results"][0]["payload"])

    def test_audit_failure_prevents_ssh_and_script_release(self):
        with patch("server.save_history", side_effect=OSError("disk full")), patch("server.execute_to_testbed") as gateway:
            self.assertEqual(self.client.post("/api/generate", json=self.payload).status_code, 503)
            response = self.client.post("/api/ssh/execute", json={"mml_script": "sys", "is_live": False,
                "apn_name": "internet_im3", "app_name": "TikTok", "payload": self.payload})
            self.assertEqual(response.status_code, 503)
            gateway.assert_not_called()

    def test_live_validation_and_outcome_never_claim_false_success(self):
        generated = self.client.post("/api/generate", json=self.payload).json()
        request = {"mml_script": generated["mml_script"], "is_live": True, "apn_name": "internet_im3",
                   "app_name": "TikTok", "payload": self.payload, "host": "10.240.12.11"}
        with patch("server.execute_to_testbed", return_value=["[SENT_UNVERIFIED] Prompts received."]) as gateway:
            self.assertEqual(self.client.post("/api/ssh/execute", json={**request, "host": "127.0.0.1"}).status_code, 422)
            self.assertEqual(self.client.post("/api/ssh/execute", json={**request, "mml_script": "sys\nundo all"}).status_code, 422)
            gateway.assert_not_called()
            response = self.client.post("/api/ssh/execute", json=request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["audit_entry"]["Status"], "SENT_UNVERIFIED")
        with patch("server.execute_to_testbed", return_value=["[FAILED] PermissionError; execution stopped."]):
            self.assertEqual(self.client.post("/api/ssh/execute", json=request).json()["status"], "FAILED")

    def test_revamp_names_and_snapshot_required_delta_rollback(self):
        revamp = self.client.post("/api/generate", json={**self.payload, "product_type": "Revamp"}).json()
        self.assertEqual(revamp["hierarchy_preview"]["rule_name"], "r_tiktok_v2_11010_11001000")
        delta = self.client.post("/api/generate", json={**self.payload, "product_type": "Reguler Update"}).json()
        self.assertTrue(all(not line or line.startswith("//") for line in delta["rollback_script"].splitlines()))

    def test_concurrent_generation_preserves_every_event(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.client.post("/api/generate", json=self.payload).status_code, range(12)))
        self.assertEqual(results, [200] * 12)
        history = self.client.get("/api/audit").json()
        self.assertEqual(len(history), 12)
        self.assertEqual(len({entry["Event ID"] for entry in history}), 12)

    def test_static_build_and_unknown_api_routes(self):
        if server.DIST.is_dir():
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("RELPOOL", response.text)
            class AssetParser(HTMLParser):
                urls = []

                def handle_starttag(self, tag, attributes):
                    attrs = dict(attributes)
                    url = attrs.get("src") if tag == "script" else attrs.get("href") if tag == "link" else None
                    if url and url.startswith("/"):
                        self.urls.append(url)

            parser = AssetParser()
            parser.feed(response.text)
            self.assertTrue(any(url.endswith(".js") for url in parser.urls))
            self.assertTrue(any(url.endswith(".css") for url in parser.urls))
            for url in parser.urls:
                asset = self.client.get(url)
                self.assertEqual(asset.status_code, 200, url)
                if url.endswith(".js"):
                    self.assertTrue(asset.headers["content-type"].startswith("text/javascript"), url)
                    self.assertEqual(asset.headers["cache-control"], "no-store")
                    self.assertNotIn("<html", asset.text[:100].lower())
        response = self.client.get("/api/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Unknown API endpoint")

    def seed_history(self, count=60):
        entries = [audit_service.build_audit_log(
            action="GENERATE MML" if index % 2 == 0 else "TESTBED_PUSH", apn="internet_im3",
            app=f"app_{index}", payload={"app_name": f"app_{index}", "he_cipher": "HIDDEN"},
        ) for index in range(count)]
        audit_service.save_history(entries)
        return audit_service.load_history()

    def test_paginated_audit_filters_and_full_export(self):
        self.seed_history()
        first = self.client.get("/api/audit/page").json()
        self.assertEqual(len(first["entries"]), 25)
        self.assertEqual(first["total"], 60)
        self.assertGreater(first["storage"]["active_bytes"], 0)
        second = self.client.get("/api/audit/page?offset=25&limit=25").json()
        self.assertEqual(len(second["entries"]), 25)
        self.assertNotEqual(first["entries"][0]["Event ID"], second["entries"][0]["Event ID"])
        filtered = self.client.get("/api/audit/page", params={"action": "GENERATE MML", "search": "app_2", "limit": 1}).json()
        self.assertEqual(filtered["filtered_total"], 6)
        self.assertEqual(len(filtered["entries"]), 1)
        exported = self.client.get("/api/audit/export", params={"action": "GENERATE MML", "search": "app_2"})
        self.assertEqual(exported.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual(len(rows), 6)
        self.assertNotIn("HIDDEN", exported.text)
        self.assertEqual(self.client.get("/api/audit/page?limit=101").status_code, 422)

    def test_archive_preserves_records_before_reset_and_is_downloadable(self):
        original = self.seed_history(12)
        page = self.client.get("/api/audit/page").json()
        response = self.client.post("/api/audit/archive", json={"confirmation": "ARCHIVE_AND_RESET", "expected_revision": page["storage"]["revision"]})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["archived_count"], 12)
        self.assertEqual(self.client.get("/api/audit").json(), [])
        self.assertEqual(self.client.get("/api/system-info").json()["statistics"]["total_wo"], 0)
        downloaded = self.client.get(result["download_url"])
        self.assertEqual(downloaded.status_code, 200)
        snapshot = json.loads(gzip.decompress(downloaded.content))
        self.assertEqual(snapshot["entries"], original)
        self.assertNotIn(b"HIDDEN", gzip.decompress(downloaded.content))
        after = self.client.get("/api/audit/page").json()["storage"]
        self.assertEqual(after["archive_count"], 1)
        self.assertEqual(after["archives"][0]["event_count"], 12)
        self.assertEqual(after["active_count"], 0)

    def test_archive_requires_confirmation_and_rejects_stale_revision(self):
        self.seed_history(2)
        revision = self.client.get("/api/audit/page").json()["storage"]["revision"]
        rejected = self.client.post("/api/audit/archive", json={"expected_revision": revision})
        self.assertEqual(rejected.status_code, 422)
        self.client.post("/api/generate", json=self.payload)
        response = self.client.post("/api/audit/archive", json={"confirmation": "ARCHIVE_AND_RESET", "expected_revision": revision})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.client.get("/api/audit").json()), 3)
        self.assertEqual(self.client.get("/api/audit/page").json()["storage"]["archive_count"], 0)

    def test_failed_archive_never_clears_active_history(self):
        original = self.seed_history(3)
        revision = self.client.get("/api/audit/page").json()["storage"]["revision"]
        with patch("core.services.audit_archive_service.gzip.GzipFile", side_effect=OSError("disk full")):
            response = self.client.post("/api/audit/archive", json={"confirmation": "ARCHIVE_AND_RESET", "expected_revision": revision})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get("/api/audit").json(), original)
        self.assertEqual(list((Path(self.directory.name) / "archives").iterdir()), [])

    def test_failed_reset_retains_both_active_records_and_completed_archive(self):
        original = self.seed_history(3)
        revision = self.client.get("/api/audit/page").json()["storage"]["revision"]
        with patch.object(audit_service, "_save_unlocked", side_effect=OSError("reset failed")):
            response = self.client.post("/api/audit/archive", json={"confirmation": "ARCHIVE_AND_RESET", "expected_revision": revision})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get("/api/audit").json(), original)
        archives = self.client.get("/api/audit/page").json()["storage"]["archives"]
        self.assertEqual(len(archives), 1)
        archive = self.client.get("/api/audit/archives/" + archives[0]["filename"])
        self.assertEqual(json.loads(gzip.decompress(archive.content))["entries"], original)

    def test_existing_archives_are_retained_across_rotations(self):
        downloads = []
        for count in (2, 3):
            self.seed_history(count)
            revision = self.client.get("/api/audit/page").json()["storage"]["revision"]
            result = self.client.post("/api/audit/archive", json={"confirmation": "ARCHIVE_AND_RESET", "expected_revision": revision}).json()
            downloads.append(result["download_url"])
        self.assertEqual(self.client.get("/api/audit/page").json()["storage"]["archive_count"], 2)
        self.assertEqual([json.loads(gzip.decompress(self.client.get(url).content))["event_count"] for url in downloads], [2, 3])
        self.assertEqual(self.client.get("/api/audit/archives/invalid.json.gz").status_code, 404)


if __name__ == "__main__":
    unittest.main()
