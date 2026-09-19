# CAHIER DES CHARGES — Application de veille et d'inscription automatisée aux événements UniCA Sport

## 1. CONTEXTE ET OBJECTIF

Je souhaite une application web progressive (PWA) qui surveille en permanence la page des événements du site UniCA Sport (https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement), détecte l'apparition de nouveaux événements, et notifie les utilisateurs inscrits selon des règles de filtrage personnalisées qu'ils auront eux-mêmes définies. Optionnellement, pour les événements « favorisés », l'application doit pouvoir s'inscrire automatiquement à la place de l'utilisateur (sans valider le paiement) afin de lui réserver un créneau pendant 30 minutes.

L'application doit être : **simple à déployer, fiable, sécurisée, et facile à maintenir**. Privilégie systématiquement la solution la plus sobre à complexité fonctionnelle égale — pas de microservices, pas de sur-ingénierie.

## 2. ARCHITECTURE TECHNIQUE IMPOSÉE

Merci de respecter strictement cette pile technique (elle a été choisie pour sa cohérence et sa simplicité de déploiement) :

- **Backend** : Django 5.x + Django REST Framework, pour l'API et l'interface d'administration (tu bénéficies gratuitement de `django.contrib.admin`, qu'il faudra étendre — voir section 6).
- **Base de données** : PostgreSQL.
- **File de tâches asynchrones / ordonnanceur** : Celery + Redis comme broker. Utiliser `django-celery-beat` pour piloter dynamiquement la fréquence de scan depuis la base de données (voir section 4.1 — le rythme doit être ajustable sans redéploiement).
- **Scraping** : Playwright (Python, mode asynchrone), avec la librairie `playwright-stealth` pour limiter la détection comme robot.
- **Authentification utilisateurs** : `django-allauth` pour gérer à la fois l'authentification classique (email + mot de passe) et l'authentification via Google OAuth2 (clé/secret configurables depuis l'interface admin).
- **Notifications push web** : `pywebpush` + clés VAPID (Push API standard, pas de dépendance à Firebase).
- **Interface utilisateur** : Une seule application Django servant des templates côté serveur (pas de framework JS séparé type React/Vue — inutile ici et source de complexité de déploiement superflue), avec :
  - **Material Web Components** (`@material/web`, chargé via CDN) pour obtenir une esthétique Material You sans réinventer les composants.
  - Un `manifest.json` et un `service-worker.js` pour rendre le site installable et gérer la réception des notifications push.
  - HTMX (optionnel mais recommandé) pour les interactions dynamiques (ajout/suppression de règles) sans écrire de JS custom fastidieux.
- **Déploiement** : un unique `docker-compose.yml` orchestrant : `web` (Django/Gunicorn), `worker` (Celery), `beat` (Celery Beat), `redis`, `db` (Postgres), et `nginx` en reverse proxy avec certificat TLS (Let's Encrypt via Certbot ou Caddy à la place de Nginx si cela simplifie la configuration TLS automatique — au choix, mais justifie ton choix).

Ne propose pas d'alternative à cette pile (pas de Node.js, pas de FastAPI, pas de MongoDB) : l'objectif est la cohérence et la maintenabilité par une seule personne.

## 3. MODÈLE DE DONNÉES (à affiner mais respecter cette structure de base)

- **User** (via `allauth`) : email, mot de passe, rôle (`is_staff`/`is_superuser` Django standard suffisent pour distinguer administrateur/superadmin).
- **Event** : identifiant unique côté site source, titre, description, date, lieu, URL, horodatage de première détection, hash de contenu (pour détecter les modifications, pas seulement les créations).
- **FilterRule** : utilisateur (FK), type (`blacklist` ou `favorite`), mode de correspondance (`contains`, `starts_with`, `ends_with`, `equals`), mot-clé, champ ciblé (titre uniquement, ou titre+description — à décider), sensibilité à la casse (booléen).
- **UniCACredentials** : utilisateur (FK, relation one-to-one), identifiant UniCA, mot de passe chiffré **de façon réversible** via `cryptography.fernet.Fernet`, avec une clé de chiffrement stockée exclusivement en variable d'environnement côté serveur (jamais en base). Documente clairement dans le code que cette clé doit être générée une fois (`Fernet.generate_key()`) et sauvegardée hors du dépôt Git.
- **NotificationPreference** : utilisateur (FK), canal (`email`, `discord_webhook`, `whatsapp`, `telegram`, `push`), configuration spécifique au canal (URL de webhook Discord, chat_id Telegram, numéro WhatsApp, endpoint/clés d'abonnement push), actif (booléen).
- **RegistrationAttempt** : événement (FK), utilisateur (FK), statut (`en_attente`, `réussi`, `échoué`, `expiré`), horodatage, message d'erreur éventuel — pour la traçabilité et le diagnostic.
- **ScanLog** : horodatage, durée d'exécution, nombre d'événements trouvés, nombre de nouveaux événements, statut (succès/échec), pour permettre le diagnostic depuis l'admin.
- **ServerSettings** (singleton, éditable depuis l'admin) : intervalle de scan diurne (défaut 60s), jitter diurne (défaut ±10s), intervalle nocturne (défaut 900s = 15 min), jitter nocturne (défaut ±30s), heures de bascule diurne/nocturne (défaut 06:00–00:00), configuration SMTP (hôte, port, utilisateur, mot de passe, TLS), clés API Google OAuth, token bot Telegram, clés API WhatsApp Business.

## 4. FONCTIONNALITÉS DÉTAILLÉES

### 4.1 Worker de scraping

- Tâche Celery auto-replanifiée (et non une tâche périodique à intervalle fixe) : à la fin de chaque exécution, elle calcule elle-même le délai avant la prochaine exécution en fonction de l'heure courante et des réglages en base (`ServerSettings`), puis se replanifie via `apply_async(countdown=...)`. Cela permet de gérer nativement la bascule diurne/nocturne et le jitter aléatoire, sans dépendre d'un cron figé.
- À chaque exécution : lancer Playwright en mode headless avec `playwright-stealth`, naviguer vers la page cible, extraire la liste des événements (titre, date, lieu, URL, description si disponible), comparer avec les événements déjà connus en base (par identifiant unique ou hash de contenu), et créer les nouveaux `Event`.
- Pour chaque nouvel événement, évaluer les `FilterRule` de chaque utilisateur : s'il matche une règle `blacklist`, ne rien envoyer ; s'il matche une règle `favorite`, déclencher en plus la tentative d'inscription automatique (section 4.2) ; dans tous les autres cas, envoyer une notification standard.
- Enregistrer un `ScanLog` à chaque passage, y compris en cas d'échec (page inaccessible, structure HTML modifiée, timeout).

### 4.2 Inscription automatique (fonctionnalité sensible — voir pièges section 7)

- Si l'utilisateur a renseigné ses identifiants UniCA et que l'événement matche une règle `favorite`, déclencher une tâche Celery dédiée qui : déchiffre les identifiants, lance une session Playwright authentifiée, navigue jusqu'à la page d'inscription de l'événement, remplit le formulaire, valide jusqu'à l'étape de blocage de place (30 minutes), **s'arrête explicitement avant toute validation de paiement**, et journalise le résultat dans `RegistrationAttempt`.
- Notifier immédiatement l'utilisateur du résultat (succès avec délai restant, ou échec avec raison) sur son ou ses canaux préférés.
- Prévoir un mécanisme de nouvelle tentative limité (2 essais maximum) en cas d'échec technique transitoire, avec backoff.

### 4.3 Système de notification multicanal

- Abstraire l'envoi de notification derrière une interface commune (`NotificationBackend`), avec une implémentation par canal (`EmailBackend`, `DiscordWebhookBackend`, `TelegramBackend`, `WhatsAppBackend`, `WebPushBackend`).
- Chaque utilisateur peut activer plusieurs canaux simultanément et personnaliser le contenu du message n'est pas requis, mais la sélection des canaux actifs doit être multi-sélection dans l'interface.
- Pour WhatsApp, utiliser l'API Cloud de Meta (WhatsApp Business Platform) plutôt qu'une solution non officielle par navigateur (Baileys, etc.), pour la fiabilité et la conformité aux conditions d'utilisation.

### 4.4 Interface utilisateur (PWA)

- Page de connexion/inscription (email+mot de passe ou Google OAuth).
- Page « Règles » : interface simple permettant d'ajouter/supprimer des règles de blacklist et de favoris (formulaire : mode de correspondance en menu déroulant, champ mot-clé, bouton d'ajout ; liste des règles existantes avec bouton de suppression).
- Page « Identifiants UniCA » : formulaire pour renseigner (ou effacer) les identifiants UniCA Sport, avec avertissement clair sur l'usage qui en sera fait.
- Page « Notifications » : sélection des canaux actifs et saisie des paramètres associés (webhook Discord, identifiant Telegram avec instructions pour l'obtenir via le bot, etc.), plus un bouton pour activer les notifications push (déclenche la demande de permission navigateur et l'abonnement).
- Design en Material You (Material Design 3) : palette de couleurs dynamique, composants `md-outlined-text-field`, `md-filled-button`, `md-switch`, etc. de la librairie `@material/web`.
- Manifest PWA complet (icônes, couleur de thème, `display: standalone`) et service worker gérant le cache minimal et la réception des push.

### 4.5 Interface d'administration

- Étendre `django.contrib.admin` (ou construire une page dédiée si plus pratique) accessible uniquement aux comptes `is_staff`.
- Un compte superadmin doit être créé automatiquement au premier déploiement (via une commande de gestion `create_default_superuser` ou une migration de données) avec l'email `vincent.foriel@gmail.com` — le mot de passe initial doit être généré aléatoirement et affiché une seule fois dans les logs au démarrage (jamais codé en dur dans le dépôt).
- Depuis l'admin :
  - Édition de `ServerSettings` (SMTP, clés Google OAuth, clés WhatsApp/Telegram, fréquence et jitter de scan diurne/nocturne).
  - Liste des comptes utilisateurs avec, pour chacun : ses règles, ses préférences de notification, et des actions rapides — **réinitialiser le mot de passe** (envoi d'un lien de réinitialisation), **supprimer le compte** (avec confirmation et suppression en cascade des données associées, conformément à un usage responsable des données personnelles), **ajouter/retirer le rôle administrateur**.
  - Consultation des `ScanLog` et `RegistrationAttempt` récents pour le diagnostic.

## 5. SÉCURITÉ (non négociable)

- Aucun secret en dur dans le code : tout via variables d'environnement (`.env`, exclu du dépôt via `.gitignore`), chargées avec `django-environ` ou équivalent.
- Mots de passe utilisateurs hachés (géré nativement par Django) ; identifiants UniCA chiffrés de façon réversible (Fernet), jamais en clair, jamais journalisés.
- HTTPS obligatoire en production (Let's Encrypt), cookies de session `Secure` et `HttpOnly`.
- Protection CSRF (native Django) et limitation de débit (`django-ratelimit`) sur les endpoints d'authentification et l'API.
- Validation stricte des entrées utilisateurs (mots-clés des règles, URLs de webhook) pour éviter toute injection.
- Journalisation des actions sensibles (connexion admin, modification de rôle, suppression de compte) dans un journal d'audit simple.

## 6. DÉPLOIEMENT

- Un unique `docker-compose.yml` à la racine, avec un fichier `.env.example` documentant chaque variable requise.
- Un `README.md` détaillant : la procédure de lancement (`docker compose up -d`), la génération de la clé Fernet, la configuration initiale des clés API tierces, et la récupération du mot de passe superadmin initial dans les logs.
- Prévoir des migrations Django versionnées et un script d'initialisation idempotent.

## 7. PIÈGES À ÉVITER (points d'attention impératifs)

1. **Fragilité du scraping** : la structure HTML du site UniCA Sport peut changer sans préavis. Isole la logique d'extraction dans un module dédié et unique, avec des sélecteurs robustes (attributs sémantiques plutôt que classes CSS générées), et fais échouer proprement (log + alerte admin) plutôt que de planter silencieusement.
2. **Détection anti-robot** : au-delà de `playwright-stealth`, varie le user-agent, respecte des délais humains entre les actions (pas de clics instantanés), et évite absolument de paralléliser les sessions Playwright pour un même compte utilisateur (risque de blocage IP ou de bannissement de compte).
3. **Zone grise légale et éthique de l'inscription automatique** : automatiser une inscription — même sans validation de paiement — pour bloquer une place à la place d'un tiers peut contrevenir aux conditions d'utilisation d'UniCA Sport, et priver d'autres usagers légitimes d'un créneau pendant 30 minutes à chaque tentative, y compris pour des événements que l'utilisateur ne confirmera peut-être jamais. Je te recommande d'implémenter un consentement explicite et documenté de l'utilisateur avant d'activer cette fonctionnalité sur son compte, et de prévoir un mécanisme de limitation (par exemple, un nombre maximal de blocages simultanés non confirmés par utilisateur) pour limiter l'impact sur les autres usagers.
4. **Étape exacte d'arrêt avant paiement** : identifie précisément, en observant manuellement le tunnel d'inscription du site, à quelle étape la place est réservée sans engagement financier ferme ; documente cette étape dans le code avec un commentaire explicite, car une évolution du site pourrait faire sauter cette limite par inadvertance.
5. **Fuseau horaire** : les horaires de bascule diurne/nocturne (6h–minuit) doivent être calculés dans le fuseau `Europe/Paris`, pas en UTC serveur, sous peine de décalage selon l'hébergement.
6. **Clé Fernet perdue = identifiants irrécupérables** : documente clairement la procédure de sauvegarde de cette clé, et prévois qu'une perte de clé nécessite que chaque utilisateur ressaisisse ses identifiants UniCA.
7. **Rate-limiting des canaux externes** : les webhooks Discord et l'API WhatsApp Business ont leurs propres limites de débit ; prévois une file d'attente Celery dédiée à l'envoi des notifications pour absorber les pics (par exemple lors de la découverte simultanée de plusieurs événements) sans dépasser ces quotas.

## 8. LIVRABLES ATTENDUS

- Code source complet et structuré (arborescence Django standard, apps séparées par domaine fonctionnel : `events`, `notifications`, `accounts`, `scraping`).
- `docker-compose.yml`, `Dockerfile`(s), `.env.example`.
- `README.md` complet (installation, configuration, déploiement, dépannage courant).
- Tests unitaires a minima sur : la logique de correspondance des règles (`contains`/`starts_with`/`ends_with`/`equals`), le chiffrement/déchiffrement des identifiants, et la logique de calcul du prochain créneau de scan (jitter + bascule diurne/nocturne).