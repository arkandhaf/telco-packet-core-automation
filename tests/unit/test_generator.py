import unittest
from core.engines.huawei_service_v import (
    HuaweiServiceVEngine,
    generate_huawei_mml_script,
    generate_rollback_script
)


class TestHuaweiEngine(unittest.TestCase):
    def setUp(self):
        self.engine = HuaweiServiceVEngine()

    def test_new_product_generation(self):
        payload = {
            "product_type": "New Product",
            "apn_name": "internet_im3",
            "app_name": "tiktok",
            "rg_val": "11010",
            "sid_val": "11001000",
            "capping_option": "20 MB/day",
            "app_domain": "*.tiktok.com, *.v2.tiktokcdn.com"
        }
        mml = self.engine.generate_provisioning(payload)
        self.assertIn("HUAWEI SERVICE-V MML SCRIPT - NEW PRODUCT PROVISIONING", mml)
        self.assertIn("host h_tiktok_1 domain *.tiktok.com", mml)
        self.assertIn("host h_tiktok_2 domain *.v2.tiktokcdn.com", mml)
        self.assertIn("user-profile crbn_internet_im3_sy", mml)
        self.assertIn("cbb-id cbbid_on_11010", mml)
        self.assertIn("rule r_tiktok_11010_11001000", mml)

    def test_revamp_generation(self):
        payload = {
            "product_type": "Revamp",
            "apn_name": "b2b_corporate",
            "app_name": "gojek",
            "rg_val": "20000",
            "sid_val": "20001000",
        }
        mml = self.engine.generate_provisioning(payload)
        self.assertIn("HUAWEI SERVICE-V MML SCRIPT - PRODUCT REVAMP", mml)
        self.assertIn("rule r_gojek_v2_20000_20001000", mml)
        self.assertIn("undo rule-binding r_gojek_v1_20000_20001000", mml)

    def test_reguler_update_delta_patch(self):
        payload = {
            "product_type": "Reguler Update",
            "apn_name": "internet_im3",
            "app_name": "youtube",
            "rg_val": "11010",
            "app_domain": "*.youtube.com"
        }
        mml = self.engine.generate_provisioning(payload)
        self.assertIn("HUAWEI SERVICE-V MML SCRIPT - REGULER UPDATE (DELTA PATCH)", mml)
        self.assertIn("filter-group fg_gaspol_youtube", mml)
        # Delta patch should not recreate cbb-id
        self.assertNotIn("cbb-id cbbid_on", mml)

    def test_rollback_generation(self):
        payload = {
            "product_type": "New Product",
            "apn_name": "internet_im3",
            "app_name": "tiktok",
            "rg_val": "11010",
            "sid_val": "11001000"
        }
        rb = self.engine.generate_rollback(payload)
        self.assertIn("ROLLBACK DRAFT - NEW PRODUCT FULL ROLLBACK", rb)
        self.assertIn("undo rule-binding r_tiktok_11010_11001000", rb)
        self.assertIn("undo rule r_tiktok_11010_11001000", rb)
        self.assertIn("undo filter-group fg_gaspol_tiktok", rb)


if __name__ == "__main__":
    unittest.main()
