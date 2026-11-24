import json
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

DATA_FILE = "tournois.json"
DEPTS = ["92", "75", "78", "91", "94"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TennisTrackBot/3.0)"}

# Mots-clés pour repérer les tournois 15/16 ans ou Jeunes
INCLUDE_KW = ["15/16", "15-16", "11/18", "13/18", "15/18", "15/17", "jeune", "junior", "gpj", "galaxie"]
EXCLUDE_KW = ["+35", "+45", "+55", "+65", "senior+", "vétéran", "veteran", "dames uniquement", "femmes uniquement"]


def load_existing():
    if not os.path.exists(DATA_FILE):
        return {"last_updated": "", "tournois": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"last_updated": "", "tournois": data}
    return data


def is_valid_category(text):
    t = text.lower()
    if any(bad in t for bad in EXCLUDE_KW):
        return False
    return any(ok in t for ok in INCLUDE_KW)


def parse_date_fr(text):
    m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d/%m/%Y")
    except ValueError:
        return None


def is_upcoming_year(text):
    """Accepte tous les tournois à venir sur les 12 prochains mois (tous les mois de l'année)."""
    dt = parse_date_fr(text)
    if not dt:
        return True
    now = datetime.now()
    return (now - timedelta(days=2)) <= dt <= (now + timedelta(days=365))


def scrape_123tennis():
    found = []
    seen_urls = set()

    for dept in DEPTS:
        for page in range(1, 11):  # Parcourt jusqu'à 10 pages par département
            url = f"https://www.123tennis.fr/tournois-tennis-departement-{dept}.html?page={page}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.select("tr, .tournoi, .card, article")
                if not cards:
                    break

                page_added = 0
                for c in cards:
                    txt = " ".join(c.get_text(" ", strip=True).split())
                    if len(txt) < 15 or not is_valid_category(txt) or not is_upcoming_year(txt):
                        continue

                    link_tag = c.find("a", href=True)
                    link = urljoin(url, link_tag["href"]) if link_tag else url
                    if link in seen_urls and link != url:
                        continue
                    seen_urls.add(link)

                    title = link_tag.get_text(strip=True) if link_tag else txt[:60]
                    date_match = re.findall(r"\d{2}/\d{2}/\d{4}", txt)
                    dates = " - ".join(date_match[:2]) if date_match else "À vérifier"

                    found.append({
                        "nom": title[:80],
                        "club": f"Département {dept}",
                        "ville": f"({dept})",
                        "dates": dates,
                        "surface": "À vérifier",
                        "lien": link,
                    })
                    page_added += 1

                if page_added == 0 and page > 2:
                    break
            except Exception:
                continue
    return found


def send_ntfy(new_items):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic or not new_items:
        return
    lines = [f"• {t['nom']} ({t['dates']})" for t in new_items[:6]]
    if len(new_items) > 6:
        lines.append(f"... et {len(new_items) - 6} autre(s) dans TennisTrack")
    msg = f"{len(new_items)} nouveau(x) tournoi(s) détecté(s) :\n" + "\n".join(lines)
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=msg.encode("utf-8"),
            headers={"Title": "TennisTrack - Nouveaux tournois !"},
            timeout=10,
        )
    except Exception:
        pass


def main():
    data = load_existing()
    existing = data.get("tournois", [])
    seen = {(t.get("nom", "").lower().strip(), t.get("dates", "").strip()) for t in existing}

    scraped = scrape_123tennis()
    added = []
    for item in scraped:
        key = (item["nom"].lower().strip(), item["dates"].strip())
        if key not in seen:
            seen.add(key)
            existing.append(item)
            added.append(item)

    data["tournois"] = existing
    data["last_updated"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if added:
        send_ntfy(added)
    print(f"Terminé : {len(added)} nouveau(x) tournoi(s) ajouté(s). Total : {len(existing)}.")


if __name__ == "__main__":
    main()
