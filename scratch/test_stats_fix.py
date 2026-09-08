import subprocess
import time
import json
import urllib.request
import os
import websocket
import base64
import shutil

USER_DATA_DIR = os.path.abspath(r"C:\Users\Dell\.gemini\antigravity-ide\brain\7283857d-4005-4570-8b4a-ec45b3fa56cf\scratch\chrome_stats_fix_profile")
if os.path.exists(USER_DATA_DIR):
    try:
        shutil.rmtree(USER_DATA_DIR)
    except Exception:
        pass

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
chrome_cmd = [
    CHROME_PATH,
    "--headless=new",
    "--remote-debugging-port=9224",
    "--remote-allow-origins=*",
    "--disable-gpu",
    "--no-sandbox",
    "--window-size=1440,960",
    f"--user-data-dir={USER_DATA_DIR}",
    "about:blank",
]

proc = subprocess.Popen(chrome_cmd)
time.sleep(2)

try:
    with urllib.request.urlopen("http://127.0.0.1:9224/json") as resp:
        targets = json.loads(resp.read().decode())
    
    page_target = [t for t in targets if t.get("type") == "page"][0]
    ws_url = page_target["webSocketDebuggerUrl"]

    ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)
    req_id = [0]

    def send_cmd(method, params=None):
        req_id[0] += 1
        current_id = req_id[0]
        payload = {"id": current_id, "method": method, "params": params or {}}
        ws.send(json.dumps(payload))
        while True:
            raw = ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == current_id:
                return msg.get("result", {})

    send_cmd("Runtime.enable")
    send_cmd("Page.enable")

    # Navigate
    send_cmd("Page.navigate", {"url": "http://localhost:8000"})
    time.sleep(2.5)

    res = send_cmd("Page.captureScreenshot", {"format": "png"})
    with open(r"C:\Users\Dell\.gemini\antigravity-ide\brain\7283857d-4005-4570-8b4a-ec45b3fa56cf\stats_cards_fixed.png", "wb") as f:
        f.write(base64.b64decode(res["data"]))
    print("Saved stats_cards_fixed.png")

finally:
    try:
        ws.close()
    except Exception:
        pass
    proc.terminate()
