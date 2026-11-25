"""
Suivi des tournois de tennis (15/16 ans) autour de Clamart.

Utilisation :
  python scrape_tournois.py          -> met à jour tournois.json
  python scrape_tournois.py --setup  -> crée le workflow GitHub (mise à jour mensuelle)
"""
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------- Réglages à modifier ----------
DATA_FILE = "tournois.json"
GEO_CACHE_FILE = "geocache.json"
DEPTS = ["92", "75", "94", "78", "91"]
HOME = (48.8017, 2.2663)   # Clamart (lat, lon)
MAX_KM = 35                # ~45 min en voiture (à vol d'oiseau)
MONTHS_AHEAD = 12
PAUSE_SECONDS = 1.0
# -----------------------------------------

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TennisTrackBot/4.0)"}

# Catégories qui incluent les 15/16 ans
INCLUDE_KW = ["15/16", "15-16", "11/18", "13/18", "15/18", "15/17"]
EXCLUDE_KW = ["+35", "+45", "+55", "+65", "senior+", "vétéran", "veteran",
              "dames uniquement", "femmes uniquement"]


# ---------- Utilitaires ----------
def load_existing():
    if not os.path.exists(DATA_FILE):
        return {"last_updated": "", "tournois": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"last_updated": "", "tournois": data}
    return data


def load_geocache():
    if os.path.exists(GEO_CACHE_FILE):
        with open(GEO_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_geocache(cache):
    with open(GEO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def parse_date_fr(text):
    m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d/%m/%Y")
    except ValueError:
        return None


def all_dates(text):
    out = []
    for d in re.findall(r"\d{2}/\d{2}/\d{4}", text):
        try:
            out.append(datetime.strptime(d, "%d/%m/%Y"))
        except ValueError:
            pass
    return out


def is_valid_category(text):
    t = text.lower()
    if any(bad in t for bad in EXCLUDE_KW):
        return False
    return any(ok in t for ok in INCLUDE_KW)


def is_upcoming(dates):
    """True si le tournoi n'est pas passé et est dans la fenêtre voulue."""
    if not dates:
        return True  # date inconnue : on garde, marqué « À vérifier »
    now = datetime.now()
    end = max(dates)
    start = min(dates)
    return end >= now - timedelta(days=1) and start <= now + timedelta(days=30 * MONTHS_AHEAD)


# ---------- Distance ----------
def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def extract_city(text):
    """Cherche « 92140 CLAMART » ou « CLAMART (92) » dans le texte. Retourne (ville, cp) ou (None, None)."""
    m = re.search(r"\b(\d{5})\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ' \-]{2,40})", text)
    if m:
        return m.group(2).strip(), m.group(1)
    m = re.search(r"([A-ZÀ-Ý][A-Za-zÀ-ÿ' \-]{2,40})\s*\((\d{2})\)", text)
    if m:
        return m.group(1).strip(), None
    return None, None


def geocode(city, postcode, cache):
    key = f"{city}|{postcode or ''}"
    if key in cache:
        return cache[key]
    params = {"q": city, "type": "municipality", "limit": 1}
    if postcode:
        params["postcode"] = postcode
    coords = None
    try:
        r = requests.get("https://api-adresse.data.gouv.fr/search/", params=params, timeout=10)
        feats = r.json().get("features", [])
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"]
            coords = [lat, lon]
    except Exception as e:
        print(f"Géocodage impossible pour {city}: {e}")
        return None  # pas mis en cache : on réessaiera
    cache[key] = coords
    return coords


# ---------- Récupération ----------
def scrape_123tennis(geocache):
    found = []
    seen_urls = set()
    pages_ok = 0

    for dept in DEPTS:
        for page in range(1, 11):
            url = f"https://www.123tennis.fr/tournois-tennis-departement-{dept}.html?page={page}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                time.sleep(PAUSE_SECONDS)
                if r.status_code != 200:
                    break
                pages_ok += 1
                soup = BeautifulSoup(r.text, "html.parser")
                # Une seule famille de sélecteurs pour éviter les doublons
                cards = soup.select("tr") or soup.select(".tournoi, .card, article")
                if not cards:
                    break

                page_added = 0
                for c in cards:
                    txt = " ".join(c.get_text(" ", strip=True).split())
                    if len(txt) < 15 or not is_valid_category(txt):
                        continue
                    dates = all_dates(txt)
                    if not is_upcoming(dates):
                        continue

                    link_tag = c.find("a", href=True)
                    link = urljoin(url, link_tag["href"]) if link_tag else url
                    if link != url and link in seen_urls:
                        continue
                    seen_urls.add(link)

                    city, cp = extract_city(txt)
                    km = None
                    if city:
                        coords = geocode(city, cp, geocache)
                        if coords:
                            km = round(haversine_km(HOME, coords), 1)
                            if km > MAX_KM:
                                continue  # trop loin

                    title = link_tag.get_text(strip=True) if link_tag else txt[:60]
                    found.append({
                        "nom": title[:80],
                        "club": f"Département {dept}",
                        "ville": city or f"({dept})",
                        "distance_km": km,
                        "dates": " - ".join(d.strftime("%d/%m/%Y") for d in dates[:2]) or "À vérifier",
                        "date_fin": max(dates).strftime("%Y-%m-%d") if dates else "",
                        "surface": "À vérifier",
                        "lien": link,
                    })
                    page_added += 1

                if page_added == 0 and page > 2:
                    break
            except Exception as e:
                print(f"Erreur sur {url}: {e}")
                continue
    return found, pages_ok


# ---------- Notifications ----------
def send_ntfy(title, message):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title.encode("utf-8")},
            timeout=10,
        )
    except Exception as e:
        print(f"ntfy: {e}")


