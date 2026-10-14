import base64
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import mac_signing
from mac_signing import import_from_environment, make_identity, search_list, sha1_of


class ReadsSecurityOutput(unittest.TestCase):
    ONE = ('keychain: "/Users/runner/work/_temp/supra-signing.keychain-db"\nversion: 512\n'
           'SHA-256 hash: ' + "AB" * 32 + '\nSHA-1 hash: ' + "0123456789ABCDEF0123" * 2 + '\nclass: 0x80001000\n')

    def test_the_one_certificate_hash(self):
        self.assertEqual(sha1_of(self.ONE), "0123456789ABCDEF0123" * 2)

    def test_refuses_none_or_two_rather_than_signing_with_a_guess(self):
        for text in ("", self.ONE + self.ONE):
            with self.assertRaises(RuntimeError):
                sha1_of(text)

    def test_the_search_list_keeps_every_keychain(self):
        text = ('    "/Users/runner/Library/Keychains/login.keychain-db"\n'
                '    "/Library/Keychains/System.keychain"\n')
        self.assertEqual(search_list(text), ["/Users/runner/Library/Keychains/login.keychain-db",
                                             "/Library/Keychains/System.keychain"])


class MakesACodeSigningCertificate(unittest.TestCase):
    def test_a_code_signing_certificate_that_macos_can_import(self):
        with tempfile.TemporaryDirectory() as directory:
            p12, password = make_identity(directory, name="Supra test")
            self.assertFalse((Path(directory) / "signing-key.pem").exists(), "the bare private key must not be left behind")
            cert = subprocess.run(["openssl", "x509", "-in", Path(directory) / "signing-cert.pem", "-noout", "-text"],
                                  capture_output=True, text=True, check=True).stdout
            self.assertIn("Code Signing", cert)
            self.assertIn("CA:FALSE", cert)
            self.assertIn("CN = Supra test", cert)
            # The encryption macOS `security import` reads, whatever OpenSSL wrote by default.
            info = subprocess.run(["openssl", "pkcs12", "-in", p12, "-info", "-noout", "-passin", f"pass:{password}",
                                   *(["-legacy"] if self.openssl3() else [])],
                                  capture_output=True, text=True)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertRegex(info.stdout + info.stderr, r"(?i)TripleDES|3DES|des-ede3")
            self.assertRegex(info.stdout + info.stderr, r"(?i)MAC: sha1")

    @staticmethod
    def openssl3():
        return subprocess.run(["openssl", "version"], capture_output=True, text=True).stdout.startswith("OpenSSL 3")


class ReleaseBuildStep(unittest.TestCase):
    def test_needs_both_secrets(self):
        for env in ({}, {"SUPRA_MAC_SIGNING_P12": "eA=="}, {"SUPRA_MAC_SIGNING_P12_PASSWORD": "x"}):
            with self.assertRaises(RuntimeError):
                import_from_environment(env)

    def test_hands_the_identity_to_the_build_and_leaves_no_key_file(self):
        with tempfile.TemporaryDirectory() as directory:
            github_env = Path(directory) / "env"
            env = {"SUPRA_MAC_SIGNING_P12": base64.b64encode(b"p12 bytes").decode(),
                   "SUPRA_MAC_SIGNING_P12_PASSWORD": "pw", "RUNNER_TEMP": directory, "GITHUB_ENV": str(github_env)}
            seen = {}

            def fake_import(p12, password, keychain):
                seen["bytes"] = Path(p12).read_bytes()
                return "AB" * 20

            with mock.patch.object(mac_signing, "import_identity", fake_import):
                self.assertEqual(import_from_environment(env), "AB" * 20)
            self.assertEqual(seen["bytes"], b"p12 bytes")
            self.assertEqual(github_env.read_text(), f"SUPRA_MAC_SIGN_IDENTITY={'AB' * 20}\n")
            self.assertFalse((Path(directory) / "supra-signing.p12").exists())


class ReadsCodesignRequirements(unittest.TestCase):
    def test_a_certificate_requirement_and_an_implied_ad_hoc_one(self):
        from prove_mac_signing import requirement_of
        cert = 'Executable=/x/Supra\ndesignated => identifier "dev.silviaai.supra" and certificate root = H"0123"\n'
        adhoc = 'Executable=/x/Supra\n# designated => cdhash H"f899"\n'
        self.assertEqual(requirement_of(cert), 'identifier "dev.silviaai.supra" and certificate root = H"0123"')
        self.assertEqual(requirement_of(adhoc), 'cdhash H"f899"')
        self.assertEqual(requirement_of("Executable=/x/Supra\n"), "")


if __name__ == "__main__":
    unittest.main()
