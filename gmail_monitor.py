#!/usr/bin/env python3
"""
gmail_monitor.py
────────────────
Surveille la boîte Gmail redwanmaatoug@gmail.com et met à jour data.csv
à partir d'emails en langage naturel décrivant des changements d'anesthésistes.

Prérequis
─────────
1. Activer IMAP dans les paramètres Gmail :
   Paramètres → Voir tous les paramètres → Transfert et POP/IMAP → Activer IMAP

2. Créer un mot de passe d'application Google (nécessite la validation en 2 étapes) :
   https://myaccount.google.com/apppasswords
   Choisir : Application = Courrier, Appareil = Autre (nom libre)

3. Remplir le fichier .env (copier .env.example) :
   GMAIL_USER=votre.adresse@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

4. Installer les dépendances :
   pip install rapidfuzz python-dotenv

Usage
─────
  python gmail_monitor.py              # lecture + mise à jour réelle
  python gmail_monitor.py --dry-run   # simulation sans modifier data.csv
"""

import argparse
import csv
import email
import imaplib
import logging
import os
import re
import subprocess
import sys
import unicodedata
from copy import deepcopy
from datetime import datetime
from email.header import decode_header
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rapidfuzz import fuzz, process

# ─── Chargement des variables d'environnement (.env) ─────────────────────────
load_dotenv(Path(__file__).parent / ".env")

# ─── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_FILE = BASE_DIR / "data.csv"
LOG_FILE  = BASE_DIR / "email_processing.log"

# ─── Configuration Gmail ──────────────────────────────────────────────────────
GMAIL_USER     = os.environ.get("GMAIL_USER", "")
# Les mots de passe d'application Google s'écrivent avec des espaces (affichage),
# mais l'API IMAP attend la version sans espaces.
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")

# ─── Configuration GitHub sync ────────────────────────────────────────────────
GIT_AUTO_PUSH = os.environ.get("GIT_AUTO_PUSH", "1").strip().lower() not in {
    "0", "false", "no", "off"
}
GIT_REMOTE = os.environ.get("GIT_REMOTE", "origin").strip() or "origin"
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main").strip() or "main"

# ─── Seuils de confiance ──────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD  = 75   # Score global minimum pour appliquer une modification (/ 100)
AMBIGUITY_GAP         = 8    # Si deux candidats sont à moins de N pts → ambigu
NAME_MATCH_THRESHOLD  = 65   # Score min pour considérer qu'un token ressemble à un nom connu

# ─── Vocabulaire de détection contextuelle ───────────────────────────────────
# Mots signalant qu'un nom est celui À REMPLACER (ancien)
OLD_SIGNALS: frozenset[str] = frozenset({
    "remplacer", "remplace", "remplacez", "enlever", "enleve", "enlevez",
    "retirer", "supprimer", "non", "pas",
})
# Mots signalant qu'un nom est le NOUVEAU médecin
NEW_SIGNALS: frozenset[str] = frozenset({
    "par", "mettre", "mettez", "affecter", "nommer", "anesthesiste", "anesth",
})
# Mots-clés rendant un email pertinent pour l'anesthésie / planning
ANESTHESIA_KEYWORDS: frozenset[str] = frozenset({
    "anesthesiste", "anesthesie", "anesth", "intervention", "operation",
    "remplacer", "remplacement", "modifier", "affecter", "planning",
    "bloc", "chirurgie", "chirurgien", "medecin", "docteur", "dr",
    "enlever", "retirer", "supprimer", "remplacez", "enlevez",
})
# Mots courants à ne pas confondre avec des noms propres
STOPWORDS: frozenset[str] = frozenset({
    "le", "la", "les", "de", "du", "des", "un", "une", "pour", "dans",
    "sur", "avec", "et", "ou", "ce", "se", "ne", "pas", "au", "aux",
    "a", "en", "an", "l", "d", "je", "vous", "nous", "bonjour",
    "cordialement", "merci", "madame", "monsieur", "mme", "mr",
    "date", "operation", "intervention", "planning", "bloc",
    "chirurgie", "clinique", "hopital", "sera", "mettre", "par",
    "remplacer", "enlever", "retirer", "non", "pas", "mois", "jour",
    "annee", "envoi", "objet", "re",
})