def notify_new(new_items):
    if not new_items:
        return
    lines = []
    for t in new_items[:6]:
        dist = f", {t['distance_km']} km" if t.get("distance_km") is not None else ""
        lines.append(f"• {t['nom']} ({t['dates']}{dist})")
    if len(new_items) > 6:
        lines.append(f"... et {len(new_items) - 6} autre(s) dans TennisTrack")
    send_ntfy("TennisTrack - Nouveaux tournois !",
              f"{len(new_items)} nouveau(x) tournoi(s) :\n" + "\n".join(lines))


# ---------- Workflow GitHub Actions (créé avec : python scrape_tournois.py --setup) ----------
WORKFLOW_PATH = ".github/workflows/update-tournois.yml"
WORKFLOW_YML = """name: Mise à jour mensuelle des tournois

on:
  schedule:
    - cron: "0 6 1 * *"   # le 1er de chaque mois à 6h UTC
  workflow_dispatch:       # bouton pour lancer à la main

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Installer les dépendances
        run: pip install requests beautifulsoup4

      - name: Lancer le script
        env:
          NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
        run: python scrape_tournois.py

      - name: Enregistrer les changements
        run: |
          git config user.name "tennistrack-bot"
          git config user.email "bot@users.noreply.github.com"
          git add tournois.json geocache.json
          git diff --staged --quiet || git commit -m "Mise à jour des tournois"
          git push
"""


def setup_workflow():
    os.makedirs(os.path.dirname(WORKFLOW_PATH), exist_ok=True)
    with open(WORKFLOW_PATH, "w", encoding="utf-8") as f:
        f.write(WORKFLOW_YML)
    print(f"Workflow créé : {WORKFLOW_PATH}")
    print("Ajoute maintenant le secret NTFY_TOPIC dans les réglages du dépôt GitHub.")


# ---------- Programme principal ----------
def main():
    if "--setup" in sys.argv:
        setup_workflow()
        return

    data = load_existing()
    geocache = load_geocache()

    scraped, pages_ok = scrape_123tennis(geocache)
    save_geocache(geocache)

    # Alerte si le site a probablement changé de structure
    if pages_ok == 0 or not scraped:
        msg = f"Aucun tournoi récupéré ({pages_ok} page(s) lues). Le site a peut-être changé."
        print(msg)
        send_ntfy("TennisTrack - Problème de mise à jour", msg)
        sys.exit(1)

    # Purge des tournois passés
    today = datetime.now().strftime("%Y-%m-%d")
    existing = [t for t in data.get("tournois", [])
                if not t.get("date_fin") or t["date_fin"] >= today]

    def key(t):
        return t.get("lien") or (t.get("nom", "").lower().strip(), t.get("dates", ""))

    seen = {key(t) for t in existing}
    added = []
    for item in scraped:
        if key(item) not in seen:
            seen.add(key(item))
            existing.append(item)
            added.append(item)

    data["tournois"] = existing
    data["last_updated"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    notify_new(added)
    print(f"Terminé : {len(added)} nouveau(x). Total : {len(existing)}.")


if __name__ == "__main__":
    main()
