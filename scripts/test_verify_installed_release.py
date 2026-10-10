import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from verify_installed_release import (TimedOut, check_sidecar, download, keychain_prompt, previous_stable,
                                      reported_data_dir, require_hosted_runner, require_stable,
                                      require_upgrade_platform, run, verify_asset, version,
                                      windows_version_matches)


class VerifierContracts(unittest.TestCase):
    def test_windows_versioninfo_reserved_component(self):
        for valid in ("0.11.5", "0.11.5.0"):
            self.assertTrue(windows_version_matches(valid, "v0.11.5"))
        for invalid in ("0.11.3.0", "0.11.5.1", "0.11.5.0.0", "0.11.5-rc.1"):
            self.assertFalse(windows_version_matches(invalid, "v0.11.5"))

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

    def test_upgrade_starts_from_the_newest_older_stable_release(self):
        def release(tag, draft=False, pre=False):
            return {"tagName": tag, "isDraft": draft, "isPrerelease": pre}
        # GitHub lists by creation date, so an old draft can come first.
        listing = [release("v0.11.1", draft=True), release("v0.11.52"), release("v0.11.51", pre=True),
                   release("v0.11.9"), release("v0.11.50"), release("nightly"), release("v0.11.49")]
        self.assertEqual(previous_stable("v0.11.52", listing), "v0.11.50")
        self.assertEqual(previous_stable("v0.11.50", listing), "v0.11.49")
        self.assertEqual(previous_stable("v0.11.10", listing), "v0.11.9")
        for tag, releases in (("v0.11.9", listing), ("v0.11.52", [release("v0.11.52"), release("v0.11.53")]),
                              ("v0.11.52", [release("v0.11.51", draft=True)])):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, f"older than {tag}"):
                previous_stable(tag, releases)

    def test_refusal_names_the_release_and_why(self):
        stable = {"tagName": "v0.11.51", "isDraft": False, "isPrerelease": False}
        require_stable("v0.11.51", stable)
        for metadata, reason in (({**stable, "isPrerelease": True}, "v0.11.51 is a pre-release"),
                                 ({**stable, "isDraft": True}, "v0.11.51 is a draft"),
                                 ({**stable, "tagName": "v0.11.50"}, "GitHub returned v0.11.50")):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                require_stable("v0.11.51", metadata)

    def test_upgrades_run_on_windows_and_mac_from_an_older_release(self):
        for system in ("Windows", "Darwin"):
            require_upgrade_platform(system, "v0.11.51", "v0.11.52")
        with self.assertRaisesRegex(ValueError, "Windows and macOS only"):
            require_upgrade_platform("Linux", "v0.11.51", "v0.11.52")
        for previous in ("v0.11.52", "v0.11.53", "v0.12.0"):
            with self.subTest(previous=previous), self.assertRaisesRegex(ValueError, "strictly older"):
                require_upgrade_platform("Darwin", previous, "v0.11.52")

    def test_the_data_directory_comes_from_the_launch_and_stays_in_user_data(self):
        with tempfile.TemporaryDirectory() as home:
            data = Path(home) / "Supra" / "data"
            output = f"[supra] backend: BUNDLED runtime at /x\n[supra] data dir: {data}\nSMOKE OK: backend=bundled\n"
            self.assertEqual(reported_data_dir(output, home), data.resolve())
            with self.assertRaisesRegex(RuntimeError, "did not report"):
                reported_data_dir("SMOKE OK: backend=bundled\n", home)
            with tempfile.TemporaryDirectory() as elsewhere, self.assertRaisesRegex(RuntimeError, "Unexpected"):
                reported_data_dir(f"[supra] data dir: {Path(elsewhere) / 'data'}\n", home)

    def test_a_command_killed_at_its_limit_keeps_what_it_printed(self):
        script = "import sys, time; print('[supra] data dir: /x', flush=True); time.sleep(30)"
        with self.assertRaises(TimedOut) as caught:
            run([sys.executable, "-c", script], timeout=2)
        self.assertIn("[supra] data dir: /x", caught.exception.output)
        self.assertIn("timed out after 2 s", str(caught.exception))

    def test_a_launch_waiting_on_a_keychain_prompt_is_named(self):
        # Shaped like the v0.11.51 to v0.11.52 upgrade run on macos-15.
        stack = "+ 2315 SecItemCopyMatching  (in Security) + 392\n+ 2315 mach_msg  (in libsystem_kernel.dylib)\n"
        prompt = "--- SecurityAgent (exit 0) ---\n7695 SecurityAgent\n\n--- stack sample (exit 0) ---\n" + stack
        self.assertTrue(keychain_prompt(prompt))
        no_agent = "--- SecurityAgent (exit 1) ---\n\n--- stack sample (exit 0) ---\n" + stack
        self.assertFalse(keychain_prompt(no_agent))
        other_hang = "--- SecurityAgent (exit 0) ---\n7695 SecurityAgent\n--- stack sample (exit 0) ---\n+ 9 poll\n"
        self.assertFalse(keychain_prompt(other_hang))

    def test_only_app_launches_are_sampled_when_they_hang(self):
        script = "import time; time.sleep(30)"
        with mock.patch("verify_installed_release.where_it_is_stuck", return_value="\n--- sampled ---") as sampled:
            with self.assertRaises(TimedOut) as plain:
                run([sys.executable, "-c", script], timeout=1)
            sampled.assert_not_called()
            self.assertNotIn("sampled", plain.exception.output)
            with self.assertRaises(TimedOut) as launch:
                run([sys.executable, "-c", script], timeout=1, diagnose=True)
            sampled.assert_called_once()
            self.assertIn("--- sampled ---", launch.exception.output)

    def test_the_published_checksum_file_matches_and_names_the_download(self):
        sha = "ab" * 32
        dmg = "Supra-Setup-Mac-arm64.dmg"
        self.assertIsNone(check_sidecar(f"{sha}  Supra-Setup-0.11.52.exe\n", "Supra-Setup-0.11.52.exe", sha))
        self.assertIsNone(check_sidecar(f"{sha} *{dmg}\r\n", dmg, sha))
        # Shaped like every Mac .sha256 up to v0.11.52: right hash, runner path in front.
        warning = check_sidecar(f"{sha}  source/desktop/dist/{dmg}\n", dmg, sha)
        self.assertIn("shasum -c", warning)
        for text, reason in ((f"{'cd' * 32}  {dmg}\n", "hashes to"),
                             (f"{sha}  Supra-Setup-Mac-x64.dmg\n", "not Supra-Setup-Mac-arm64.dmg"),
                             (f"{sha}  {dmg}\n{sha}  {dmg}\n", "one"), ("", "one"),
                             (f"{sha.upper()}  {dmg}\n", "one")):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, reason):
                check_sidecar(text, dmg, sha)

    def test_an_installer_is_only_used_after_its_checksum_file_checks_out(self):
        name = "Supra-Setup-Mac-arm64.dmg"
        installer = b"test installer fixture"
        sha = hashlib.sha256(installer).hexdigest()

        def attempt(sidecar):
            files = {name: installer}
            if sidecar is not None:
                files[name + ".sha256"] = sidecar
            assets = [{"name": n, "size": len(b), "digest": "sha256:" + hashlib.sha256(b).hexdigest()}
                      for n, b in files.items()]
            metadata = {"tagName": "v0.11.52", "isDraft": False, "isPrerelease": False, "assets": assets}

            def gh(args, timeout=300, env=None, diagnose=False):
                if args[:3] == ["gh", "release", "view"]:
                    return json.dumps(metadata)
                pattern = args[args.index("--pattern") + 1]
                (Path(args[args.index("--dir") + 1]) / pattern).write_bytes(files[pattern])
                return ""

            report = {"artifacts": [], "warnings": []}
            with tempfile.TemporaryDirectory() as root, mock.patch("verify_installed_release.run", gh):
                path = download("v0.11.52", name, Path(root), report)
                self.assertEqual(path.name, name)
            return report

        self.assertEqual(attempt(f"{sha}  {name}\n".encode())["warnings"], [])
        self.assertEqual(len(attempt(f"{sha}  source/desktop/dist/{name}\n".encode())["warnings"]), 1)
        with self.assertRaisesRegex(ValueError, "hashes to"):
            attempt(f"{'0' * 64}  {name}\n".encode())
        with self.assertRaisesRegex(ValueError, "one exact release asset: Supra-Setup-Mac-arm64.dmg.sha256"):
            attempt(None)


if __name__ == "__main__":
    unittest.main()
