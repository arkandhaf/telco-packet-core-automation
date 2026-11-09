import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core.parsers.ciq_parser import get_sample_ciq_csv
from core.services import audit_service as audit


class UIWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patcher = patch.object(audit, "HISTORY_FILE", str(Path(self.directory.name) / "audit.json"))
        self.patcher.start()
        self.app = AppTest.from_file("app.py").run(timeout=30)

    def tearDown(self):
        self.patcher.stop()
        self.directory.cleanup()

    def button(self, label):
        return next(button for button in self.app.button if button.label == label)

    def text_input(self, label):
        return next(widget for widget in self.app.text_input if widget.label == label)

    def assert_no_exceptions(self):
        self.assertEqual([entry.message for entry in self.app.exception], [])

    def test_manual_generation_simulation_and_live_gate(self):
        self.assert_no_exceptions()
        self.button("Generate and assess change").click().run()
        self.assert_no_exceptions()
        self.assertEqual(len(audit.load_history()), 1)
        self.assertIn("generated", self.app.session_state)
        self.button("Run simulation").click().run()
        self.assert_no_exceptions()
        history = audit.load_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["Status"], "SIMULATED")
        self.assertEqual(len({entry["WO ID"] for entry in history}), 1)
        next(widget for widget in self.app.radio if widget.label == "Target Server Mode:").set_value("Live GGSN Testbed").run()
        self.assertTrue(self.button("Push config to testbed").disabled)
        self.assert_no_exceptions()

    def test_invalid_manual_input_is_not_audited_or_retained(self):
        self.text_input("Rating Group (RG ID)").set_value("not-numeric")
        self.button("Generate and assess change").click().run()
        self.assert_no_exceptions()
        self.assertTrue(self.app.error)
        self.assertEqual(audit.load_history(), [])
        self.assertNotIn("generated", self.app.session_state)

    def test_audit_failure_prevents_generation(self):
        with patch("ui.views.manual_view.append_history", side_effect=OSError("disk full")):
            self.button("Generate and assess change").click().run()
        self.assert_no_exceptions()
        self.assertTrue(self.app.error)
        self.assertNotIn("generated", self.app.session_state)

    def test_audit_filter_empty_state(self):
        self.button("Generate and assess change").click().run()
        self.text_input("Search work orders, APNs or applications").set_value("no-such-work-order").run()
        self.assert_no_exceptions()
        self.assertTrue(any("No events match" in entry.value for entry in self.app.info))

    def test_batch_reupload_with_same_filename_invalidates_results(self):
        mode = next(widget for widget in self.app.radio if widget.label == "Pilih Mode Input Provisioning:")
        mode.set_value(next(option for option in mode.options if "Batch" in option))
        upload = io.BytesIO(get_sample_ciq_csv().encode())
        upload.name = "ciq.csv"
        with patch("ui.views.batch_view.st.file_uploader", return_value=upload):
            self.app.run()
            self.button("Validate, assess and generate batch").click().run()
        self.assert_no_exceptions()
        self.assertEqual(len(self.app.session_state["batch_results"]), 4)
        self.assertEqual(len(audit.load_history()), 5)
        upload = io.BytesIO(b"bad_column\ninvalid")
        upload.name = "ciq.csv"
        with patch("ui.views.batch_view.st.file_uploader", return_value=upload):
            self.app.run()
            self.button("Validate, assess and generate batch").click().run()
        self.assert_no_exceptions()
        self.assertNotIn("batch_results", self.app.session_state)
        self.assertEqual(len(audit.load_history()), 5)


if __name__ == "__main__":
    unittest.main()