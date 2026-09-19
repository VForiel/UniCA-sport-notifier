# Instructions pour les agents IA — UniCA-sport-notifier

Ce projet est une application web progressive (PWA) de veille et d'inscription automatisée aux événements du site UniCA Sport (https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement).

## Règles impératives
1. **Consulter systématiquement le `Cahier des charges.md` et le `README.md`** avant toute évolution d'architecture.
2. **Respecter la pile technique imposée** :
   - Backend : Django 5.x + Django REST Framework + Celery + Redis.
   - Scraping : Playwright asynchrone avec `playwright-stealth`.
   - Authentification : `django-allauth`.
   - Interface : Templates Django + `@material/web` (Material You) + HTMX + Service Worker PWA.
   - Déploiement : Docker Compose avec Caddy (TLS automatique).
3. **Structure des fichiers** :
   - Éviter d'ajouter des fichiers non nécessaires à la racine.
   - Les applications Django sont logées dans `apps/` (`accounts`, `events`, `notifications`, `scraping`, `core`).
   - Les templates sont dans `templates/` et les statiques dans `static/`.
4. **Sécurité & Secrets** :
   - Aucun secret en dur. Utiliser `.env` géré par `django-environ`.
   - Les identifiants UniCA doivent être chiffrés avec Fernet et la clé `FERNET_KEY` provient strictement de l'environnement.
   - L'auto-inscription doit impérativement **s'arrêter avant toute étape de paiement ou débit bancaire**.
   - Fuseau horaire : toujours utiliser `Europe/Paris` pour le calcul jour/nuit.
5. **Tests** :
   - Maintenir la couverture de tests sur la logique de correspondance des règles, la cryptographie, et le calcul de replanification avec jitter.
