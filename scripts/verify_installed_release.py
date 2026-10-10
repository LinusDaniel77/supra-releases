"""Install public releases ONLY on disposable GitHub-hosted Windows/Mac runners.

No source checkout, signing secrets, provider credentials or application rebuild.
This checks installed backend startup, and that upgrading (the Windows installer
over the old one, or the new Mac app bundle over the old one) keeps the user's
data, NOT interactive UI behavior, Gatekeeper/SmartScreen approval, or updater
UI handoff.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import signal
import subprocess
import tempfile

REPO = "LinusDaniel77/supra-releases"


def version(tag):
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Only stable vMAJOR.MINOR.PATCH tags are allowed")
    return tag[1:]


def version_key(tag):
    return tuple(map(int, version(tag).split(".")))


def require_stable(tag, metadata):
    if metadata["tagName"] != tag:
        raise ValueError(f"Asked for {tag}, but GitHub returned {metadata['tagName']}")
    if metadata["isDraft"] or metadata["isPrerelease"]:
        kind = "a draft" if metadata["isDraft"] else "a pre-release"
        raise ValueError(f"{tag} is {kind}; only published stable releases may be installed")


def previous_stable(tag, releases):
    """The newest published stable release strictly older than tag.

    The upgrade test installs this first and then the new release over it. A
    pre-release or a draft cannot be installed (require_stable), so it is never
    chosen, and the listing's order is not trusted: versions are compared.
    """
    newest = None
    for release in releases:
        name = release.get("tagName", "")
        if release.get("isDraft") or release.get("isPrerelease"):
            continue
        try:
            key = version_key(name)
        except ValueError:
            continue
        if key < version_key(tag) and (newest is None or key > version_key(newest)):
            newest = name
    if newest is None:
        raise ValueError(f"No published stable release older than {tag} to upgrade from")
    return newest


def require_upgrade_platform(system, previous, tag):
    if system not in ("Windows", "Darwin"):
        raise ValueError("Upgrades are tested on Windows and macOS only")
    if version_key(previous) >= version_key(tag):
        raise ValueError(f"An upgrade to {tag} needs a strictly older stable version, not {previous}")


def user_data_root():
    """Where the operating system keeps each user's application data."""
    if os.name == "nt":
        return Path(os.environ["APPDATA"])
    return Path.home() / "Library" / "Application Support"


def reported_data_dir(output, user_data):
    """The data directory a launch reports, which must lie under user_data."""
    match = re.search(r"^\[supra\] data dir: (.+)$", output, re.MULTILINE)
    if not match:
        raise RuntimeError("The launch did not report its data directory")
    data = Path(match[1].strip()).resolve()
    if not data.is_relative_to(Path(user_data).resolve()):
        raise RuntimeError(f"Unexpected application data directory: {data}")
    return data


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


def check_sidecar(text, name, sha):
    """The published NAME.sha256: the hash the README tells users to compare,
    and the file name `shasum -c` looks for in their download folder. A wrong
    hash fails. A name with a build-runner path in front (every Mac DMG up to
    v0.11.52) is returned as a warning: the hash comparison still works, only
    `shasum -c` does not."""
    fields = text.split()
    if len(fields) != 2 or not re.fullmatch(r"[a-f0-9]{64}", fields[0]):
        raise ValueError(f"{name}.sha256 is not one '<sha256>  <file name>' line")
    published, listed = fields[0], fields[1].removeprefix("*")
    if published != sha:
        raise ValueError(f"{name}.sha256 gives {published}, but {name} hashes to {sha}")
    if listed == name:
        return None
    if listed.endswith("/" + name):
        return f"{name}.sha256 names {listed}, so `shasum -c` in a download folder cannot find the file"
    raise ValueError(f"{name}.sha256 names {listed}, not {name}")


class TimedOut(RuntimeError):
    """A command that was killed at its time limit, with what it printed first."""

    def __init__(self, name, timeout, output):
        super().__init__(f"{name} timed out after {timeout} s; its last output:\n{output[-4000:]}")
        self.output = output


def where_it_is_stuck(pid):
    """On a Mac, what a hung process is doing, taken before it is killed.

    A three-second stack sample of the process, and whether SecurityAgent, the
    process that draws the system's password and keychain prompts, is running:
    a prompt nobody can answer on a runner hangs a launch without a word.
    """
    if platform.system() != "Darwin":
        return ""
    notes = []
    for label, command in (("SecurityAgent", ["pgrep", "-lx", "SecurityAgent"]),
                           ("stack sample", ["sample", str(pid), "3"])):
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=60)
            # The main thread's stack comes first in a sample, so keep the start.
            notes.append(f"--- {label} (exit {done.returncode}) ---\n{done.stdout[:12000]}{done.stderr[:1000]}")
        except (OSError, subprocess.TimeoutExpired) as error:
            notes.append(f"--- {label}: {error} ---")
    found = "\n" + "\n".join(notes)
    print(f"A launch hung; what it was doing:{found}", flush=True)
    return found


def keychain_prompt(diagnostics):
    """Whether a hung Mac launch was waiting on a keychain prompt.

    SecurityAgent was running and the stack was inside a keychain read. That is
    what Electron's safeStorage does when the "Supra Safe Storage" item was made
    by an app with a different signature: every ad-hoc signed release has a new
    one, so macOS asks the user again after each update.
    """
    agent = re.search(r"^--- SecurityAgent \(exit 0\) ---\n\d+ SecurityAgent", diagnostics, re.MULTILINE)
    return bool(agent) and ("SecItemCopyMatching" in diagnostics or "SecKeychain" in diagnostics)


