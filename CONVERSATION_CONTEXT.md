# CONVERSATION_CONTEXT.md

## Objectif du programme

Ce programme est un système de matchmaking permettant d'associer le bon anesthésiste à une date d'opération et au nom du chirurgien.

## Historique des modifications

 - 25/02/2026 : Création du fichier CONVERSATION_CONTEXT.md pour suivre l'historique des étapes et décisions prises lors du développement.
 - 25/02/2026 : Tous les noms d'anesthésistes ont été remplacés par "Dr Adel Maatoug" dans data.csv et script.js. Le nom est désormais cliquable vers Doctolib.
 - 25/02/2026 : Le lien vers la vidéo YouTube a été modifié pour https://www.youtube.com/watch?v=Iq0A1jabLO0.
 - 21/03/2026 : Refonte visuelle complète de index.html — navigation redessinée en grille 3+2 avec icônes SVG haute résolution (YouTube, enveloppe, euro, presse-papiers, document) ; labels courts (Vidéo, Contact, Honoraires, Consignes, Questionnaire) ; tous les styles inline du body consolidés dans le <head> ; fond allégé (#f0f4f8), ombre réduite, espacement amélioré.
 - 21/03/2026 : Création de gmail_monitor.py — script Python de surveillance Gmail (IMAP SSL) qui lit les emails non lus, filtre ceux liés à l'anesthésie, extrait en langage naturel une date, un ancien et un nouveau médecin par fenêtre glissante + fuzzy matching (rapidfuzz), calcule un score de confiance global, et met à jour data.csv uniquement si le score ≥ 75/100. Journalisation complète dans email_processing.log. Mode --dry-run disponible. Création de requirements.txt associé.

## Prochaines étapes

- Ajouter les étapes de modification à chaque nouvelle action.
- Continuer le développement du système de matchmaking.

---

Ce fichier sera mis à jour à chaque étape importante du projet.