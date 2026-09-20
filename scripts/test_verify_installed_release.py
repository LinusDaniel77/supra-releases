import hashlib
from pathlib import Path
import tempfile
import unittest

from verify_installed_release import require_hosted_runner, verify_asset, version


class VerifierContracts(unittest.TestCase):
    def test_stable_versions_only(self):
        self.assertEqual(version("v0.11.5"), "0.11.5")
        for invalid in ("main", "v1.2.3-rc.1", "v01.2.3", "../v1.2.3", "v1.2.3\n", "v1.2.3;whoami"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                version(invalid)

    def test_no_installation_on_personal_or_self_hosted_machines(self):
        for env in ({}, {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"},
                    {"RUNNER_ENVIRONMENT": "github-hosted"},
                    {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}):
            with self.subTest(env=env), self.assertRaises(RuntimeError):
                require_hosted_runner(env)
        with tempfile.TemporaryDirectory() as directory:
            require_hosted_runner({"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                                   "RUNNER_TEMP": directory})

    def test_fail_closed_on_missing_wrong_digest_or_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(b"test installer fixture")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            valid = {"digest": "sha256:" + sha, "size": path.stat().st_size}
            self.assertEqual(verify_asset(path, valid), sha)
            for invalid in ({**valid, "size": 1}, {**valid, "digest": "sha256:" + "0" * 64},
                            {**valid, "digest": ""}, {"size": valid["size"]}):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    verify_asset(path, invalid)


if __name__ == "__main__":
    unittest.main()
