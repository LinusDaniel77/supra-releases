"""One stable signing identity for the Mac app, on a disposable runner.

WHY. Supra keeps the key that encrypts a person's saved session in the macOS
keychain ("Supra Safe Storage"). macOS lets an app read that item without
asking only if the app satisfies the requirement recorded when the item was
made. An ad-hoc signature's requirement is the hash of that one build, so every
update is a stranger to it and macOS asks for the person's password after every
update. A certificate signature's requirement names the certificate instead, so
every build signed with the same certificate is the same app to the keychain.

This module puts such a certificate into a temporary keychain on a GitHub-hosted
Mac runner and returns its SHA-1, which `codesign --sign` accepts. The release
build signs with the certificate kept in the SUPRA_MAC_SIGNING_P12 secret;
prove_mac_signing.py makes a throwaway one to test the idea.

It is not a Developer ID: Gatekeeper treats the app exactly as it treats an
ad-hoc one (it cannot verify the developer), and nothing here notarizes.

The private key is never printed. Only the certificate's public SHA-1 is.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

# The name the certificate carries. The build looks the identity up by SHA-1,
# so this is only what a person sees in `codesign -dv` and Keychain Access.
COMMON_NAME = "Supra by Silvia (self-signed)"

OPENSSL_CONFIG = """[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = {name}
[ext]
basicConstraints = critical, CA:false
keyUsage = critical, digitalSignature
extendedKeyUsage = critical, codeSigning
subjectKeyIdentifier = hash
"""


def sh(args, **options):
    """Run a command, failing with its output. Only the command's first two
    words are shown, never its arguments, which may hold a password."""
    done = subprocess.run([str(a) for a in args], capture_output=True, text=True, **options)
    if done.returncode:
        raise RuntimeError(f"{' '.join(map(str, args[:2]))} exited {done.returncode}: {(done.stderr or done.stdout)[-2000:]}")
    return done.stdout


def sha1_of(find_certificate_output):
    """The SHA-1 from `security find-certificate -Z`, upper case, or an error."""
    found = re.findall(r"^SHA-1 hash: ([0-9A-F]{40})$", find_certificate_output, re.MULTILINE)
    if len(found) != 1:
        raise RuntimeError(f"expected one signing certificate in the keychain, found {len(found)}")
    return found[0]


def search_list(list_keychains_output):
    """The keychains in `security list-keychains -d user` output, as paths."""
    return re.findall(r'"([^"]+)"', list_keychains_output)


def make_identity(directory, name=COMMON_NAME, days=3650):
    """A new self-signed code-signing certificate as (PKCS#12 path, password).

    The PKCS#12 uses the SHA-1/3DES encryption every macOS `security import`
    reads; OpenSSL 3 needs -legacy (or these explicit choices) to write it."""
    directory = Path(directory)
    config = directory / "signing.cnf"
    config.write_text(OPENSSL_CONFIG.format(name=name), encoding="utf-8")
    key, cert, p12 = directory / "signing-key.pem", directory / "signing-cert.pem", directory / "signing.p12"
    password = secrets.token_hex(16)
    sh(["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-sha256", "-days", str(days),
        "-keyout", key, "-out", cert, "-config", config])
    sh(["openssl", "pkcs12", "-export", "-inkey", key, "-in", cert, "-name", name, "-out", p12,
        "-keypbe", "PBE-SHA1-3DES", "-certpbe", "PBE-SHA1-3DES", "-macalg", "sha1",
        "-passout", f"pass:{password}"])
    key.unlink()
    return p12, password


def import_identity(p12, password, keychain):
    """Put the identity in a new keychain that codesign may use without asking.

    Returns the certificate's SHA-1. The keychain joins the user search list so
    codesign finds it; the login keychain stays the default, so the app's own
    keychain item is made where it always is."""
    keychain = Path(keychain)
    keychain_password = secrets.token_hex(16)
    sh(["security", "create-keychain", "-p", keychain_password, keychain])
    sh(["security", "set-keychain-settings", "-lut", "21600", keychain])
    sh(["security", "unlock-keychain", "-p", keychain_password, keychain])
    sh(["security", "import", p12, "-k", keychain, "-P", password, "-T", "/usr/bin/codesign"])
    # Without this, codesign's first use of the key waits on a dialog nobody can answer.
    sh(["security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s",
        "-k", keychain_password, keychain])
    current = search_list(sh(["security", "list-keychains", "-d", "user"]))
    if str(keychain) not in current:
        sh(["security", "list-keychains", "-d", "user", "-s", keychain, *current])
    return sha1_of(sh(["security", "find-certificate", "-a", "-Z", keychain]))


def import_from_environment(env=os.environ):
    """The release build's step: import SUPRA_MAC_SIGNING_P12 (base64) and write
    SUPRA_MAC_SIGN_IDENTITY to the job's environment for the build that follows."""
    encoded, password = env.get("SUPRA_MAC_SIGNING_P12", ""), env.get("SUPRA_MAC_SIGNING_P12_PASSWORD", "")
    if not encoded or not password:
        raise RuntimeError("SUPRA_MAC_SIGNING_P12 and SUPRA_MAC_SIGNING_P12_PASSWORD must both be set")
    runner_temp = Path(env["RUNNER_TEMP"])
    p12 = runner_temp / "supra-signing.p12"
    p12.write_bytes(base64.b64decode(encoded))
    try:
        identity = import_identity(p12, password, runner_temp / "supra-signing.keychain-db")
    finally:
        p12.unlink()
    with open(env["GITHUB_ENV"], "a", encoding="utf-8") as out:
        out.write(f"SUPRA_MAC_SIGN_IDENTITY={identity}\n")
    print(f"Signing identity {identity} ({COMMON_NAME}) is ready for codesign.")
    return identity


if __name__ == "__main__":
    if sys.argv[1:] != ["import"]:
        raise SystemExit("usage: mac_signing.py import")
    import_from_environment()
