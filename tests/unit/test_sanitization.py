import unittest
from core.engines.huawei_service_v import (
    _sanitize_identifier,
    _sanitize_domain,
    _parse_domains,
    _sanitize_rg_sid
)


class TestSanitization(unittest.TestCase):
    def test_sanitize_identifier_normal(self):
        self.assertEqual(_sanitize_identifier("Indosat IM3 Internet"), "indosat_im3_internet")
        self.assertEqual(_sanitize_identifier("Gojek-Driver (B2B)"), "gojek_driver_b2b")

    def test_sanitize_identifier_edge_cases(self):
        self.assertEqual(_sanitize_identifier(""), "unknown")
        self.assertEqual(_sanitize_identifier("   "), "unknown")
        self.assertEqual(_sanitize_identifier("___"), "unknown")

    def test_sanitize_domain_protocols(self):
        self.assertEqual(_sanitize_domain("https://api.tiktok.com/"), "api.tiktok.com")
        self.assertEqual(_sanitize_domain("http://cdn.tiktok.com/"), "cdn.tiktok.com")
        self.assertEqual(_sanitize_domain("HTTP://V2.TIKTOKCDN.COM/ "), "v2.tiktokcdn.com")

    def test_parse_multi_domains_comma_and_newline(self):
        raw = "https://api.tiktok.com/,\n*.tiktokcdn.com,  v2.tiktok.com/"
        domains = _parse_domains(raw, app_fallback="tiktok")
        self.assertEqual(len(domains), 3)
        self.assertIn("api.tiktok.com", domains)
        self.assertIn("*.tiktokcdn.com", domains)
        self.assertIn("v2.tiktok.com", domains)

    def test_parse_domain_fallback(self):
        domains = _parse_domains("", app_fallback="youtube")
        self.assertEqual(domains, ["*.youtube.com"])

    def test_sanitize_rg_sid(self):
        self.assertEqual(_sanitize_rg_sid("11010.0", default="11010"), "11010")
        self.assertEqual(_sanitize_rg_sid("20000", default="10000"), "20000")
        self.assertEqual(_sanitize_rg_sid("abc", default="10000"), "10000")


if __name__ == "__main__":
    unittest.main()
