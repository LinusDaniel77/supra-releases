"""Prove that one stable signing certificate stops the keychain prompt on update.

On a disposable GitHub-hosted Mac runner, with a published release's app:

  A  the app signed with a new self-signed certificate;
  B  A with one file added (a different build, as an update is) and signed
     again with the SAME certificate;
  C  B signed ad-hoc instead, as every release so far has been.

A runs first and makes the "Supra Safe Storage" keychain item. B must then
start without macOS asking for the password: that is the claim. C must still
be stopped by the prompt, or the test proves nothing, because a launch that
never reads the keychain would pass B too. The prompt is detected the way the
installed-release check detects it: the launch hangs with SecurityAgent running
and the stack inside a keychain read.

No source checkout, provider credentials or release secrets. The certificate is
made here and thrown away with the runner.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import tempfile

from mac_signing import import_identity, make_identity
from verify_installed_release import download, require_hosted_runner, run, smoke, version

SERVICE = "Supra Safe Storage"


def requirement_of(text):
    """The designated requirement in `codesign -d -r-` output. An ad-hoc
    signature has only an implied one, which codesign prints as a comment."""
    for line in text.splitlines():
        line = line.strip().removeprefix("#").strip()
        if line.startswith("designated =>"):
            return line.split("=>", 1)[1].strip()
    return ""


def signature(app):
    """(designated requirement, CDHash) of a signed bundle, from codesign -d."""
    done = subprocess.run(["codesign", "-d", "-r-", "--verbose=4", str(app)], capture_output=True, text=True)
    text = done.stdout + done.stderr
    requirement = requirement_of(text)
    cdhash = next((line.split("=", 1)[1].strip() for line in text.splitlines() if line.startswith("CDHash=")), "")
    if not requirement or not cdhash:
        raise RuntimeError(f"codesign did not describe {app}: {text[-1500:]}")
    return requirement, cdhash


def sign(app, identity):
    """Sign the bundle the way desktop/scripts/adhoc-sign.js does, with `identity`."""
    shutil.rmtree(app / "Contents" / "_CodeSignature", ignore_errors=True)
    run(["codesign", "--force", "--deep", "--timestamp=none", "--sign", identity, str(app)], timeout=900)
    run(["codesign", "--verify", "--deep", "--strict", str(app)], timeout=600)
    return signature(app)


def extract_app(tag, root, report):
    arch = {"arm64": "arm64", "x86_64": "x64"}[platform.machine()]
    dmg = download(tag, f"Supra-Setup-Mac-{arch}.dmg", root, report)
    mount, app = root / "mounted", root / "base" / "Supra.app"
    app.parent.mkdir()
    run(["hdiutil", "attach", str(dmg), "-readonly", "-nobrowse", "-mountpoint", str(mount)])
    try:
        run(["ditto", str(mount / "Supra.app"), str(app)])
    finally:
        run(["hdiutil", "detach", str(mount)])
    with (app / "Contents/Info.plist").open("rb") as source:
        info = plistlib.load(source)
    if info["CFBundleShortVersionString"] != version(tag) or info["CFBundleIdentifier"] != "dev.silviaai.supra":
        raise RuntimeError("Mac application identity/version mismatch")
    return app


def copy(app, name):
    target = app.parent.parent / name / "Supra.app"
    target.parent.mkdir()
    run(["ditto", str(app), str(target)])
    return target


def main():
    require_hosted_runner(os.environ)
    if platform.system() != "Darwin":
        raise RuntimeError("This proof runs on a Mac runner")
    tag = os.environ.get("RELEASE_TAG", "").strip() or json.loads(
        run(["gh", "api", "repos/LinusDaniel77/supra-releases/releases/latest"]))["tag_name"]
    root = Path(tempfile.mkdtemp(prefix="supra-signing-", dir=os.environ["RUNNER_TEMP"]))
    evidence = Path("signing-evidence")
    evidence.mkdir(exist_ok=True)
    report = {"release": tag, "artifacts": [], "checks": [], "warnings": [], "status": "failed"}
    try:
        # Nothing may answer for the app before A makes its item.
        subprocess.run(["security", "delete-generic-password", "-s", SERVICE], capture_output=True)
        base = extract_app(tag, root, report)
        p12, password = make_identity(root)
        identity = import_identity(p12, password, root / "proof.keychain-db")
        report["identity_sha1"] = identity

        a = copy(base, "a")
        report["a"] = dict(zip(("requirement", "cdhash"), sign(a, identity)))
        b = copy(a, "b")
        (b / "Contents" / "Resources" / "next-build.txt").write_text("a later build\n", encoding="utf-8")
        report["b"] = dict(zip(("requirement", "cdhash"), sign(b, identity)))
        c = copy(b, "c")
        report["c"] = dict(zip(("requirement", "cdhash"), sign(c, "-")))
        if report["a"]["cdhash"] == report["b"]["cdhash"]:
            raise RuntimeError("B is the same build as A, so it would not stand for an update")
        if report["a"]["requirement"] != report["b"]["requirement"] or "certificate" not in report["a"]["requirement"]:
            raise RuntimeError(f"A and B should share a certificate requirement: {report['a']} {report['b']}")
        if "cdhash" not in report["c"]["requirement"]:
            raise RuntimeError(f"C should be pinned to its own build, as ad-hoc signatures are: {report['c']}")

        smoke(a / "Contents/MacOS/Supra", "a-first-launch-makes-the-keychain-item", evidence, report)
        smoke(b / "Contents/MacOS/Supra", "b-same-certificate-later-build", evidence, report)
        report["checks"].append("a-later-build-with-the-same-certificate-read-the-keychain-without-a-prompt")
        try:
            smoke(c / "Contents/MacOS/Supra", "c-ad-hoc-control", evidence, report)
        except RuntimeError as error:
            if "keychain" not in str(error):
                raise
            report["checks"].append("control-ad-hoc-build-was-stopped-by-the-keychain-prompt")
        else:
            raise RuntimeError("The ad-hoc control started without a prompt, so this test cannot tell the two apart")
        report["status"] = "passed"
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        rendered = json.dumps(report, indent=2)
        (evidence / "report.json").write_text(rendered, encoding="utf-8")
        print(rendered, flush=True)
        if report["status"] == "passed":
            print("::notice title=Stable Mac signing::A later build signed with the same certificate read the "
                  "keychain item without a prompt; the ad-hoc control was stopped by it.", flush=True)
        else:
            print(f"::error title=Stable Mac signing::{report.get('error', 'failed')[:900]}", flush=True)
        for kc in root.glob("*.keychain-db"):
            subprocess.run(["security", "delete-keychain", str(kc)], capture_output=True)


if __name__ == "__main__":
    main()
