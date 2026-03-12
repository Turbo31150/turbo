# Auto-Updater + Versioning System JARVIS v10.6.0

Système complet de gestion des mises à jour et des versions pour JARVIS, avec rollback automatique, vérification d'intégrité et gestion centralisée des composants.

## Architecture

### 1. Auto-Updater (`auto_updater.py`)

Module autonome de gestion des mises à jour avec ~300 lignes de code.

#### Fonctionnalités principales

- **Vérification des releases**: Récupération via API GitHub (httpx async)
- **Comparaison sémantique**: Utilise `packaging.version` pour major.minor.patch
- **Téléchargement & Extraction**: ZIP depuis GitHub avec gestion des erreurs
- **Vérification d'intégrité**: SHA256 checksum validation
- **Sauvegardes automatiques**: Avant chaque mise à jour
- **Rollback intelligent**: Restauration automatique en cas d'erreur au démarrage
- **Parsing Changelog**: Extraction markdown → dict structuré
- **SQLite Logging**: Historique complet (version, date, status, rollback)
- **Mode Auto/Manuel**: Check automatique toutes les 6h ou à la demande
- **Gestion fichiers Windows**: Retry + reboot pour fichiers verrouillés

#### Classes

```python
VersionComparer        # Comparaison semver
ChangelogParser        # Parsing markdown
IntegrityChecker       # Vérification SHA256 async
BackupManager          # Gestion des sauvegardes
UpdateDatabase         # Logging SQLite
GitHubReleaseManager   # API GitHub
AutoUpdater            # Orchestrateur principal
```

#### Utilisation

```python
# Mode manuel
updater = AutoUpdater()
release = await updater.check_for_updates(force=True)
if release:
    success = await updater.perform_update(release)

# Mode automatique
await updater.enable_auto_updates()

# Historique
history = updater.get_history()
```

### 2. Version Manager (`version_manager.py`)

Gestion centralisée des versions et compatibilité (~250 lignes).

#### Fonctionnalités principales

- **Composants multi-niveaux**: core, plugins, models, configs
- **Changelog Generator**: Auto-génération depuis git log
- **Compatibility Matrix**: Règles de compatibilité entre composants
- **Migration Runner**: Exécution des scripts up/down
- **Feature Flags**: Activation par version
- **Health Checks**: Post-update verification
- **Export JSON**: Rapports structurés

#### Classes

```python
VersionDatabase        # Gestion SQLite
ChangelogGenerator     # Git log parsing
MigrationRunner        # Exécution migrations
FeatureFlagManager     # Gestion des flags
VersionManager         # Orchestrateur
```

#### Utilisation

```python
vm = VersionManager()
vm.initialize_components()
vm.setup_compatibility_matrix()

# Feature flags
vm.feature_flags.register_flag('new_ui', '10.5.0', True)
is_enabled = vm.feature_flags.is_enabled('new_ui', '10.6.0')

# Health check
health = vm.perform_health_check()

# Rapport
report = vm.export_version_json()
```

## Structure SQLite

### Table: updates
```sql
CREATE TABLE updates (
    id INTEGER PRIMARY KEY,
    version TEXT,
    update_date TIMESTAMP,
    status TEXT,           -- SUCCESS, FAILED_STARTUP, ERROR
    rollback BOOLEAN,      -- True si rollback effectué
    backup_path TEXT,
    changelog TEXT,
    notes TEXT
)
```

### Table: components
```sql
CREATE TABLE components (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    current_version TEXT,
    latest_version TEXT,
    type TEXT,             -- system, plugin, model, config
    installation_date TIMESTAMP,
    status TEXT            -- installed, update_available, incompatible
)
```

### Table: compatibility_matrix
```sql
CREATE TABLE compatibility_matrix (
    component_a TEXT,
    component_b TEXT,
    min_version_a TEXT,
    min_version_b TEXT,
    max_version_a TEXT,
    max_version_b TEXT,
    compatible BOOLEAN
)
```

### Table: feature_flags
```sql
CREATE TABLE feature_flags (
    name TEXT UNIQUE,
    enabled BOOLEAN,
    min_version TEXT,
    max_version TEXT,
    description TEXT,
    created_date TIMESTAMP
)
```

### Table: migrations
```sql
CREATE TABLE migrations (
    migration_name TEXT UNIQUE,
    version_from TEXT,
    version_to TEXT,
    executed BOOLEAN,
    execution_date TIMESTAMP,
    status TEXT            -- pending, success, failed
)
```

### Table: health_checks
```sql
CREATE TABLE health_checks (
    check_date TIMESTAMP,
    version TEXT,
    cpu_usage REAL,
    memory_usage REAL,
    disk_usage REAL,
    services_running INTEGER,
    errors_count INTEGER,
    status TEXT            -- healthy, degraded, unhealthy
)
```

## Configuration

Voir `config_example.json` pour un exemple complet:

