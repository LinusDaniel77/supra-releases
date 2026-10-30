"""Prove that a secret kept through /usr/bin/security survives an update without a prompt.

Every ad-hoc signed Supra build is a new app to the keychain, so after an update
macOS asks for the password before Supra can read what the last build saved
(Silvia-Supra #118). A stable designated requirement and a stable self-signed
certificate were both tried and both still prompted (prove_mac_signing.py).

The idea here: let Apple's own keychain tool, /usr/bin/security, hold the item.
The keychain then sees that tool, which an update does not change, and not
Supra. On a disposable GitHub-hosted Mac runner, with two builds of a small app
(keychain_probe.c) that differ as two releases do:

  control  build 1 stores a secret through the Security framework, as
           Electron's safeStorage does; build 2 must be stopped by the prompt,
           or this runner shows no prompt and the claim below proves nothing;
  claim    build 1 stores a secret through /usr/bin/security; build 2 reads it
           through the same tool, gets the same value, and is not prompted.

No source checkout, credentials or secrets: the secrets are made here and
thrown away with the runner.
"""

from __future__ import annotations

import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
WAIT_S = 90


def build(out: Path, number: int) -> Path:
    exe = out / f"build{number}"
    subprocess.run(["clang", "-O1", f"-DBUILD={number}", "-framework", "Security", "-framework",
                    "CoreFoundation", "-o", str(exe), str(HERE / "keychain_probe.c")], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(exe)], check=True)
    done = subprocess.run(["codesign", "-d", "--verbose=4", str(exe)], capture_output=True, text=True)
    cdhash = next(line.split("=", 1)[1] for line in (done.stdout + done.stderr).splitlines()
                  if line.startswith("CDHash="))
    print(f"build {number}: ad-hoc, CDHash {cdhash}")
    return exe


def security_agent_running() -> bool:
    return subprocess.run(["pgrep", "-x", "SecurityAgent"], capture_output=True).returncode == 0


def launch(exe: Path, *args: str) -> dict:
    """Run one mode; a run that hangs while SecurityAgent is up was prompted."""
    proc = subprocess.Popen([str(exe), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=WAIT_S)
        return {"exit": proc.returncode, "out": out.strip(), "err": err.strip(), "prompted": False}
    except subprocess.TimeoutExpired:
        prompted = security_agent_running()
        proc.kill()
        out, err = proc.communicate()
        subprocess.run(["pkill", "-x", "SecurityAgent"], capture_output=True)
        return {"exit": None, "out": out.strip(), "err": err.strip(), "prompted": prompted,
                "timed_out_s": WAIT_S}


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("needs macOS")
    report: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        one, two = build(Path(tmp), 1), build(Path(tmp), 2)

        secret = secrets.token_hex(32)
        report["control_write"] = launch(one, "api-write", "Supra Probe API", "probe", secret)
        report["control_read"] = launch(two, "api-read", "Supra Probe API", "probe")

        secret = secrets.token_hex(32)
        report["claim_write"] = launch(one, "tool-write", "Supra Probe Tool", "probe", secret)
        report["claim_read_same_build"] = launch(one, "tool-read", "Supra Probe Tool", "probe")
        report["claim_read"] = launch(two, "tool-read", "Supra Probe Tool", "probe")
        attrs = subprocess.run(["security", "find-generic-password", "-s", "Supra Probe Tool", "-a", "probe"],
                               capture_output=True, text=True)
        report["claim_item"] = (attrs.stdout + attrs.stderr).strip()
        claim_value_matches = report["claim_read"]["out"] == secret

    for key in ("control_write", "claim_write", "claim_read_same_build", "claim_read"):
        report[key]["out"] = "<secret>" if report[key]["out"] else ""
    print(json.dumps(report, indent=2))

    control_ok = report["control_write"]["exit"] == 0 and report["control_read"]["prompted"]
    claim_ok = (report["claim_write"]["exit"] == 0 and report["claim_read"]["exit"] == 0
                and not report["claim_read"]["prompted"] and claim_value_matches)
    print(f"control (framework, build 2 prompted): {'yes' if control_ok else 'NO'}")
    print(f"claim (security tool, build 2 read it, same value, no prompt): {'yes' if claim_ok else 'NO'}")
    if not control_ok:
        print("The control was not prompted, so this runner cannot show the claim either way.")
        return 1
    return 0 if claim_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
