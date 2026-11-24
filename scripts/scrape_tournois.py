#!/usr/bin/env python3
"""
Robot automatique TennisTrack (Clamart - 45 min - 15/16 ans)
Tourne gratuitement chaque matin via GitHub Actions.
Scrape les annuaires publics de tournois FFT (lastmatch.fr & 123tennis-padel.fr),
filtre les tournois de tennis <= 45 min de Clamart pour 15/16 ans (et 17/18),
met à jour tournois.json et peut envoyer une notification push iPhone via ntfy.sh.
"""

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tournois.json")
MAX_MINS = 45

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TennisTrackBot/1.0; +https://github.com/)"
}

# Temps de trajet estimés en voiture depuis Clamart (92140)
CITIES_MIN = {
    "clamart": 5, "chatillon": 7, "meudon": 8, "fontenay-aux-roses": 8,
    "le plessis-robinson": 9, "plessis-robinson": 9, "vanves": 10,
    "issy-les-moulineaux": 10, "malakoff": 10, "sceaux": 11, "bagneux": 12,
    "chatenay-malabry": 12, "bourg-la-reine": 13, "montrouge": 13,
    "antony": 14, "velizy": 14, "velizy-villacoublay": 14, "boulogne-billancourt": 15,
    "boulogne": 15, "sevres": 15, "chaville": 15, "cachan": 16, "arcueil": 16,
    "verrieres-le-buisson": 16, "bièvres": 16, "bievres": 16,
    "l hay-les-roses": 17, "hay-les-roses": 17, "fresnes": 17, "gentilly": 17,
    "villejuif": 18, "viroflay": 18, "ville-d avray": 18, "wissous": 18,
    "chevilly-larue": 18, "rungis": 18, "jouy-en-josas": 18, "massy": 20,
    "palaiseau": 20, "versailles": 20, "saint-cloud": 20, "marnes-la-coquette": 20,
    "thiais": 20, "vitry-sur-seine": 21, "ivry-sur-seine": 21, "charenton": 22,
    "athis-mons": 22, "garches": 22, "orly": 22, "vaucresson": 22, "le chesnay": 22,
    "suresnes": 23, "alfortville": 23, "choisy-le-roi": 23, "paray-vieille-poste": 23,
    "rueil-malmaison": 25, "puteaux": 25, "neuilly-sur-seine": 25, "levallois": 25,
    "clichy": 25, "nanterre": 26, "creteil": 26, "maisons-alfort": 26,
    "courbevoie": 27, "bois-colombes": 27, "la garenne-colombes": 27,
    "asnieres": 28, "chatou": 28, "joinville": 28, "vincennes": 28, "saint-mande": 28,
    "chilly-mazarin": 25, "longjumeau": 25, "savigny-sur-orge": 26, "juvisy": 26,
    "colombes": 30, "croissy-sur-seine": 30, "le vesinet": 30, "nogent-sur-marne": 30,
    "villeneuve-saint-georges": 30, "fontenay-sous-bois": 30, "champigny": 30,
    "saint-maur": 32, "saint-maur-des-fosses": 32, "houilles": 33, "montreuil": 32,
    "sucy-en-brie": 34, "bonneuil-sur-marne": 32, "ormesson": 35, "rosny-sous-bois": 35,
    "saint-germain-en-laye": 35, "marly-le-roi": 30, "louveciennes": 28,
    "gif-sur-yvette": 28, "orsay": 24, "bures-sur-yvette": 25, "les ulis": 26,
    "yerres": 35, "brunoy": 36, "montgeron": 34, "vigneux-sur-seine": 33,
    "villennes-sur-seine": 38, "poissy": 38, "conflans": 42, "les mureaux": 42,
    "paris 15": 16, "paris 14": 17, "paris 16": 20, "paris 13": 20, "paris 12": 28,
    "paris 7": 22, "paris 6": 22, "paris 5": 22, "paris 17": 26, "paris": 24,
}

MONTHS_FR = {
    "jan": "01", "janv": "01", "janvier": "01",
    "fev": "02", "fevr": "02", "fevrier": "02",
    "mar": "03", "mars": "03",
    "avr": "04", "avril": "04",
    "mai": "05",
    "juin": "06",
    "juil": "07", "juillet": "07",
    "aou": "08", "aout": "08",
    "sep": "09", "sept": "09", "septembre": "09",
    "oct": "10", "octobre": "10",
    "nov": "11", "novembre": "11",
    "dec": "12", "decembre": "12",
}

SOURCES = [
    ("lastmatch", "https://lastmatch.fr/tournois-tennis/departement/hauts-de-seine/"),
    ("lastmatch", "https://lastmatch.fr/tournois-tennis/departement/val-de-marne/"),
    ("lastmatch", "https://lastmatch.fr/tournois-tennis/departement/yvelines/"),
    ("lastmatch", "https://lastmatch.fr/tournois-tennis/departement/essonne/"),
    ("lastmatch", "https://lastmatch.fr/tournois-tennis/departement/paris/"),
    ("123tennis", "https://www.123tennis-padel.fr/hauts-de-seine-92/"),
    ("123tennis", "https://www.123tennis-padel.fr/val-de-marne-94/"),
    ("123tennis", "https://www.123tennis-padel.fr/yvelines-78/"),
    ("123tennis", "https://www.123tennis-padel.fr/essonne-91/"),
]


def norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", (text or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9/ -]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def find_city_and_mins(text: str):
    n = norm(text)
    for city, mins in sorted(CITIES_MIN.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(city)}\b", n):
            return city.title(), mins
    return None, None