# Noms de mois français → numéro
MONTH_MAP: dict[str, int] = {
    "janvier": 1, "jan": 1,
    "fevrier": 2, "fev": 2,
    "mars":    3,
    "avril":   4, "avr": 4,
    "mai":     5,
    "juin":    6, "jui": 6,
    "juillet": 7, "juil": 7,
    "aout":    8, "aou": 8,
    "septembre": 9,  "sep": 9,  "sept": 9,
    "octobre":  10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "dec": 12,
}

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  NORMALISATION TEXTE
# ══════════════════════════════════════════════════════════════════════════════

def normalize(text: str) -> str:
    """Minuscules, sans accents, ponctuation → espace, espaces multiples nettoyés."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_title(name: str) -> str:
    """Supprime le titre Dr / Dr. / Docteur en début de nom."""
    return re.sub(r"^(dr\.?\s*|docteur\s+)", "", name, flags=re.IGNORECASE).strip()


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACTION DE DATES
# ══════════════════════════════════════════════════════════════════════════════

def extract_dates(text: str) -> list[str]:
    """
    Détecte toutes les dates dans le texte (formats variés).
    Retourne une liste de chaînes DD/MM/YYYY sans doublons.
    """
    year_now = datetime.now().year
    found: list[str] = []

    # DD/MM, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    for m in re.finditer(
        r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{4}|\d{2}))?\b",
        text,
    ):
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else year_now
        if len(str(y)) == 2:
            y += 2000
        if 1 <= d <= 31 and 1 <= mo <= 12:
            found.append(f"{d:02d}/{mo:02d}/{y}")

    # "12 avril [2026]" dans le texte normalisé
    norm = normalize(text)
    month_re = "|".join(sorted(MONTH_MAP.keys(), key=len, reverse=True))
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({month_re})\b(?:\s+(\d{{4}}))?", norm):
        d = int(m.group(1))
        mo = MONTH_MAP.get(m.group(2), 0)
        y = int(m.group(3)) if m.group(3) else year_now
        if mo and 1 <= d <= 31:
            found.append(f"{d:02d}/{mo:02d}/{y}")

    return list(dict.fromkeys(found))   # déduplique en conservant l'ordre


# ══════════════════════════════════════════════════════════════════════════════
#  CSV
# ══════════════════════════════════════════════════════════════════════════════

def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  FUZZY MATCHING
# ══════════════════════════════════════════════════════════════════════════════

def fuzzy_best(
    query: str,
    candidates: list[str],
    threshold: int = NAME_MATCH_THRESHOLD,
) -> tuple[Optional[str], int]:
    """
    Retourne (nom_canonique, score) ou (None, 0) si sous le seuil.
    Comparaison après normalisation et suppression du titre Dr/Docteur.
    """
    if not candidates or not query.strip():
        return None, 0

    q_norm = normalize(strip_title(query))
    # Construit un mapping canonical → normalisé pour retrouver la forme originale
    c_map = {c: normalize(strip_title(c)) for c in candidates}

    result = process.extractOne(
        q_norm, list(c_map.values()), scorer=fuzz.token_sort_ratio
    )
    if result is None or result[1] < threshold:
        return None, 0

    # Retrouve le nom canonique correspondant à la valeur normalisée matchée
    canonical = next(k for k, v in c_map.items() if v == result[0])
    return canonical, result[1]


def is_ambiguous(
    query: str, candidates: list[str], best_score: int
) -> bool:
    """True si un deuxième candidat est à moins de AMBIGUITY_GAP points du meilleur."""
    q_norm = normalize(strip_title(query))
    c_norms = [normalize(strip_title(c)) for c in candidates]
    results = process.extract(
        q_norm, c_norms, scorer=fuzz.token_sort_ratio, limit=2
    )
    return len(results) >= 2 and (best_score - results[1][1]) < AMBIGUITY_GAP


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACTION ANCIEN / NOUVEAU MÉDECIN
# ══════════════════════════════════════════════════════════════════════════════

def _best_name_in_fragment(
    fragment: str, known_names: list[str], threshold: int = NAME_MATCH_THRESHOLD
) -> tuple[Optional[str], int]:
    """
    Dans un fragment de texte (potentiellement bruité), cherche le nom connu
    qui correspond le mieux en testant des sous-fenêtres de 1 à 3 tokens.
    Retourne (canonical, score) ou (None, 0).
    """
    words = fragment.split()
    best: tuple[Optional[str], int] = (None, 0)
    for start in range(min(len(words), 5)):
        for end in range(start + 1, min(start + 4, len(words) + 1)):
            chunk = " ".join(words[start:end])
            chunk_stripped = re.sub(r"^(dr\.?\s*|docteur\s+)", "", chunk).strip()
            if len(chunk_stripped) < 3:
                continue
            canonical, score = fuzzy_best(chunk_stripped, known_names, threshold=threshold)
            if canonical and score > best[1]:
                best = (canonical, score)
    return best


def extract_old_new(
    text: str, known_names: list[str]
) -> tuple[Optional[str], int, Optional[str], int]:
    """
    Identifie l'ancien médecin et le nouveau médecin dans `text`.

    Stratégie principale : patterns regex ordonnés sur le texte normalisé.
    Retourne : (old_name, old_score, new_name, new_score)
    """
    norm = normalize(text)
    old_raw: Optional[str] = None
    new_raw: Optional[str] = None

    # ── Patterns ordonnés du plus spécifique au plus général ─────────────────
    #
    # Chaque pattern capture les fragments bruts (avant fuzzy matching).
    # Les groupes capturent au maximum ~30 caractères pour éviter le bruit.

    # 1) "remplacer/enlever ... X ... par/mettre ... Y"
    m = re.search(
        r"(?:remplacer?|remplacez|enlever?|enlevez|retirer?|supprimer?)"
        r"\s+(.{3,30}?)\s+"
        r"(?:et\s+)?(?:par|mettre|affecter|affecter)\s+(.{3,30}?)(?=\s|$)",
        norm,
    )
    if m:
        old_raw, new_raw = m.group(1).strip(), m.group(2).strip()

    # 2) "Y et non X"  ou  "sera Y et non X"
    if not old_raw:
        m = re.search(
            r"(?:sera\s+)?(.{3,25}?)\s+et\s+non\s+(.{3,25}?)(?=\s|$)",
            norm,
        )
        if m:
            new_raw = m.group(1).strip()
            old_raw = m.group(2).strip()

    # 3) "mettre/affecter/nommer/sera Y" (nouveau uniquement)
    if not new_raw:
        m = re.search(
            r"(?:mettre|mettez|affecter|nommer|sera)\s+(.{3,30})(?:\s|$)",
            norm,
        )
        if m:
            new_raw = m.group(1).strip()

    # 4) "anesthesiste[s]? [: ]? Y"
    if not new_raw:
        m = re.search(r"anesthesi\w*\s*[:.\\s]\s*(.{3,30})(?:\s|$)", norm)
        if m:
            new_raw = m.group(1).strip()

    # ── Fuzzy matching sur les fragments extraits ─────────────────────────────
    old_name, old_score = _best_name_in_fragment(old_raw, known_names) if old_raw else (None, 0)
    new_name, new_score = _best_name_in_fragment(new_raw, known_names) if new_raw else (None, 0)

    # ── Désambiguïsation si old == new ───────────────────────────────────────
    if old_name and new_name and old_name == new_name:
        old_name, old_score = None, 0

    return old_name, old_score, new_name, new_score


# ══════════════════════════════════════════════════════════════════════════════
#  PERTINENCE
# ══════════════════════════════════════════════════════════════════════════════

def is_relevant(subject: str, body: str) -> bool:
    """True si l'email est lié à l'anesthésie ou à une modification de planning."""
    combined = normalize(subject + " " + body)
    return any(kw in combined for kw in ANESTHESIA_KEYWORDS)


# ══════════════════════════════════════════════════════════════════════════════
#  INTERPRÉTATION D'UN EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def interpret(subject: str, body: str, data: list[dict]) -> dict:
    """
    Analyse un email et retourne un dict de décision :
      dates, old_name, old_score, new_name, new_score, confidence, action, reason
    """
    full_text = subject + "\n" + body
    dates     = extract_dates(full_text)

    # Pools de noms connus
    all_anest = list({r["anesthesiologist"] for r in data})
    all_surg  = list({r["surgeon"] for r in data})
    all_known = all_anest + all_surg

    # Restreint les candidats "ancien" aux anesthésistes déjà affectés à cette date
    candidates_old = all_anest
    if dates:
        date_rows = [r for r in data if r["date"] == dates[0]]
        if date_rows:
            candidates_old = list({r["anesthesiologist"] for r in date_rows})

    # Extraction avec tous les noms connus (old peut aussi être un nouveau nom en base)
    old_name, old_score, new_name, new_score = extract_old_new(full_text, all_known)

    # Re-validation de l'ancien médecin contre les anesthésistes de la date concernée
    if old_name and dates and candidates_old is not all_anest:
        _, validated_score = fuzzy_best(old_name, candidates_old, threshold=50)
        if validated_score < 50:
            old_name, old_score = None, 0  # Pas dans la date concernée
        else:
            old_score = validated_score

    # ── Score de confiance global (/ 100) ─────────────────────────────────────
    # Date trouvée          → +35 pts
    # Ancien médecin trouvé → jusqu'à +30 pts (pondéré par score de matching)
    # Nouveau médecin trouvé → jusqu'à +35 pts
    confidence = 0
    if dates:      confidence += 35
    if old_name:   confidence += round(old_score * 0.30)
    if new_name:   confidence += round(new_score * 0.35)
    confidence = min(confidence, 100)

    result = {
        "dates":      dates,
        "old_name":   old_name,
        "old_score":  old_score,
        "new_name":   new_name,
        "new_score":  new_score,
        "confidence": confidence,
        "action":     "none",
        "reason":     "",
    }

    # ── Règles de décision ────────────────────────────────────────────────────
    if not dates:
        result.update(action="manual", reason="Aucune date détectée.")
        return result

    if not new_name:
        result.update(action="manual", reason="Nouveau médecin non identifié.")
        return result

    if confidence < CONFIDENCE_THRESHOLD:
        result.update(
            action="manual",
            reason=f"Confiance trop faible ({confidence}/100 < seuil {CONFIDENCE_THRESHOLD}).",
        )
        return result

    if old_name and is_ambiguous(old_name, candidates_old, old_score):
        result.update(
            action="manual",
            reason="Ambiguïté sur l'ancien médecin (plusieurs correspondances proches).",
        )
        return result

    result["action"] = "update"
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  MISE À JOUR DU CSV
# ══════════════════════════════════════════════════════════════════════════════

def apply_update(
    data: list[dict], interp: dict, dry_run: bool = False
) -> tuple[list[dict], int]:
    """
    Applique la modification à `data` (en mémoire).
    Si `dry_run=True`, ne sauvegarde pas sur disque.
    Retourne (data_modifiée, nombre_de_lignes_modifiées).

    Règles :
    - Si old_name est précisé  → ne modifie que les lignes où l'anesthésiste matche old_name.
    - Si old_name est absent   → ne modifie que si la date n'a qu'UNE seule ligne (évite
                                 de remplacer tous les chirurgiens ambiguément).
    """
    new_data = deepcopy(data)
    count = 0

    for date in interp["dates"]:
        rows_for_date = [r for r in new_data if r["date"] == date]

        if not rows_for_date:
            continue

        if interp["old_name"]:
            # Remplace uniquement les lignes dont l'anesthésiste ressemble à old_name
            for row in rows_for_date:
                _, match_score = fuzzy_best(
                    row["anesthesiologist"], [interp["old_name"]], threshold=60
                )
                if match_score >= 60:
                    row["anesthesiologist"] = interp["new_name"]
                    count += 1
        else:
            # Pas d'ancien précisé → ne procède que si une seule ligne pour cette date
            if len(rows_for_date) == 1:
                rows_for_date[0]["anesthesiologist"] = interp["new_name"]
                count += 1
            else:
                log.warning(
                    f"  ⚠️  Plusieurs lignes pour le {date} et aucun ancien médecin précisé "
                    f"→ revue manuelle requise."
                )

    if count > 0 and not dry_run:
        save_csv(DATA_FILE, new_data)

    return new_data, count


# ══════════════════════════════════════════════════════════════════════════════
#  LECTURE GMAIL (IMAP)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_unread_emails() -> list[dict]:
    """
    Se connecte à Gmail via IMAP SSL, retourne les emails non lus
    sous forme de liste de dicts {uid, from, subject, body}.
    L'email est automatiquement marqué comme lu après récupération (comportement IMAP standard).
    """
    if not GMAIL_PASSWORD:
        log.error(
            "Identifiants manquants dans le fichier .env.\n"
            "  1. Copiez .env.example → .env\n"
            "  2. Renseignez GMAIL_USER et GMAIL_APP_PASSWORD\n"
            "  Aide : https://myaccount.google.com/apppasswords"
        )
        sys.exit(1)

    if not GMAIL_USER:
        log.error("GMAIL_USER manquant dans .env")
        sys.exit(1)

    log.info("Connexion IMAP → imap.gmail.com…")
    conn = imaplib.IMAP4_SSL("imap.gmail.com")
    conn.login(GMAIL_USER, GMAIL_PASSWORD)
    conn.select("INBOX")

    _, uid_data = conn.search(None, "UNSEEN")
    uid_list = uid_data[0].split()
    log.info(f"{len(uid_list)} email(s) non lu(s) trouvé(s).")

    results: list[dict] = []
    for uid in uid_list:
        _, msg_data = conn.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        # Décodage de l'objet de l'email
        raw_subject = msg["Subject"] or ""
        subject = ""
        for part, enc in decode_header(raw_subject):
            if isinstance(part, bytes):
                subject += part.decode(enc or "utf-8", errors="replace")
            else:
                subject += str(part)

        # Extraction du corps en texte brut (prefer text/plain)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
        else:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")

        results.append({
            "uid":     uid.decode(),
            "from":    msg.get("From", ""),
            "subject": subject.strip(),
            "body":    body.strip(),
        })

    conn.logout()
    return results


def sync_data_to_github(changed_rows: int, dry_run: bool) -> None:
    """
    Commit + push de data.csv vers GitHub uniquement si le fichier a changé.
    """
    if dry_run:
        log.info("Sync GitHub ignorée (mode dry-run).")
        return

    if not GIT_AUTO_PUSH:
        log.info("Sync GitHub désactivée (GIT_AUTO_PUSH=0/false).")
        return

    if not (BASE_DIR / ".git").exists():
        log.warning("Dossier .git introuvable, impossible de pousser vers GitHub.")
        return

    def run_git(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=BASE_DIR,
            text=True,
            capture_output=True,
            check=False,
        )

    add_res = run_git(["add", str(DATA_FILE.name)])
    if add_res.returncode != 0:
        log.error(f"git add a échoué: {add_res.stderr.strip() or add_res.stdout.strip()}")
        return

    staged_check = run_git(["diff", "--cached", "--quiet", "--", str(DATA_FILE.name)])
    if staged_check.returncode == 0:
        log.info("Aucun changement git détecté sur data.csv, pas de push.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"Auto-update data.csv from Gmail ({changed_rows} row(s)) - {timestamp}"

    commit_res = run_git(["commit", "-m", commit_msg, "--", str(DATA_FILE.name)])
    if commit_res.returncode != 0:
        out = commit_res.stderr.strip() or commit_res.stdout.strip()
        if "nothing to commit" in out.lower():
            log.info("Rien à commit après vérification, push ignoré.")
            return
        log.error(f"git commit a échoué: {out}")
        return

    log.info(f"Commit créé: {commit_msg}")

    push_res = run_git(["push", GIT_REMOTE, GIT_BRANCH])
    if push_res.returncode != 0:
        log.error(f"git push a échoué: {push_res.stderr.strip() or push_res.stdout.strip()}")
        return

    log.info(f"Push GitHub réussi vers {GIT_REMOTE}/{GIT_BRANCH}.")


# ══════════════════════════════════════════════════════════════════════════════
#  BOUCLE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Moniteur Gmail → mise à jour des anesthésistes dans data.csv"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule le traitement sans modifier data.csv",
    )
    args = parser.parse_args()

    banner = "═" * 64
    log.info(banner)
    log.info("Démarrage du moniteur Gmail")
    if args.dry_run:
        log.info("⚠️  Mode DRY-RUN actif — data.csv ne sera PAS modifié")
    log.info(banner)

    data = load_csv(DATA_FILE)
    emails = fetch_unread_emails()

    if not emails:
        log.info("Aucun email non lu à traiter.")
        log.info(banner)
        return

    total_rows_changed = 0

    for em in emails:
        sep = "─" * 56
        log.info(f"\n{sep}")
        log.info(f"UID     : {em['uid']}")
        log.info(f"De      : {em['from']}")
        log.info(f"Objet   : {em['subject']}")
        preview = em["body"][:150].replace("\n", " ")
        log.info(f"Corps   : {preview}{'…' if len(em['body']) > 150 else ''}")

        # ── Filtre de pertinence ──────────────────────────────────────────────
        if not is_relevant(em["subject"], em["body"]):
            log.info("→ Ignoré (non lié à l'anesthésie / planning).")
            continue

        # ── Interprétation ────────────────────────────────────────────────────
        interp = interpret(em["subject"], em["body"], data)

        log.info(f"  Dates détectées  : {interp['dates'] or '—'}")
        log.info(
            f"  Ancien médecin   : {interp['old_name'] or '(non précisé)'}"
            f"  (score {interp['old_score']})"
        )
        log.info(
            f"  Nouveau médecin  : {interp['new_name'] or '(non identifié)'}"
            f"  (score {interp['new_score']})"
        )
        log.info(f"  Confiance        : {interp['confidence']}/100")
        log.info(f"  Décision         : {interp['action'].upper()}")

        # ── Application ───────────────────────────────────────────────────────
        if interp["action"] == "update":
            updated_data, n = apply_update(data, interp, dry_run=args.dry_run)
            if n > 0:
                total_rows_changed += n
                qualifier = "simulée" if args.dry_run else "appliquée"
                log.info(f"  ✅ Modification {qualifier} : {n} ligne(s) mise(s) à jour.")
                if not args.dry_run:
                    data = updated_data  # Propagation en mémoire pour les emails suivants
            else:
                log.warning(
                    "  ⚠️  Aucune ligne correspondante dans data.csv "
                    f"pour la date {interp['dates']} / médecin {interp['old_name']}."
                )
        else:
            log.warning(f"  ⏸  Revue manuelle requise : {interp['reason']}")
            log.warning(f"  Corps complet : {em['body'][:400]}")

    if total_rows_changed > 0:
        sync_data_to_github(changed_rows=total_rows_changed, dry_run=args.dry_run)
    else:
        log.info("Aucune ligne modifiée dans data.csv, synchronisation GitHub non nécessaire.")

    log.info(f"\n{banner}")
    log.info("Traitement terminé.")


if __name__ == "__main__":
    main()
