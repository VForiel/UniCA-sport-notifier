# UniCA Sport Notifier

Application Web Progressive (PWA) de veille automatique, de filtrage personnalisé et de réservation anticipée (30 minutes) pour les événements du portail UniCA Sport ([sport.univ-cotedazur.fr](https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement)).

---

## Table des Matières
1. [Fonctionnalités Clés](#1-fonctionnalités-clés)
2. [Pile Technologique](#2-pile-technologique)
3. [Architecture et Sécurité](#3-architecture-et-sécurité)
4. [Déploiement avec Docker Compose (Recommandé)](#4-déploiement-avec-docker-compose-recommandé)
5. [Installation en Développement Local](#5-installation-en-développement-local)
6. [Génération de la Clé de Chiffrement Fernet](#6-génération-de-la-clé-de-chiffrement-fernet)
7. [Récupération du Mot de Passe Superadministrateur](#7-récupération-du-mot-de-passe-superadministrateur)
8. [Configuration des Canaux Externes](#8-configuration-des-canaux-externes)
9. [Points d'Attention & Règles Éthiques](#9-points-dattention--règles-éthiques)
10. [Exécution de la Suite de Tests](#10-exécution-de-la-suite-de-tests)

---

## 1. Fonctionnalités Clés

- **Veille autonome & Scraper asynchrone** : Scraping Playwright avec `playwright-stealth`, rotation d'User-Agents et temporisations humaines réalistes.
- **Ordonnanceur dynamique auto-replanifié** : Tâche Celery sans cron figé ; calcule son prochain délai en fonction de l'heure légale à Paris (`Europe/Paris`), du mode diurne/nocturne et d'un jitter aléatoire $\pm$ ajustable en base.
- **Règles de filtrage personnalisées** :
  - **Liste noire** : Ne jamais notifier les activités exclues.
  - **Favoris** : Priorité maximale, alerte immédiate et déclenchement de la réservation automatique.
  - Modes : `contient`, `commence par`, `se termine par`, `égal à`, sensibilité à la casse réglable.
- **Réservation temporaire 30 minutes (Sécurité & Éthique)** :
  - Connexion automatisée via compte CAS ou externe UniCA.
  - Ajout de l'événement au panier pour verrouiller le créneau pendant 30 minutes.
  - **Arrêt formel et explicite avant toute étape de paiement ou débit bancaire.** L'utilisateur valide lui-même sa commande.
  - Consentement formel requis et limitation stricte à 2 réservations simultanées pour préserver l'équité sportive.
- **Multi-canal de notifications** : Web Push PWA (norme standard VAPID Push API), Webhook Discord (Embeds riches), Bot Telegram, WhatsApp Business (Meta Cloud API officielle), Email SMTP.
- **Interface Progressive Web App (PWA)** :
  - Interface sobre (thème clair/sombre selon le système), sans police ni script externe.
  - HTMX servi localement (ajout/suppression de règles sans rechargement).
  - Installable sur mobile et ordinateur avec `manifest.json` et `service-worker.js`.
- **Accès sur invitation** : tout nouveau compte est créé inactif ; les administrateurs reçoivent un email et le valident depuis l'admin (action « Valider les comptes sélectionnés »).
- **Administration Django sur-mesure** :
  - Singleton `ServerSettings` éditable à chaud (intervalles, jitter, clés API).
  - Actions rapides sur les utilisateurs : réinitialisation de mot de passe par email, suppression de compte en cascade (RGPD), bascule de droits.
  - Journal d'audit des actions sensibles (`AuditLog`) et diagnostics (`ScanLog`, `RegistrationAttempt`).

---

## 2. Pile Technologique

- **Backend** : Python 3.12+ / Django 5.1 / Django REST Framework
- **Tâches Asynchrones & Broker** : Celery 5.6 + Redis 7
- **Base de données** : PostgreSQL 16 (production) / SQLite (développement/tests)
- **Scraping & Automatisation** : Playwright Async (Chromium headless) + `playwright-stealth`
- **Authentification** : `django-allauth` (Email + Google OAuth2)
- **Notifications Web Push** : `pywebpush` + Clés VAPID (zéro dépendance Firebase)
- **Frontend** : Django Server-Side Rendering + CSS maison + HTMX 2.0 (servi localement)
- **Reverse Proxy & TLS** : Caddy 2 (certificats Let's Encrypt / ZeroSSL automatiques)

---

## 3. Architecture et Sécurité

1. **Chiffrement réversible des identifiants UniCA** : Chiffrés avec AES-128 via `cryptography.fernet.Fernet`. La clé `FERNET_KEY` est impérativement lue depuis la variable d'environnement et n'est **jamais** stockée en base de données.
2. **Protection CSRF & Sessions Sécurisées** : Cookies `HttpOnly`, `Secure` et `SameSite=Lax` activés en production.
3. **Journalisation d'audit** : Demandes d'accès, validations, modifications de rôles et suppressions de comptes consignées dans `AuditLog`.
4. **En-têtes de sécurité** : Django pose HSTS, Content-Security-Policy (aucune ressource tierce hormis les images d'événements), `X-Frame-Options` et `Referrer-Policy` ; les proxys Caddy n'en ajoutent pas.
5. **Limitation des abus** : connexion admin via allauth (tentatives limitées), test de notification limité à 5 envois par heure, webhooks restreints à `discord.com`, cache Redis partagé entre workers (`CACHE_URL`).
6. **Purge automatique** : Celery beat supprime chaque jour les `ScanLog` de plus de 30 jours et les événements de test.

---

## 4. Déploiement avec Docker Compose (Recommandé)

### Prérequis
- Docker et Docker Compose installés sur votre serveur.
- Un nom de domaine pointant vers l'adresse IP de votre serveur (pour le certificat TLS automatique Caddy).

### Étape 1 : Cloner le projet
```bash
git clone https://github.com/VForiel/UniCA-sport-notifier.git
cd UniCA-sport-notifier
```

### Étape 2 : Configurer le fichier d'environnement
Copiez le modèle et éditez les variables :
```bash
cp .env.example .env
```

### Étape 3 : Générer la clé Fernet et la clé secrète
Exécutez cette commande pour obtenir votre clé Fernet :
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Collez la clé obtenue dans la variable `FERNET_KEY=` de votre fichier `.env`.

Définissez également un `SECRET_KEY` aléatoire, un `POSTGRES_PASSWORD` aléatoire (obligatoire) et ajustez `DOMAIN_NAME` :
```env
SECRET_KEY=votre-cle-secrete-django-tres-longue
DOMAIN_NAME=sport-notifier.votre-domaine.fr
DEBUG=False
```

### Étape 4 : Lancer l'application
```bash
docker compose up -d
```
Docker va orchestrer les 6 services :
- `db` (PostgreSQL)
- `redis` (Broker Celery)
- `web` (Django Gunicorn)
- `worker` (Scraping Playwright & Réservations)
- `beat` (Garde-fou Celery Beat)
- `caddy` (Reverse proxy HTTPS automatique)

Le script `docker/entrypoint.sh` applique automatiquement les migrations, collecte les fichiers statiques et initialise le superadministrateur.

---

## 5. Installation en Développement Local

Si vous souhaitez exécuter le projet en local avec SQLite :

1. Créez et activez un environnement virtuel Python 3.12+ :
   ```bash
   python -m venv .venv
   # Windows PowerShell :
   .venv\Scripts\Activate.ps1
   # Linux / macOS :
   source .venv/bin/activate
   ```

2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. Configurez `.env` :
   ```env
   SECRET_KEY=dev-secret-key
   DEBUG=True
   TIME_ZONE=Europe/Paris
   DATABASE_URL=sqlite:///db.sqlite3
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   FERNET_KEY=votre-cle-fernet-generee
   ```

4. Appliquez les migrations et créez le superadmin :
   ```bash
   python manage.py migrate
   python manage.py create_default_superuser
   ```

5. Lancez le serveur de développement :
   ```bash
   python manage.py runserver
   ```
   Rendez-vous sur `http://localhost:8000/`.

---

## 6. Génération de la Clé de Chiffrement Fernet

Pour générer une nouvelle clé de chiffrement Fernet :
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> [!WARNING]
> **Conservez précieusement cette clé hors du dépôt Git.**
> Si la clé `FERNET_KEY` est perdue ou modifiée sur le serveur, les identifiants UniCA précédemment enregistrés deviennent indéchiffrables. Les utilisateurs devront alors simplement ressaisir leur mot de passe UniCA depuis la page `/credentials/`.

---

## 7. Récupération du Mot de Passe Superadministrateur

Au premier déploiement, la commande `create_default_superuser` crée automatiquement le compte avec l'adresse :
- **Email** : `vincent.foriel@gmail.com`

Le mot de passe aléatoire de 16 caractères est affiché **une unique fois** dans les logs de démarrage du conteneur `web` :
```bash
docker compose logs web | grep -A 8 "COMPTE SUPERADMIN INITIAL"
```
Connectez-vous immédiatement sur `https://votre-domaine.fr/admin/` et modifiez ce mot de passe selon vos préférences.

---

### Sauvegardes de la base

Le service `backup` écrit chaque jour un dump compressé de PostgreSQL dans `./backups/unica-db-AAAA-MM-JJ.sql.gz`
(dossier modifiable avec `BACKUP_DIR`, durée de conservation avec `BACKUP_KEEP_DAYS`, 30 jours par défaut).
Il vérifie toutes les heures, donc un jour manqué (serveur éteint, redéploiement) est rattrapé au redémarrage.

Restauration (écrase la base actuelle) :
```bash
docker compose stop web worker beat
gunzip -c backups/unica-db-AAAA-MM-JJ.sql.gz | docker compose exec -T db sh -c 'psql -U $POSTGRES_USER -d postgres -c "DROP DATABASE $POSTGRES_DB WITH (FORCE)" -c "CREATE DATABASE $POSTGRES_DB" && psql -U $POSTGRES_USER $POSTGRES_DB'
docker compose start web worker beat
```

Ces sauvegardes restent sur le même serveur : pensez à en copier régulièrement ailleurs.

---

## 8. Configuration des Canaux Externes

Toutes ces clés peuvent être renseignées dans `.env` ou modifiées directement dans l'interface admin (`ServerSettings`) :

### A. Notifications Web Push (PWA)
Générez un couple de clés VAPID :
```bash
npx web-push generate-vapid-keys
```
Renseignez `VAPID_PUBLIC_KEY` et `VAPID_PRIVATE_KEY`.

### B. Webhook Discord
1. Sur Discord, rendez-vous dans les paramètres d'un salon textuel > *Intégrations* > *Webhooks*.
2. Cliquez sur *Nouveau webhook* et copiez son URL.
3. Chaque utilisateur colle son URL dans sa page `/notifications/`.

### C. Bot Telegram
1. Créez un bot auprès de `@BotFather` sur Telegram et récupérez le `TELEGRAM_BOT_TOKEN`.
2. Configurez ce token dans l'admin `ServerSettings`.
3. Chaque utilisateur renseigne son `Chat ID` dans `/notifications/` (obtenu via `@userinfobot`).

### D. WhatsApp Business (Meta Cloud API)
1. Créez une application sur le [Meta for Developers](https://developers.facebook.com/).
2. Activez le produit WhatsApp et configurez un numéro de téléphone d'envoi.
3. Renseignez l'access token permanent et le `phone_number_id` dans `ServerSettings`.

---

## 9. Points d'Attention & Règles Éthiques

1. **Arrêt avant paiement** : La réservation automatisée (`apps/scraping/auto_register.py`) navigue dans le tunnel d'inscription jusqu'à l'étape de blocage du créneau dans le panier (30 minutes accordées par UniCA Sport), puis s'interrompt formellement. Aucune validation bancaire n'est réalisée.
2. **Quota de réservations** : Par souci d'équité avec les autres étudiants, chaque compte est bridé à un maximum de 2 réservations temporaires simultanées non confirmées.
3. **Fuseau horaire `Europe/Paris`** : La bascule jour (06:00) / nuit (00:00) est calculée dans le fuseau légal français, indépendant de l'heure UTC du serveur hôte.
4. **Anti-flood APIs** : Les envois de notifications transitent par la file Celery dédiée `notifications` avec rate-limiting à 30 requêtes/min.

---

## 10. Exécution de la Suite de Tests & Simulateur

### A. Lancement via Visual Studio Code (F5)
Un fichier de configuration prêt à l'emploi est disponible dans `.vscode/launch.json` :
1. **Django: Lancer le serveur web** : Démarre l'application sur `http://localhost:8000/`.
2. **Celery: Worker (Mode solo Windows)** : Démarre le worker Celery configuré en mode solo pour Windows (`-P solo`).
3. **Celery: Beat (Ordonnanceur)** : Démarre le planificateur Celery Beat.
4. **UniCA: Simuler un événement de test** : Déclenche la commande de simulation d'un nouvel événement.
5. **UniCA: Lancer un scan réel immédiat** : Exécute `run_scan_once`.
6. **Tests: Exécuter la suite de tests** : Lance la suite de tests unitaire.

### B. Bouton de Test dans l'Interface Web
Dans l'application web :
- Rendez-vous sur la page **Notifications** (`/notifications/`) ou sur le **Tableau de bord** (`/`).
- Cliquez sur le bouton **"Simuler un test"** ou **"Simuler un événement de test"**.
- L'application crée un événement fictif et déclenche immédiatement vos canaux actifs (Push Web, Discord, Telegram, WhatsApp, Email) en affichant le statut détaillé de chaque envoi.

### C. Simulation en ligne de commande
```bash
python manage.py simulate_new_event --title "KAYAK et Calanques [TEST]"
```
Optionnellement avec l'option `--favorite` pour tester le déclenchement prioritaire des favoris :
```bash
python manage.py simulate_new_event --title "KAYAK et Calanques [TEST]" --favorite
```

### D. Exécution des Tests Automatisés
```bash
python manage.py test tests
```
Résultat attendu :
```
Ran 22 tests in ...s
OK
```