```json
{
  "auto_updater": {
    "enabled": true,
    "check_interval_hours": 6,
    "auto_apply": false,
    "rollback_on_error": true
  },
  "github": {
    "repository": "turbONE/jarvis",
    "verify_ssl": true
  },
  "components": {
    "core": {"version": "10.6.0", "critical": true},
    "plugins": {"version": "2.1.0", "critical": false}
  },
  "machines": {
    "M1": {"host": "127.0.0.1", "port": 1234},
    "M2": {"host": "192.168.1.26", "port": 1234},
    "M3": {"host": "192.168.1.113", "port": 1234}
  }
}
```

## Flux de mise à jour

```
1. check_for_updates()
   └─> Récupère latest release via GitHub API
   └─> Compare versions (semver)
   └─> Retourne None ou release dict

2. perform_update(release)
   └─> Crée backup de la version actuelle
   └─> Télécharge ZIP depuis GitHub
   └─> Vérifie SHA256 (si présent)
   └─> Extrait dans dossier temporaire
   └─> Remplace les fichiers source
   └─> Test démarrage
   ├─> Si OK: logs "SUCCESS", cleanup
   └─> Si ERREUR: rollback, logs "FAILED_STARTUP"

3. Historique
   └─> Enregistré dans SQLite
   └─> Accessible via get_history()
   └─> Logs aussi dans fichier texte
```

## Flux de versioning

```
1. initialize_components()
   └─> Enregistre core, plugins, models, configs

2. setup_compatibility_matrix()
   └─> Définit règles d'incompatibilité

3. register_flag('feature_name', 'min_version', True)
   └─> Crée feature flag avec conditions

4. perform_health_check()
   └─> Vérifie fichiers critiques
   └─> Teste accès DB
   └─> Valide config JSON
   └─> Enregistre dans health_checks

5. export_version_json()
   └─> Exporte rapport en JSON
   └─> Inclut composants, flags, status
```

## Mode Auto (Background)

```python
updater = AutoUpdater()
await updater.enable_auto_updates()

# Lance une tâche async qui:
# - Attend CHECK_INTERVAL (6h)
# - Appelle check_for_updates()
# - Si nouvelle version: perform_update()
# - Boucle infinie jusqu'à disable_auto_updates()

updater.disable_auto_updates()  # Arrête la boucle
```

## Gestion des erreurs

### Rollback automatique
- Détecte erreur au démarrage
- Restaure backup automatiquement
- Logs status "FAILED_STARTUP"
- Notifie via Telegram (optionnel)

### Intégrité
- Vérification SHA256 du ZIP
- Valide structure fichiers
- Teste accès DB post-update

### Fichiers verrouillés (Windows)
- Utilise os.replace() avec retry
- Possible reboot si nécessaire
- Logs tentatives et résultat

## Logging

Trois niveaux:
1. **Auto-updater logs**: `/home/turbo/jarvis-m1-ops\logs\auto_updater.log`
2. **SQLite history**: `jarvis.db` table `updates`
3. **Console output**: INFO level par défaut

Format:
```
2026-03-04 14:23:45 [INFO] AutoUpdater: Vérification des mises à jour...
2026-03-04 14:23:47 [INFO] AutoUpdater: Nouvelle version disponible: v10.7.0
```

## Migration Scripts

Structure type pour `migrations/10.6.0_to_10.7.0.py`:

```python
def migrate_up():
    """Migrer de 10.6.0 à 10.7.0"""
    # Changements de schéma DB
    # Transformation de données
    # Mises à jour de config
    return True

def migrate_down():
    """Rollback de 10.7.0 à 10.6.0"""
    # Inverse des changements
    return True
```

## Dependencies

```
httpx==0.27.0          # Client HTTP async
aiofiles==23.2.1       # I/O async
packaging==24.0        # Semver comparison
```

## Exemples d'utilisation

Voir `example_usage.py` pour 8 exemples complets:

1. Mise à jour manuelle
2. Mises à jour automatiques
3. Consultation historique
4. Comparaison de versions
5. Version Manager
6. Monitoring composants
7. Génération Changelog
8. Workflow complet

## Statistiques

- **auto_updater.py**: ~478 lignes
- **version_manager.py**: ~607 lignes
- **Total**: ~1085 lignes (hors commentaires)
- **10 classes principales**
- **8 tables SQLite**
- **3 dépendances externes**

## Intégration JARVIS

### M1 (127.0.0.1:1234) - Primary
- Peut exécuter mises à jour
- Orchestre autres machines
- Logs historique centralisé

### M2 & M3 (Secondary)
- Reçoivent updates après M1
- Synchronisation via DB
- Health checks parallèles

## Prochaines étapes

- Intégration Telegram notifications
- Dashboard web pour monitoring
- API REST pour contrôle distant
- Support multi-machine (distribution)
- Signature des releases (optionnel)

## License

JARVIS v10.6.0 - Propriétaire
