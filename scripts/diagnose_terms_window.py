"""Install a published Windows Supra and record what its terms window shows.

A one-off diagnostic for a report that the "Before you use Supra" window
opens with nothing in it on an installed 0.11.32. The release verifier
launches with --smoke, which skips the terms window entirely, so it can
never see this. This launches the installed app the way a person does, with
a fresh profile that has not accepted the terms, and records:

  - every top-level window of the app: title, visible, position, size;
  - through the Chromium remote-debugging port: each page's URL, its
    readyState, whether the preload bridge exists, and the start of its
    visible text;
  - a capture of each page and of the whole desktop, printed as small JPEGs
    in base64 between markers so they can be read from the job log;
  - Electron's own log.

It changes nothing it did not create, and it never accepts the terms.
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TAG = os.environ.get("RELEASE_TAG", "v0.11.32")
ROOT = Path(os.environ.get("RUNNER_TEMP", "C:/diag")) / "terms-diag"
PORT = 9223


def log(*parts):
    print(*parts, flush=True)


def dump_jpeg(label, png_or_image, width=900):
    from PIL import Image  # noqa: PLC0415

    img = png_or_image if isinstance(png_or_image, Image.Image) else Image.open(io.BytesIO(png_or_image))
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, int(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55)
    data = base64.b64encode(buf.getvalue()).decode()
    log(f"=====BEGIN IMAGE {label} {img.width}x{img.height}=====")
    for i in range(0, len(data), 120):
        log(data[i:i + 120])
    log(f"=====END IMAGE {label}=====")


def install():
    ROOT.mkdir(parents=True, exist_ok=True)
    name = f"Supra-Setup-{TAG.lstrip('v')}.exe"
    subprocess.run(["gh", "release", "download", TAG, "-R", "LinusDaniel77/supra-releases",
                    "-p", name, "-D", str(ROOT), "--clobber"], check=True)
    dest = ROOT / "installed"
    cmd = subprocess.list2cmdline([str(ROOT / name)]) + f" /S /currentuser /D={dest}"
    subprocess.run(cmd, check=True, shell=False, timeout=600)
    exe = dest / "Supra.exe"
    assert exe.is_file(), "installer did not place Supra.exe"
    return exe


def app_windows(pids):
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if buf.value:
                found.append({"title": buf.value, "visible": bool(user32.IsWindowVisible(hwnd)),
                              "iconic": bool(user32.IsIconic(hwnd)),
                              "rect": [r.left, r.top, r.right - r.left, r.bottom - r.top]})
        return True

    user32.EnumWindows(cb, 0)
    return found


def process_tree(root_pid):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name"
                          " | ConvertTo-Json"], capture_output=True, text=True).stdout
    rows = json.loads(out or "[]")
    pids, changed = {root_pid}, True
    while changed:
        changed = False
        for r in rows:
            if r["ParentProcessId"] in pids and r["ProcessId"] not in pids:
                pids.add(r["ProcessId"])
                changed = True
    names = {r["ProcessId"]: r["Name"] for r in rows if r["ProcessId"] in pids}
    return pids, names


def cdp_pages():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=3) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        log("remote debugging not reachable:", repr(e))
        return []


def cdp_probe(page, label):
    import websocket  # noqa: PLC0415

    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
    n = [0]

    def call(method, params=None):
        n[0] += 1
        ws.send(json.dumps({"id": n[0], "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == n[0]:
                return msg

    expr = ("JSON.stringify({ready: document.readyState, href: location.href,"
            " bridge: typeof window.supraLegal, body: document.body ? document.body.innerText.slice(0, 400) : null,"
            " size: [innerWidth, innerHeight], visibility: document.visibilityState})")
    res = call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    log(f"[{label}] page state:", res.get("result", {}).get("result", {}).get("value"))
    shot = call("Page.captureScreenshot", {"format": "png"})
    data = shot.get("result", {}).get("data")
    if data:
        dump_jpeg(f"{label}-page", base64.b64decode(data))
    else:
        log(f"[{label}] page capture failed:", shot)
    ws.close()


def main():
    exe = install()
    log("installed:", exe)
    appdata = Path(os.environ["APPDATA"]) / "Supra"
    log("profile exists before launch:", appdata.exists())
    elog = ROOT / "electron.log"
    proc = subprocess.Popen([str(exe), f"--remote-debugging-port={PORT}",
                             "--enable-logging=file", f"--log-file={elog}"])
    log("launched pid", proc.pid)
    from PIL import ImageGrab  # noqa: PLC0415

    t0 = time.monotonic()
    for t in (2, 4, 6, 9, 13, 20, 30):
        time.sleep(max(0.0, t - (time.monotonic() - t0)))
        pids, names = process_tree(proc.pid)
        log(f"--- t={t}s alive={proc.poll() is None} processes={sorted(set(names.values()))}")
        for w in app_windows(pids):
            log("   window:", json.dumps(w))
        if t in (6, 13, 30):
            for page in cdp_pages():
                log("   page:", page.get("type"), page.get("title"), page.get("url"))
                if page.get("type") == "page":
                    try:
                        cdp_probe(page, f"t{t}-{Path(page.get('url', '')).name or 'page'}")
                    except Exception as e:  # noqa: BLE001
                        log("   probe failed:", repr(e))
            try:
                dump_jpeg(f"t{t}-desktop", ImageGrab.grab())
            except Exception as e:  # noqa: BLE001
                log("desktop capture failed:", repr(e))
    log("settings.json:", (appdata / "settings.json").read_text("utf-8")[:600]
        if (appdata / "settings.json").exists() else "(none)")
    if elog.exists():
        log("===== electron.log (tail) =====")
        log(elog.read_text("utf-8", "replace")[-6000:])
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
