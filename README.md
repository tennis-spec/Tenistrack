# TennisTrack 15/16 (Leny) — Kit Gratuit 100 % Automatique

Ce kit contient :
- `index.html`, `manifest.json`, `icon-180.png` : ton application iPhone plein écran (PWA), connectée automatiquement au fichier `tournois.json`.
- `tournois.json` : les 22 tournois déjà vérifiés (Décembre 2026 → Février 2027, ≤ 45 min de Clamart).
- `scripts/scrape_tournois.py` : le robot Python qui cherche automatiquement de nouveaux tournois autour de Clamart (92, 94, 78, 91, 75) et met à jour `tournois.json`.
- `.github/workflows/update-tournois.yml` : la tâche GitHub Actions gratuite qui lance le robot chaque matin à 8h/9h sans que tu n'aies rien à faire.

## Installation gratuite en 5 minutes (1 seule fois)

1. **Crée un compte gratuit sur [github.com](https://github.com)**.
2. Clique sur **New** (Nouveau dépôt), appelle-le `tennistrack`, laisse-le en **Public** et clique sur **Create repository**.
3. **Dézippe** ce fichier ZIP sur ton ordinateur (ou iPhone) puis dépose **tous les fichiers et dossiers** (y compris le dossier caché `.github/workflows/update-tournois.yml` et `scripts/scrape_tournois.py`) dans ton dépôt GitHub (**uploading an existing file** → **Commit changes**).
   - *Astuce :* si tu fais l'upload depuis le navigateur et que le dossier `.github` n'est pas visible, clique sur **Add file → Create new file**, tape `.github/workflows/update-tournois.yml` comme nom et colle le contenu du fichier.
4. **Active le site web gratuit (GitHub Pages) :**
   - Va dans **Settings → Pages**.
   - Dans *Branch*, choisis **main** puis clique sur **Save**.
   - Au bout d'1 minute, ton lien d'application apparaît : `https://TON-PSEUDO.github.io/tennistrack/`
5. **Active le robot automatique :**
   - Va dans **Settings → Actions → General → Workflow permissions**, coche **Read and write permissions** puis **Save**.
   - Va dans l'onglet **Actions**, clique sur **Mise a jour automatique tournois TennisTrack** → **Run workflow** pour le tester immédiatement.
6. **Installe l'application sur ton iPhone :**
   - Ouvre `https://TON-PSEUDO.github.io/tennistrack/` dans **Safari**.
   - Appuie sur **Partager** → **Sur l'écran d'accueil** → **Ajouter**.

## Bonus gratuit : recevoir une notification push iPhone dès que le robot trouve un nouveau tournoi

1. Télécharge l'application gratuite **ntfy** sur l'App Store.
2. Ouvre **ntfy**, appuie sur **+** et abonne-toi à un nom de canal secret (exemple : `tennistrack-leny-clamart-92140`).
3. Sur GitHub, va dans **Settings → Secrets and variables → Actions → New repository secret** :
   - Name : `NTFY_TOPIC`
   - Secret : `tennistrack-leny-clamart-92140` (le même nom de canal)
4. Dès que le robot ajoute un nouveau tournoi le matin, tu reçois automatiquement une notification sur ton iPhone !