def extract_dates(text: str):
    # Format DD/MM/YYYY
    slash = re.findall(r"\b(\d{1,2})/(\d{1,2})/(202\d)\b", text)
    if slash:
        iso = [f"{y}-{int(m):02d}-{int(d):02d}" for d, m, y in slash]
        return iso[0], iso[1] if len(iso) > 1 else iso[0]

    # Format "19 déc 2026"
    n = norm(text)
    words = re.findall(r"\b(\d{1,2})\s+([a-z]{3,9})\.?\s+(202\d)\b", n)
    iso = []
    for d, m, y in words:
        mm = MONTHS_FR.get(m[:4]) or MONTHS_FR.get(m[:3]) or MONTHS_FR.get(m)
        if mm:
            iso.append(f"{y}-{mm}-{int(d):02d}")
    if iso:
        return iso[0], iso[1] if len(iso) > 1 else iso[0]
    return None, None


def is_relevant_tennis(text: str):
    n = norm(text)
    # Exclure padel, beach tennis, pickleball, vétérans +35/+45, femmes uniquement
    if any(bad in n for bad in ["padel", "beach", "pickleball", "p100", "p250", "p500", "p1000", "dames uniquement", "filles uniquement", "+35", "+45", "+55"]):
        return False, None
    # Catégories ciblées : 15/16 ans en priorité, ou 11/18 / jeunes / 17/18
    if any(k in n for k in ["15/16", "15-16", "11/18", "11-18", "11/16", "11-16", "open jeunes", "tournoi jeunes", "gpj", "jeune"]):
        return True, "15/16"
    if any(k in n for k in ["17/18", "17-18"]):
        return True, "17/18 (surcl.)"
    return False, None


def detect_surface(text: str) -> str:
    n = norm(text)
    if "terre battue" in n or "terre" in n:
        return "Terre battue"
    if "resine" in n or "greenset" in n:
        return "Résine"
    if "moquette" in n:
        return "Moquette"
    if "gazon" in n:
        return "Gazon synth."
    return "Dur / Résine"


def make_id(name: str, start: str) -> str:
    h = hashlib.md5(f"{norm(name)}|{start}".encode("utf-8")).hexdigest()[:10]
    return f"auto_{h}"


def scrape_source(kind: str, url: str):
    found = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"[WARN] {url} -> HTTP {resp.status_code}")
            return found
    except Exception as exc:
        print(f"[WARN] Erreur réseau {url}: {exc}")
        return found

    soup = BeautifulSoup(resp.text, "html.parser")
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if kind == "lastmatch" and "/tournois-tennis/" not in href:
            continue
        if kind == "123tennis" and not re.search(r"/(hauts-de-seine-92|val-de-marne-94|yvelines-78|essonne-91|paris-75)/[^/]+/[^/]+", href):
            continue

        card = a.parent if a.parent and len(a.parent.get_text(" ", strip=True)) < 500 else a
        block_text = card.get_text(" ", strip=True)
        title = a.get_text(" ", strip=True)
        if len(title) < 6 or len(title) > 120:
            continue

        ok, cat = is_relevant_tennis(f"{title} {block_text}")
        if not ok:
            continue

        city, mins = find_city_and_mins(f"{title} {block_text} {href}")
        if not city or mins is None or mins > MAX_MINS:
            continue

        start, end = extract_dates(block_text)
        if not start or end < today_iso:
            continue

        full_url = urljoin(url, href)
        fmt = "TMC" if "tmc" in norm(f"{title} {block_text}") else "Open"
        found.append({
            "id": make_id(title, start),
            "name": title[:90],
            "club": city,
            "city": city,
            "mins": mins,
            "start": start,
            "end": end,
            "month": start[:7],
            "cat": cat,
            "surface": detect_surface(block_text),
            "format": fmt,
            "url": full_url,
            "notes": f"Ajouté automatiquement par le robot ({kind})",
        })
    return found


def send_ntfy(new_items):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic or not new_items:
        return
    lines = [f"• {t['name']} ({t['city']}, {t['start']})" for t in new_items[:6]]
    body = "\n".join(lines)
    if len(new_items) > 6:
        body += f"\n... et {len(new_items) - 6} autre(s) dans TennisTrack."
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=body.encode("utf-8"),
            headers={
                "Title": f"TennisTrack : {len(new_items)} nouveau(x) tournoi(s) 15/16 !",
                "Tags": "tennis,trophy",
            },
            timeout=15,
        )
        print(f"[INFO] Notification ntfy envoyée ({len(new_items)} tournois).")
    except Exception as exc:
        print(f"[WARN] Échec notification ntfy : {exc}")


def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("tournois", [])
    known_keys = {
        (norm(t.get("name", "")), t.get("start", "")) for t in existing
    }
    known_urls = {t.get("url", "").rstrip("/") for t in existing if t.get("url")}

    added = []
    for kind, url in SOURCES:
        for item in scrape_source(kind, url):
            key = (norm(item["name"]), item["start"])
            u = item["url"].rstrip("/")
            if key in known_keys or u in known_urls:
                continue
            existing.append(item)
            known_keys.add(key)
            known_urls.add(u)
            added.append(item)

    existing.sort(key=lambda t: (t.get("start", ""), t.get("mins", 99)))
    now = datetime.now(timezone.utc)
    months_lbl = ["jan.", "fév.", "mar.", "avr.", "mai", "juin", "juil.", "août", "sep.", "oct.", "nov.", "déc."]
    data["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    data["updated_label"] = f"{now.day} {months_lbl[now.month - 1]} {now.year}"
    data["tournois"] = existing

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=
