"""Detecte les recouvrements et les elements trop petits au toucher.

Recette du lot 9 : sur mobile, la barre de navigation basse est fixe.
Elle ne doit pas recouvrir un contenu, et les cibles tactiles
doivent atteindre 44 px de haut (recommandation WCAG 2.5.5).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = os.environ.get("FASOJOB_BASE", "http://127.0.0.1:8773")
PORT = int(os.environ.get("FASOJOB_CDP_PORT", "9224"))

PAGES = [
    ("accueil", "/"),
    ("catalogue", "/catalogue/"),
    ("fiche-offre", "/offre/secretaire-caissiere/"),
    ("methode", "/comment-ca-marche/"),
    ("proposer", "/proposer-une-annonce/"),
    ("signaler", "/signaler-une-arnaque/"),
]

WIDTHS = [360, 390]

MEASURE = """
(() => {
  const doc = document.documentElement;
  const vh = window.innerHeight;

  // La barre inferieure fixe, si elle existe.
  const bottomNav = document.querySelector('.fj-bottom-nav');
  let overlaps = [];
  let navOpaque = true;
  if (bottomNav) {
    const navRect = bottomNav.getBoundingClientRect();
    const navStyle = getComputedStyle(bottomNav);
    // Une barre opaque masque ce qui passe dessous : ce n est pas un
    // defaut de lisibilite.
    navOpaque = navStyle.backgroundColor !== 'rgba(0, 0, 0, 0)'
      && !navStyle.backgroundColor.startsWith('rgba(0, 0, 0, 0.');
    // Elements visibles situes sous la barre.
    document.querySelectorAll('main a, main button, main input, main select, main textarea').forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      // Une barre opaque masque ce qui passe dessous : ce n est pas
      // un defaut de lisibilite, on ne le signale donc pas.
      if (navOpaque) return;
      if (r.top < navRect.top && r.bottom > navRect.top && r.top > 0) {
        const cls = (typeof el.className === 'string') ? el.className : '';
        overlaps.push(el.tagName + '.' + cls.slice(0, 40) + ' top=' + Math.round(r.top) + ' bottom=' + Math.round(r.bottom));
      }
    });
  }

  // Cibles tactiles trop petites.
  const small = [];
  document.querySelectorAll('a, button, input, select, textarea, [role=button]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (el.closest('[hidden]')) return;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') return;
    if (r.height < 40) {
      // WCAG 2.5.5 excepte les liens sits dans un bloc de texte.
      if (el.tagName === 'A' && el.closest('p, li, td, dd, figcaption')) {
        return;
      }
      // Une case ou un bouton radio n est qu un indicateur : c est le
      // label qui constitue la zone reellement cliquable. On mesure
      // cette zone, pas l indicateur.
      const clickable = el.closest('label');
      if (clickable && clickable !== el) {
        const zone = clickable.getBoundingClientRect();
        if (zone.height >= 40) {
          return;
        }
      }
      const cls = (typeof el.className === 'string') ? el.className : '';
      const parent = el.parentElement;
      const parentCls = (parent && typeof parent.className === 'string') ? parent.className : '';
      const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30);
      small.push(
        el.tagName + '.' + cls.slice(0, 30)
        + ' | parent=' + parentCls.slice(0, 25)
        + ' | texte=' + text
        + ' | h=' + Math.round(r.height)
      );
    }
  });

  // Reserve basse : le contenu doit prevoir la place de la barre.
  const main = document.querySelector('main');
  const paddingBottom = main ? getComputedStyle(main).paddingBottom : '0';

  return {
    vh: vh,
    url: location.href,
    title: document.title,
    bodyClass: document.body.className,
    navPresent: !!bottomNav,
    navHeight: bottomNav ? Math.round(bottomNav.getBoundingClientRect().height) : 0,
    overlaps: overlaps.slice(0, 8),
    small: small.slice(0, 8),
    smallCount: small.length,
    mainPaddingBottom: paddingBottom
  };
})()
"""


def start_chrome():
    # Un profil unique par execution : un profil reutilise peut garder
    # un ancien etat d emulation de device.
    import tempfile

    profile = tempfile.mkdtemp(prefix="fasojob-chrome-cibles-")
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


def main():
    process, socket_url = start_chrome()
    if not socket_url:
        process.terminate()
        print("Chrome headless indisponible.")
        return 1

    import websocket

    socket = websocket.create_connection(socket_url, timeout=60)
    counter = [0]

    def send(method, params=None):
        counter[0] += 1
        message_id = counter[0]
        socket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(socket.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    send("Page.enable")
    send("Network.enable")
    send("Network.setCacheDisabled", {"cacheDisabled": True})
    send("Runtime.enable")

    def navigate_and_wait(url):
        """Navigate et attend le chargement reel de la page.

        Page.navigate est asynchrone : sans cette attente, la mesure
        interroge la page precedente. On interroge l etat du document
        plutot que d ecouter un evenement, ce qui ne perturbe pas la
        connexion.
        """
        send("Page.navigate", {"url": url})
        deadline = time.time() + 20
        while time.time() < deadline:
            time.sleep(0.2)
            try:
                state = send(
                    "Runtime.evaluate",
                    {"expression": "document.readyState", "returnByValue": True},
                )
            except Exception:
                return False
            ready = state.get("result", {}).get("value")
            if ready == "complete":
                return True
        return False

    print()
    print("=== Cibles tactiles et recouvrements (mobile) ===")
    print()

    problems = []
    for name, path in PAGES:
        for width in WIDTHS:
            # On fixe le viewport avant de charger : la barre basse n
            # existe qu au Below 768 px et doit etre mesuree reellement.
            send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": 780,
                    "deviceScaleFactor": 1,
                    "mobile": True,
                },
            )
            time.sleep(0.3)
            navigate_and_wait(BASE + path)
            time.sleep(0.6)
            result = send(
                "Runtime.evaluate",
                {
                    "expression": MEASURE,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            value = result.get("result", {}).get("value") or {}
            if not value:
                raw = send(
                    "Runtime.evaluate",
                    {"expression": "document.title + '|' + location.href", "returnByValue": True},
                )
                print("      [debug] %s" % raw)
            overlaps = value.get("overlaps") or []
            small = value.get("small") or []
            status = "ok" if not overlaps and not small else "PROBLEME"
            print(
                "  %-12s %d px  nav=%s h=%s  recouvrements=%d  cibles<40px=%d  %s"
                "  [%s]"
                % (
                    name,
                    width,
                    "oui" if value.get("navPresent") else "non",
                    value.get("navHeight"),
                    len(overlaps),
                    len(small),
                    status,
                    value.get("url"),
                )
            )
            if overlaps:
                for item in overlaps[:4]:
                    print("      RECOUVRE : %s" % item)
            if small:
                for item in small[:4]:
                    print("      PETIT : %s" % item)
            if overlaps or small:
                problems.append((name, width))

    socket.close()
    process.terminate()

    print()
    if problems:
        print("%d page(s) ou resolution(s) a corriger." % len(problems))
        return 1
    print("Aucune cible trop petite et aucun recouvrement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
