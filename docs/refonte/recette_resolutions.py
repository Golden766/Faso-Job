"""Recette multi-resolutions via le protocole DevTools de Chrome.

Le viewport est reellement fixe, ce qui active les media queries : c'est
la seule maniere de mesurer la mise en page responsive fidelement.

Ce script est un outil de recette, pas une dependance du projet.

Usage :

    python docs/refonte/recette_resolutions.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = os.environ.get("FASOJOB_BASE", "http://127.0.0.1:8773")
PORT = int(os.environ.get("FASOJOB_CDP_PORT", "9222"))

PAGES = [
    ("accueil", "/"),
    ("catalogue", "/catalogue/"),
    ("fiche-offre", "/offre/secretaire-caissiere/"),
    ("methode", "/comment-ca-marche/"),
    ("proposer", "/proposer-une-annonce/"),
    ("signaler", "/signaler-une-arnaque/"),
]

WIDTHS = [360, 390, 768, 1024, 1280]

MEASURE = """
(() => {
  const doc = document.documentElement;
  const vw = doc.clientWidth;
  const bad = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right > vw + 1) {
      const cls = (typeof el.className === 'string') ? el.className : '';
      bad.push(el.tagName + '.' + cls.slice(0, 50) + ' right=' + Math.round(r.right));
    }
  });
  return {
    vw: vw,
    scrollW: doc.scrollWidth,
    overflow: doc.scrollWidth > vw + 1,
    bad: bad.slice(0, 10)
  };
})()
"""


def start_chrome():
    profile = os.path.join(
        os.environ.get("TEMP", "."), "fasojob-chrome-profile-recette"
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
                targets = json.loads(response.read().decode("utf-8"))
                for target in targets:
                    if target.get("type") == "page":
                        return process, target["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    return process, None


class DevTools:
    """Client minimal du protocole DevTools."""

    def __init__(self, url):
        import websocket

        self.socket = websocket.create_connection(url, timeout=45)
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
        time.sleep(1.2)

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

    def evaluate(self, expression):
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        return result.get("result", {}).get("value")

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass


def main():
    process, socket_url = start_chrome()
    if not socket_url:
        process.terminate()
        print("Chrome headless indisponible.")
        return 1

    client = DevTools(socket_url)
    client.send("Page.enable")
    client.send("Runtime.enable")
    client.disable_cache()

    problems = []
    print()
    print("=== Debordement horizontal par resolution ===")
    print()

    for name, path in PAGES:
        url = BASE + path
        client.navigate(url)
        line = []
        for width in WIDTHS:
            client.set_viewport(width, 900)
            time.sleep(0.35)
            result = client.evaluate(MEASURE)
            if result is None:
                line.append("%d:?" % width)
                continue
            if result["overflow"]:
                problems.append((name, width, result["bad"]))
                line.append("%d:DEBORDE" % width)
            else:
                line.append("%d:ok" % width)
        print("  %-14s %s" % (name, "  ".join(line)))

    print()
    if problems:
        print("DEBORDEMENTS DETECTES :")
        for name, width, bad in problems:
            print("  %s a %d px :" % (name, width))
            for item in bad[:6]:
                print("      %s" % item)
        client.close()
        process.terminate()
        return 1

    print("Aucun debordement horizontal sur les %d pages x %d resolutions."
          % (len(PAGES), len(WIDTHS)))
    client.close()
    process.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
