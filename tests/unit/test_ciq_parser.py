import io
import unittest
import zipfile
import pandas as pd
from core.parsers.ciq_parser import (
    map_ciq_dataframe,
    process_ciq_batch,
    generate_combined_script_txt,
    generate_batch_zip,
    get_sample_ciq_csv
)


class TestCIQParser(unittest.TestCase):
    def test_alias_mapping_indonesian_headers(self):
        raw_df = pd.DataFrame([{
            "Tipe Produk": "New Product",
            "Nama APN": "internet_im3",
            "Aplikasi Target": "Mobile Legends",
            "Rating Group": "30000",
            "Service ID": "30001000",
            "Kecepatan": "Full Speed",
            "QCI": "1 (Voice/Low Latency)",
            "Domain": "*.mobilelegends.com"
        }])
        mapped_df, report = map_ciq_dataframe(raw_df)
        self.assertIn("product_type", mapped_df.columns)
        self.assertIn("apn_name", mapped_df.columns)
        self.assertIn("app_name", mapped_df.columns)
        self.assertIn("rg_val", mapped_df.columns)
        self.assertIn("sid_val", mapped_df.columns)

    def test_batch_processing_and_zip_packager(self):
        sample_csv = get_sample_ciq_csv()
        df = pd.read_csv(io.StringIO(sample_csv))
        results = process_ciq_batch(df)

        self.assertEqual(len(results), 4)
        zip_bytes = generate_batch_zip(results)
        self.assertIsInstance(zip_bytes, bytes)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            self.assertIn("ALL_MML_SCRIPTS.txt", names)
            self.assertIn("BATCH_MANIFEST.csv", names)
            self.assertTrue(any(n.startswith("scripts/") for n in names))
            self.assertTrue(any(n.startswith("rollbacks/") for n in names))


if __name__ == "__main__":
    unittest.main()
