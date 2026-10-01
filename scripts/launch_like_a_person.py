"""Install a published Supra and launch it the way a person does.

The release verifier starts the app with --smoke, which never opens the
windows a person sees. That is how 0.11.12 to 0.11.32 shipped with an empty
terms window that nobody could get past. This walks the real path on the
installed build, with a fresh profile, and fails on anything short of it:

  1. first launch: the terms window shows the agreement text;
  2. tick every box and press Accept, through the page itself;
  3. the launch screen shows its steps, the engine starts, and the app
     window opens with real content (not an error page, not blank);
  4. Settings opens and shows its page;
  5. quit, launch again: no terms window, straight into the app.

Everything is read over the Chromium remote-debugging port: page URLs,
document text, and pixel statistics of each page's own capture.
"""

from __future__ import annotations

import base64
import io
import json
import os
import platform
import plistlib
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TAG = os.environ.get("RELEASE_TAG", "v0.11.33")
ROOT = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "launch-test"
PORT = 9223
IS_WIN = os.name == "nt"
FAILURES: list[str] = []


def log(*parts):
    print(*parts, flush=True)


def check(ok, what):
    log(("PASS " if ok else "FAIL ") + what)
    if not ok:
        FAILURES.append(what)
    return ok


def gh_download(name):
    # A build may still be uploading: wait for the asset rather than fail.
    for _ in range(80):
        listed = subprocess.run(["gh", "release", "view", TAG, "-R", "LinusDaniel77/supra-releases",
                                 "--json", "assets", "-q", ".assets[].name"],
                                capture_output=True, text=True).stdout.split()
        if name in listed:
            break
        log(f"   waiting for {name} on {TAG}")
        time.sleep(30)
    subprocess.run(["gh", "release", "download", TAG, "-R", "LinusDaniel77/supra-releases",
                    "-p", name, "-D", str(ROOT), "--clobber"], check=True)
    return ROOT / name


def install():
    ROOT.mkdir(parents=True, exist_ok=True)
    version = TAG.lstrip("v")
    if IS_WIN:
        installer = gh_download(f"Supra-Setup-{version}.exe")
        dest = ROOT / "installed"
        subprocess.run(subprocess.list2cmdline([str(installer)]) + f" /S /currentuser /D={dest}",
                       check=True, timeout=600)
        return dest / "Supra.exe"
    arch = {"arm64": "arm64", "x86_64": "x64"}[platform.machine()]
    dmg = gh_download(f"Supra-Setup-Mac-{arch}.dmg")
    mount, app = ROOT / "mounted", ROOT / "installed" / "Supra.app"
    app.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["hdiutil", "attach", str(dmg), "-readonly", "-nobrowse", "-mountpoint", str(mount)],
                   check=True)
    try:
        subprocess.run(["ditto", str(mount / "Supra.app"), str(app)], check=True)
    finally:
        subprocess.run(["hdiutil", "detach", str(mount)], check=True)
    with (app / "Contents/Info.plist").open("rb") as f:
        assert plistlib.load(f)["CFBundleShortVersionString"] == version
    return app / "Contents/MacOS/Supra"


def profile_dir():
    # Electron names userData after package.json "name" (supra-desktop), not
    # the product name; the app logs it as "data dir .../supra-desktop/data".
    if IS_WIN:
        return Path(os.environ["APPDATA"]) / "supra-desktop"
    return Path.home() / "Library/Application Support/supra-desktop"


def pages():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
            return [p for p in json.loads(r.read()) if p.get("type") == "page"]
    except Exception:  # noqa: BLE001
        return []


