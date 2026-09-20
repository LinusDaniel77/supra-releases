"""Install public releases ONLY on disposable GitHub-hosted Windows/Mac runners.

No source checkout, signing secrets, provider credentials or application rebuild.
This checks installed backend startup and Windows installer replacement, NOT
interactive UI behavior, Gatekeeper/SmartScreen approval, or updater UI handoff.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import signal
import subprocess
import tempfile

REPO = "LinusDaniel77/supra-releases"


def version(tag):
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Only stable vMAJOR.MINOR.PATCH tags are allowed")
    return tag[1:]


def windows_version_matches(installed, tag):
    # Windows VERSIONINFO may render the reserved fourth component as .0.
    return installed in (version(tag), version(tag) + ".0")


def require_hosted_runner(env):
    if env.get("GITHUB_ACTIONS") != "true" or env.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("Installation is restricted to disposable GitHub-hosted runners")
    if not env.get("RUNNER_TEMP") or not Path(env["RUNNER_TEMP"]).is_dir():
        raise RuntimeError("Missing runner temporary directory")


def verify_asset(path, asset):
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("Published asset must have a GitHub SHA-256 digest")
    if path.stat().st_size != asset["size"]:
        raise ValueError("Asset byte count differs from published metadata")
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != "sha256:" + actual:
        raise ValueError("Asset digest differs from published metadata")
    return actual


def run(args, timeout=300, env=None):
    options = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt"
               else {"start_new_session": True})
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          env=env, **options) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               timeout=30, check=False, **options)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            process.communicate(timeout=30)
            raise
        text = output.decode("utf-8", errors="replace")
        if process.returncode:
            raise RuntimeError(f"{Path(args[0]).name if isinstance(args, list) else 'installer'} "
                               f"exited {process.returncode}: {text[-8000:]}")
        return text


def download(tag, name, root, report):
    version(tag)
    metadata = json.loads(run(["gh", "release", "view", tag, "--repo", REPO,
                               "--json", "tagName,isDraft,isPrerelease,assets"]))
    if metadata["isDraft"] or metadata["isPrerelease"] or metadata["tagName"] != tag:
        raise ValueError("Only published stable releases may be installed")
    matches = [asset for asset in metadata["assets"] if asset["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one exact release asset: {name}")
    directory = root / tag
    directory.mkdir(exist_ok=True)
    run(["gh", "release", "download", tag, "--repo", REPO, "--pattern", name,
         "--dir", str(directory)], timeout=600)
    path = directory / name
    sha = verify_asset(path, matches[0])
    report["artifacts"].append({"tag": tag, "name": name, "sha256": sha,
                                "bytes": path.stat().st_size})
    return path


def smoke(executable, label, evidence, report):
    # No model calls: the packaged smoke entry point starts its bundled stub backend.
    env = dict(os.environ)
    for key in list(env):
        if key.endswith("API_KEY") or key in ("GH_TOKEN", "GITHUB_TOKEN", "ELECTRON_RUN_AS_NODE"):
            env.pop(key)
    output = run([str(executable), "--smoke"], timeout=300, env=env)
    (evidence / f"{label}.log").write_text(output, encoding="utf-8")
    if "SMOKE OK: backend=bundled" not in output:
        raise RuntimeError(f"{label}: successful process exit without bundled-backend proof")
    report["checks"].append(label)
    return output


def install_windows(tag, root, evidence, report):
    installer = download(tag, f"Supra-Setup-{version(tag)}.exe", root, report)
    destination = root / "installed-supra"
    # NSIS /D must be LAST and unquoted, even when the path contains spaces.
    # https://nsis.sourceforge.io/Docs/Chapter3.html
    command = subprocess.list2cmdline([str(installer)]) + f" /S /currentuser /D={destination}"
    run(command, timeout=600)
    executable = destination / "Supra.exe"
    if not executable.is_file():
        raise RuntimeError("NSIS did not install Supra at the requested isolated destination")
    escaped = str(executable).replace("'", "''")
    installed_version = run(["pwsh", "-NoProfile", "-Command",
                             f"(Get-Item -LiteralPath '{escaped}').VersionInfo.ProductVersion"]).strip()
    if not windows_version_matches(installed_version, tag):
        raise RuntimeError(f"Installed version {installed_version!r} does not match {tag}")
    output = smoke(executable, f"{tag}-installed-start", evidence, report)
    return executable, output


def install_mac(tag, root, evidence, report):
    arch = {"arm64": "arm64", "x86_64": "x64"}[platform.machine()]
    dmg = download(tag, f"Supra-Setup-Mac-{arch}.dmg", root, report)
    run(["hdiutil", "verify", str(dmg)])
    mount = root / "mounted"
    app = root / "installed" / "Supra.app"
    app.parent.mkdir()
    run(["hdiutil", "attach", str(dmg), "-readonly", "-nobrowse", "-mountpoint", str(mount)])
    try:
        run(["ditto", str(mount / "Supra.app"), str(app)])
    finally:
        run(["hdiutil", "detach", str(mount)])
    with (app / "Contents/Info.plist").open("rb") as source:
        info = plistlib.load(source)
    if info["CFBundleShortVersionString"] != version(tag) or info["CFBundleIdentifier"] != "dev.silviaai.supra":
        raise RuntimeError("Installed Mac application identity/version mismatch")
    executable = app / "Contents/MacOS/Supra"
    binary = run(["lipo", "-archs", str(executable)]).strip()
    if binary != platform.machine():
        raise RuntimeError(f"Expected native executable, got {binary}")
    for launch in range(2):
        run(["codesign", "--verify", "--deep", "--strict", str(app)])
        smoke(executable, f"{tag}-installed-start-{launch + 1}", evidence, report)
    run(["codesign", "--verify", "--deep", "--strict", str(app)])
    report["checks"].append("bundle-seal-preserved-after-two-installed-launches")


def main():
    require_hosted_runner(os.environ)
    tag = os.environ["RELEASE_TAG"]
    version(tag)
    previous = os.environ.get("PREVIOUS_TAG", "")
    upgrade = os.environ.get("TEST_UPGRADE") == "true"
    if upgrade and (os.name != "nt" or tuple(map(int, version(previous).split("."))) >=
                    tuple(map(int, version(tag).split(".")))):
        raise ValueError("Upgrade requires Windows and a strictly older stable version")
    evidence = Path("installed-evidence")
    evidence.mkdir(exist_ok=True)
    report = {"release": tag, "platform": platform.platform(), "upgrade_from": previous if upgrade else None,
              "status": "failed", "artifacts": [], "checks": [],
              "limitations": ["No interactive CAD/UI or updater restart handoff test",
                              "No trusted publisher or clean-device OS reputation proof",
                              "No paid model evaluation"]}
    try:
        root = Path(tempfile.mkdtemp(prefix="supra-install-", dir=os.environ["RUNNER_TEMP"]))
        if os.name == "nt":
            if upgrade:
                _, output = install_windows(previous, root, evidence, report)
                match = re.search(r"^\[supra\] data dir: (.+)$", output, re.MULTILINE)
                if not match:
                    raise RuntimeError("Baseline smoke did not identify its actual data directory")
                data = Path(match[1].strip()).resolve()
                if not data.is_relative_to(Path(os.environ["APPDATA"]).resolve()) or not data.is_dir():
                    raise RuntimeError("Unexpected baseline application data directory")
                marker = data / "ci-preservation-marker.txt"
                marker.write_text("preserve-existing-project-data", encoding="utf-8")
            executable, output = install_windows(tag, root, evidence, report)
            if upgrade:
                if f"[supra] data dir: {data}" not in output:
                    raise RuntimeError("New installation silently switched its data directory")
                if marker.read_text(encoding="utf-8") != "preserve-existing-project-data":
                    raise RuntimeError("Installer replacement did not preserve the profile marker")
                report["checks"].append("profile-marker-preserved-across-installer-upgrade")
            smoke(executable, f"{tag}-second-installed-start", evidence, report)
        elif platform.system() == "Darwin":
            install_mac(tag, root, evidence, report)
        else:
            raise RuntimeError("Unsupported installation-test platform")
        report["status"] = "passed"
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        rendered = json.dumps(report, indent=2)
        (evidence / "verification.json").write_text(rendered + "\n", encoding="utf-8")
        print(rendered, flush=True)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                summary.write("### Published installer verification\n\n```json\n" + rendered + "\n```\n")


if __name__ == "__main__":
    main()
