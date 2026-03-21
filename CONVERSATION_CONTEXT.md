# CONVERSATION_CONTEXT.md

## Objectif du programme

Ce programme est un système de matchmaking permettant d'associer le bon anesthésiste à une date d'opération et au nom du chirurgien.

## Historique des modifications

 - 25/02/2026 : Création du fichier CONVERSATION_CONTEXT.md pour suivre l'historique des étapes et décisions prises lors du développement.
 - 25/02/2026 : Tous les noms d'anesthésistes ont été remplacés par "Dr Adel Maatoug" dans data.csv et script.js. Le nom est désormais cliquable vers Doctolib.
 - 25/02/2026 : Le lien vers la vidéo YouTube a été modifié pour https://www.youtube.com/watch?v=Iq0A1jabLO0.
 - 21/03/2026 : Refonte visuelle complète de index.html — navigation redessinée en grille 3+2 avec icônes SVG haute résolution (YouTube, enveloppe, euro, presse-papiers, document) ; labels courts (Vidéo, Contact, Honoraires, Consignes, Questionnaire) ; tous les styles inline du body consolidés dans le <head> ; fond allégé (#f0f4f8), ombre réduite, espacement amélioré.
 - 21/03/2026 : Création de gmail_monitor.py — script Python de surveillance Gmail (IMAP SSL) qui lit les emails non lus, filtre ceux liés à l'anesthésie, extrait en langage naturel une date, un ancien et un nouveau médecin par fenêtre glissante + fuzzy matching (rapidfuzz), calcule un score de confiance global, et met à jour data.csv uniquement si le score ≥ 75/100. Journalisation complète dans email_processing.log. Mode --dry-run disponible. Création de requirements.txt associé.
 - 21/03/2026 : Complétion de data.csv — 149 entrées couvrant tous les jours ouvrés (lundi–vendredi) du 21/02/2026 au 30/06/2026, avec 2 créneaux chirurgicaux par jour et 40 chirurgiens différents. Dr Adel Maatoug affecté à tous les créneaux.
 - 21/03/2026 : Automatisation de gmail_monitor.py via systemd — création de /etc/systemd/system/gmail-monitor.service (oneshot) et /etc/systemd/system/gmail-monitor.timer (toutes les 30 minutes, Persistent=true). Timer activé et démarré (enabled au boot). Dépendances installées dans le venv /opt/matchmaking/.venv. Correction : GMAIL_APP_PASSWORD strip des espaces pour compatibilité IMAP.
 - 21/03/2026 : Prérequis Gmail restants — pour que la connexion IMAP fonctionne, il faut : (1) activer IMAP dans les paramètres Gmail (Paramètres → Transfert et POP/IMAP), (2) vérifier que le mot de passe d'application dans .env est valide (https://myaccount.google.com/apppasswords).
 - 21/03/2026 : Finalisation de l'automatisation GitHub — gmail_monitor.py effectue désormais un git add/commit/push automatique de data.csv vers origin/main uniquement quand des lignes sont réellement modifiées après traitement d'emails (hors --dry-run). Variables optionnelles supportées via .env : GIT_AUTO_PUSH, GIT_REMOTE, GIT_BRANCH.

## Prochaines étapes

- Ajouter les étapes de modification à chaque nouvelle action.
- Continuer le développement du système de matchmaking.

---

Ce fichier sera mis à jour à chaque étape importante du projet.