def run(args, timeout=300, env=None, diagnose=False):
    options = ({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt"
               else {"start_new_session": True})
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          env=env, **options) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            stuck = where_it_is_stuck(process.pid) if diagnose else ""
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               timeout=30, check=False, **options)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            output, _ = process.communicate(timeout=30)
            name = Path(args[0]).name if isinstance(args, list) else "installer"
            raise TimedOut(name, timeout, (output or b"").decode("utf-8", errors="replace") + stuck) from None
        text = output.decode("utf-8", errors="replace")
        if process.returncode:
            raise RuntimeError(f"{Path(args[0]).name if isinstance(args, list) else 'installer'} "
                               f"exited {process.returncode}: {text[-8000:]}")
        return text


def download(tag, name, root, report):
    version(tag)
    metadata = json.loads(run(["gh", "release", "view", tag, "--repo", REPO,
                               "--json", "tagName,isDraft,isPrerelease,assets"]))
    require_stable(tag, metadata)
    directory = root / tag
    directory.mkdir(exist_ok=True)

    def fetch(asset_name):
        matches = [asset for asset in metadata["assets"] if asset["name"] == asset_name]
        if len(matches) != 1:
            raise ValueError(f"Expected one exact release asset: {asset_name}")
        run(["gh", "release", "download", tag, "--repo", REPO, "--pattern", asset_name,
             "--dir", str(directory)], timeout=600)
        path = directory / asset_name
        return path, verify_asset(path, matches[0])

    path, sha = fetch(name)
    sidecar, _ = fetch(name + ".sha256")
    warning = check_sidecar(sidecar.read_text(encoding="utf-8"), name, sha)
    if warning:
        print(f"::warning::{tag}: {warning}", flush=True)
        report["warnings"].append(f"{tag}: {warning}")
    report["artifacts"].append({"tag": tag, "name": name, "sha256": sha,
                                "bytes": path.stat().st_size})
    return path


def smoke(executable, label, evidence, report):
    # No model calls: the packaged smoke entry point starts its bundled stub backend.
    env = dict(os.environ)
    for key in list(env):
        if key.endswith("API_KEY") or key in ("GH_TOKEN", "GITHUB_TOKEN", "ELECTRON_RUN_AS_NODE"):
            env.pop(key)
    try:
        output = run([str(executable), "--smoke"], timeout=300, env=env, diagnose=True)
    except TimedOut as error:
        # Keep what a hung launch printed: it is the only record of where it stopped.
        (evidence / f"{label}.log").write_text(error.output, encoding="utf-8")
        if keychain_prompt(error.output):
            raise RuntimeError(
                f"{label}: macOS asked for permission to read Supra's keychain item and nobody can "
                "answer on a runner. The item was made by the previous release, and an ad-hoc "
                "signature changes with every build, so a user sees this prompt after every update "
                "and the app waits on it.") from error
        raise
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
    app.parent.mkdir(exist_ok=True)
    if app.exists():
        # An upgrade: replace the app the way dragging the new one into
        # Applications does. The user's data lives outside the bundle.
        shutil.rmtree(app)
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
        output = smoke(executable, f"{tag}-installed-start-{launch + 1}", evidence, report)
    run(["codesign", "--verify", "--deep", "--strict", str(app)])
    report["checks"].append("bundle-seal-preserved-after-two-installed-launches")
    return executable, output


def main():
    require_hosted_runner(os.environ)
    tag = os.environ["RELEASE_TAG"]
    version(tag)
    previous = os.environ.get("PREVIOUS_TAG", "").strip()
    upgrade = os.environ.get("TEST_UPGRADE") == "true"
    if upgrade and not previous:
        previous = previous_stable(tag, json.loads(run(
            ["gh", "release", "list", "--repo", REPO, "--limit", "1000",
             "--json", "tagName,isDraft,isPrerelease"])))
    if upgrade:
        require_upgrade_platform(platform.system(), previous, tag)
    evidence = Path("installed-evidence")
    evidence.mkdir(exist_ok=True)
    report = {"release": tag, "platform": platform.platform(), "upgrade_from": previous if upgrade else None,
              "status": "failed", "artifacts": [], "checks": [], "warnings": [],
              "limitations": ["No interactive CAD/UI or updater restart handoff test",
                              "No trusted publisher or clean-device OS reputation proof",
                              "No paid model evaluation"]}
    try:
        root = Path(tempfile.mkdtemp(prefix="supra-install-", dir=os.environ["RUNNER_TEMP"]))
        if os.name == "nt":
            install = install_windows
        elif platform.system() == "Darwin":
            install = install_mac
        else:
            raise RuntimeError("Unsupported installation-test platform")
        if upgrade:
            # Install the older release, let it create its data directory, and
            # leave a marker there. Installing the new release over it must
            # keep the same directory and the marker: on Windows the NSIS
            # installer replaces the program, on a Mac the new app bundle
            # replaces the old one.
            _, output = install(previous, root, evidence, report)
            data = reported_data_dir(output, user_data_root())
            if not data.is_dir():
                raise RuntimeError(f"Baseline data directory does not exist: {data}")
            marker = data / "ci-preservation-marker.txt"
            marker.write_text("preserve-existing-project-data", encoding="utf-8")
        executable, output = install(tag, root, evidence, report)
        if upgrade:
            if reported_data_dir(output, user_data_root()) != data:
                raise RuntimeError("New installation silently switched its data directory")
            if marker.read_text(encoding="utf-8") != "preserve-existing-project-data":
                raise RuntimeError("Replacing the installation did not preserve the profile marker")
            report["checks"].append("profile-marker-preserved-across-upgrade")
        if os.name == "nt":
            smoke(executable, f"{tag}-second-installed-start", evidence, report)
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