class Page:
    def __init__(self, info):
        import websocket  # noqa: PLC0415

        self.info = info
        self.ws = websocket.create_connection(info["webSocketDebuggerUrl"], timeout=20,
                                              suppress_origin=True)
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                return msg

    def eval(self, expr):
        res = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                             "awaitPromise": True})
        return res.get("result", {}).get("result", {}).get("value")

    def pixels(self):
        from PIL import Image, ImageStat  # noqa: PLC0415

        shot = self.call("Page.captureScreenshot", {"format": "png"}).get("result", {}).get("data")
        if not shot:
            return {"captured": False}
        img = Image.open(io.BytesIO(base64.b64decode(shot))).convert("RGB")
        small = img.resize((max(1, img.width // 4), max(1, img.height // 4)))
        return {"captured": True, "size": img.size, "colours": len(set(small.getdata())),
                "stddev": [round(s) for s in ImageStat.Stat(small).stddev]}

    def close(self):
        self.ws.close()


def wait_for_page(pred, timeout, label):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for p in pages():
            if pred(p):
                log(f"   {label} appeared after {time.monotonic() - t0:.1f}s: {p.get('url')}")
                return p
        time.sleep(0.5)
    log(f"   {label} did not appear within {timeout}s; pages: {[p.get('url') for p in pages()]}")
    return None


def page_text(page):
    return page.eval("document.body ? document.body.innerText : ''") or ""


def launch(exe, label):
    elog = ROOT / f"electron-{label}.log"
    proc = subprocess.Popen([str(exe), f"--remote-debugging-port={PORT}",
                             "--enable-logging=file", f"--log-file={elog}"])
    log(f"== {label}: launched pid {proc.pid}")
    return proc, elog


def stop(proc):
    if IS_WIN:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        subprocess.run(["pkill", "-f", "Supra.app/Contents"], capture_output=True)
    time.sleep(4)


def is_app_url(url):
    return url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:")


def first_launch(exe):
    proc, elog = launch(exe, "first")
    try:
        # 1. Terms window, with the agreement in it.
        info = wait_for_page(lambda p: p.get("url", "").endswith("legal.html"), 60, "terms window")
        if not check(info is not None, "first launch opens the terms window"):
            return
        legal = Page(info)
        time.sleep(1.5)
        href = legal.eval("location.href")
        text = page_text(legal)
        terms = legal.eval("(document.getElementById('terms') || {}).textContent || ''") or ""
        px = legal.pixels()
        log("   terms page:", json.dumps({"href": href, "text_chars": len(text), "terms_chars": len(terms),
                                         "pixels": px}))
        check(href and href.startswith("file:"), "terms page loaded from the app, not an error page")
        check("Before you use Supra" in text, "terms window shows its heading")
        check("SUPRA TERMS OF USE" in terms and len(terms) > 5000, "the full agreement text is shown")
        check(px.get("captured") and px.get("colours", 0) > 20, "terms window renders more than one flat colour")

        # 2. Agree, through the page.
        boxes = legal.eval("document.querySelectorAll('input[type=checkbox]').length")
        legal.eval("document.querySelectorAll('input[type=checkbox]').forEach(b => { b.click(); })")
        enabled = legal.eval("!document.getElementById('accept').disabled")
        check(boxes and boxes >= 3 and enabled, f"ticking all {boxes} boxes enables Accept")
        legal.eval("document.getElementById('accept').click()")
        legal.close()

        # 3. Launch screen, engine, app window.
        splash = wait_for_page(lambda p: p.get("url", "").endswith("splash.html"), 20, "launch screen")
        if splash:
            sp = Page(splash)
            time.sleep(1.0)
            steps = sp.eval("document.querySelectorAll('#steps li').length")
            st = page_text(sp)
            log("   launch screen:", json.dumps({"steps": steps, "text": st[:160]}))
            check(steps == 5, "launch screen lists its five steps")
            check("Supra" in st, "launch screen shows the wordmark")
            sp.close()
        else:
            check(False, "launch screen appears after Accept")
        app = wait_for_page(lambda p: is_app_url(p.get("url", "")), 300, "app window")
        if not check(app is not None, "the engine starts and the app window opens"):
            return
        page = Page(app)
        for _ in range(60):  # the app paints after its bundle loads
            text = page_text(page)
            if len(text) > 40:
                break
            time.sleep(1)
        px = page.pixels()
        log("   app window:", json.dumps({"url": app.get("url"), "text": text[:300], "pixels": px}))
        check(len(text) > 40, "the app window shows real content")
        check(px.get("captured") and px.get("colours", 0) > 20, "the app window is not blank")
        check(splash is None or not any(p.get("url", "").endswith("splash.html") for p in pages()),
              "the launch screen closes once the app is up")

        # 4. Settings.
        page.eval("window.supra && window.supra.openSettings && window.supra.openSettings()")
        settings = wait_for_page(lambda p: p.get("url", "").endswith("settings.html"), 30, "Settings")
        if check(settings is not None, "Settings opens"):
            sp = Page(settings)
            time.sleep(1.5)
            stext = page_text(sp)
            spx = sp.pixels()
            log("   settings:", json.dumps({"text": stext[:200], "pixels": spx}))
            check(len(stext) > 40 and spx.get("colours", 0) > 20, "Settings shows its page")
            sp.close()
        page.close()
        settings_file = profile_dir() / "settings.json"
        saved = json.loads(settings_file.read_text("utf-8")) if settings_file.exists() else {}
        check(saved.get("legalAcceptanceVersion") == "1.3", "acceptance of the 1.3 terms was recorded")
    finally:
        stop(proc)
        if elog.exists():
            log("   electron log tail:", elog.read_text("utf-8", "replace")[-1500:])


def second_launch(exe):
    proc, elog = launch(exe, "second")
    try:
        app = wait_for_page(lambda p: is_app_url(p.get("url", "")) or p.get("url", "").endswith("legal.html"),
                            300, "first window")
        check(app is not None and is_app_url(app.get("url", "")),
              "second launch goes straight into the app, with no terms window")
        if app and is_app_url(app.get("url", "")):
            page = Page(app)
            for _ in range(60):
                text = page_text(page)
                if len(text) > 40:
                    break
                time.sleep(1)
            check(len(text) > 40, "second launch shows the app")
            page.close()
    finally:
        stop(proc)


def main():
    exe = install()
    log("installed:", exe, "on", platform.system(), platform.machine())
    first_launch(exe)
    second_launch(exe)
    log("")
    if FAILURES:
        log(f"LAUNCH TEST FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            log("  -", f)
        return 1
    log("LAUNCH TEST PASSED: installed, agreed, launched, Settings, relaunched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
