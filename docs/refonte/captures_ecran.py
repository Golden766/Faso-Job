"""Captures d'ecran aux resolutions cibles du lot 9.

Les captures sont prises via le protocole DevTools : la largeur du viewport
est reellement fixee, contrairement a --window-size qui fixe la fenetre
entiere (barre de titres comprise) et produit des images trop etroites.

Usage :

    python docs/refonte/captures_ecran.py
"""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = os.environ.get("FASOJOB_BASE", "http://127.0.0.1:8773")
PORT = int(os.environ.get("FASOJOB_CDP_PORT", "9223"))
OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "captures",
)

# Ecran et largeur pour chaque resolution cible.
TARGETS = [
    ("mobile-360", 360, 780),
    ("mobile-390", 390, 844),
    ("tablette-768", 768, 1024),
    ("bureau-1024", 1024, 800),
    ("bureau-1280", 1280, 900),
]

PAGES = [
    ("accueil", "/"),
    ("catalogue", "/catalogue/"),
    ("fiche-offre", "/offre/secretaire-caissiere/"),
    ("methode", "/comment-ca-marche/"),
    ("proposer", "/proposer-une-annonce/"),
    ("signaler", "/signaler-une-arnaque/"),
]


def start_chrome():
    profile = os.path.join(
        os.environ.get("TEMP", "."), "fasojob-chrome-captures"
    )
    os.makedirs(profile, exist_ok=True)
    process = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--remote-debugging-port=%d" % PORT,
            "--user-data-dir=%s" % profile,
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:%d/json" % PORT, timeout=2
            ) as response:
                for target in json.loads(response.read().decode("utf-8")):
                    if target.get("type") == "page":
                        return process, target["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    return process, None


class DevTools:
    def __init__(self, url):
        import websocket

        self.socket = websocket.create_connection(url, timeout=60)
        self.counter = 0

    def send(self, method, params=None):
        self.counter += 1
        message_id = self.counter
        self.socket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def disable_cache(self):
        """Desactive le cache : une feuille ancienne fausse les mesures."""
        self.send("Network.enable")
        self.send("Network.setCacheDisabled", {"cacheDisabled": True})

    def navigate(self, url):
        self.send("Page.navigate", {"url": url})
        time.sleep(1.4)

    def set_viewport(self, width, height):
        self.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": width < 768,
            },
        )
        time.sleep(0.4)

    def capture(self, path):
        result = self.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True},
        )
        data = result.get("data")
        if not data:
            return False
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(data))
        return True

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass


def main():
    os.makedirs(OUTPUT, exist_ok=True)
    process, socket_url = start_chrome()
    if not socket_url:
        process.terminate()
        print("Chrome headless indisponible.")
        return 1

    client = DevTools(socket_url)
    client.send("Page.enable")
    client.send("Runtime.enable")
    client.disable_cache()

    written = 0
    for name, path in PAGES:
        for label, width, height in TARGETS:
            # On navigue d'abord, puis on fixe la largeur : fixer le
            # viewport avant le chargement donne une page de largeur nulle.
            client.navigate(BASE + path)
            client.set_viewport(width, height)
            target = os.path.join(OUTPUT, "lot9-%s-%s.png" % (name, label))
            if client.capture(target):
                written += 1
                print("  %s" % os.path.basename(target))

    client.close()
    process.terminate()
    print()
    print("%d captures ecrites dans %s" % (written, OUTPUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
