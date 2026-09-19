from django.test import TestCase, override_settings
from cryptography.fernet import Fernet
from apps.events.services import encrypt_password, decrypt_password, FernetKeyError

class CryptoTests(TestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode()

    def test_encrypt_decrypt_cycle(self):
        with override_settings(FERNET_KEY=self.key):
            secret = "SuperSecretUniCAPassword123!#"
            encrypted = encrypt_password(secret)
            self.assertNotEqual(secret, encrypted)
            self.assertTrue(len(encrypted) > 20)

            decrypted = decrypt_password(encrypted)
            self.assertEqual(secret, decrypted)

    def test_empty_password(self):
        with override_settings(FERNET_KEY=self.key):
            self.assertEqual(encrypt_password(""), "")
            self.assertEqual(decrypt_password(""), "")

    def test_invalid_token(self):
        with override_settings(FERNET_KEY=self.key):
            with self.assertRaises(FernetKeyError):
                decrypt_password("InvalidCorruptedFernetToken==")

    def test_missing_fernet_key(self):
        with override_settings(FERNET_KEY=""):
            with self.assertRaises(FernetKeyError):
                encrypt_password("password")
