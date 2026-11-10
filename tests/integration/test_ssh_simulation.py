import unittest
import os
from unittest.mock import patch
from cryptography.fernet import Fernet
from core.transports.ssh_gateway import execute_to_testbed
from core.transports.crypto import encrypt_password, decrypt_password


class TestSSHAndCryptoIntegration(unittest.TestCase):
    def test_simulation_mode_executes_all_commands(self):
        commands = [
            "sys",
            "service-v",
            "host h_tiktok domain *.tiktok.com sequence 65535",
            "filter f_tiktok l34-protocol any host h_tiktok",
            "filter-group fg_gaspol_tiktok filter f_tiktok",
            "q",
            "save",
            "Y"
        ]
        logs = execute_to_testbed(commands, is_live=False)
        self.assertEqual(len(logs), len(commands) + 1)
        self.assertIn("SIMULATION COMPLETED", logs[-1])

    @patch.dict(os.environ, {"SECRET_KEY": Fernet.generate_key().decode("ascii")})
    def test_encryption_and_decryption_cycle(self):
        plain_text = "IndosatCoreSecretPassword2026!"
        encrypted = encrypt_password(plain_text)
        self.assertNotEqual(encrypted, plain_text)
        decrypted = decrypt_password(encrypted)
        self.assertEqual(decrypted, plain_text)


if __name__ == "__main__":
    unittest.main()
