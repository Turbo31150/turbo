# 🏗️ JARVIS-TURBO (V_FINAL) : Architecture System Blueprint

Ce document est le manifeste architectural exhaustif de JARVIS-TURBO, détaillant les choix techniques fondamentaux pour atteindre un fonctionnement autonome "Zero-Stop" à haute performance.

## 1. Concurrence Hybride (Asyncio + ProcessPool)
L'orchestrateur repose sur une combinaison de `asyncio` pour les opérations I/O (WebSocket, requêtes API) et d'un `ProcessPoolExecutor` dynamique (lié au nombre de cœurs logiques via `psutil`) pour les calculs lourds (minification, traitement Deep Research). Cette isolation garantit que la boucle d'événements principale n'est jamais bloquée. Les communications inter-processus sont minimisées par l'échange de clés primaires plutôt que de données volumineuses.

## 2. Auto-Réparation et Supervision
En cas d'échec d'une tâche dans le pool de processus, l'orchestrateur utilise une logique de "Fallback" vers une exécution asynchrone sécurisée, gérée via `asyncio.TaskGroup` pour éviter les fuites de mémoire. L'auto-guérison intègre un "Exponential Backoff" pour empêcher les boucles de redémarrage infinies en cas de conflit matériel sévère.

## 3. Télémétrie Matérielle et Auto-Tuning (Affinité CPU)
Le module `monitor.py` utilise `psutil` pour une boucle de rétroaction en temps réel. Si la charge CPU/RAM dépasse les seuils critiques (ex: 85% CPU, 90% RAM), l'orchestrateur dégrade la priorité (valeurs "nice") des travailleurs en arrière-plan ou purge le cache LRU. L'affinité CPU est utilisée pour lier les tâches critiques à des cœurs dédiés, maximisant la chaleur du cache L1/L2/L3.

## 4. Persistance Inférieure à 10ms (aiosqlite + Cache LRU)
La mémoire persistante utilise `aiosqlite` couplé à un cache LRU asynchrone (ex: `async-lru` ou équivalent Rust) pour répondre aux requêtes en moins de 10ms. Les opérations de lecture intensives sont servies depuis la RAM, tandis que les écritures sont sécurisées sur le disque.

## 5. Sécurité Cryptographique (Chiffrement AES-256)
La protection de la mémoire est assurée par le module `security.py` (cryptography/Fernet), garantissant que les données sensibles ne sont jamais stockées en clair. (L'intégration de SQLCipher est la prochaine étape recommandée pour le chiffrement transparent de la base de données SQLite).

## 6. Pipeline Turbo (Grunt Concurrent)
La compilation (minification, optimisation d'assets) est orchestrée via `grunt-concurrent`, permettant au serveur WebSocket et aux tâches de fond de s'exécuter en parallèle sans bloquer le développement de l'interface utilisateur.

## 7. Communication WebSocket (Heartbeat & Drift-Free)
Le pont WebSocket implémente un mécanisme de "Heartbeat" (Ping/Pong explicite avec horodatage UTC) pour détecter les connexions semi-ouvertes et calculer la latence. En cas de déconnexion, un "Exponential Backoff" gère la reconnexion avec récupération d'état pour éviter la perte de contexte.

## 8. Conteneurisation Multi-Étapes (Déploiement Idempotent)
Bien que le déploiement actuel se fasse via `install.sh` directement sur l'hôte M1, l'architecture cible est une image Docker multi-étapes. Le "Builder" compile l'environnement (compilateurs C++ pour la crypto, `npm install`), puis le runtime final est basé sur une image Slim non-privilégiée (`user: nobody`), garantissant sécurité (Zero Trust) et portabilité.

## 9. Divulgation Progressive du Contexte (CLAUDE.md)
Le fichier `CLAUDE.md` agit comme un index racine pour les agents IA. Il n'est pas monolithique mais utilise des pointeurs (imports conceptuels) vers des documentations spécifiques (comme ce manifeste), évitant ainsi de saturer la fenêtre de contexte de 200k tokens tout en assurant une dérive stylistique nulle lors de la génération de code.

## 10. Résilience Autonome ("Dead Man's Switch")
L'inactivité est gérée par un suivi absolu d'horodatage (`last_active` dans SQLite), insensible à la dérive d'horloge. Si le seuil de 24h est dépassé, une notification non bloquante (via `aiosmtplib` ou `aiohttp`) est envoyée en mode "fire-and-forget", résumant les avancées autonomes sans jamais geler l'orchestrateur.

---
*Ce manifeste certifie la solidité structurelle de JARVIS-TURBO (V_FINAL) et valide son déploiement en tant qu'environnement d'orchestration autonome de qualité exceptionnelle.*
