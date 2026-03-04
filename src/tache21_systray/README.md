# JARVIS Tache 21: System Tray & Notification Manager

## Vue d'ensemble

Système complet de system tray Windows 10/11 pour JARVIS v10.6 avec:
- Icône dynamique (vert/orange/rouge)
- Notifications natives temps réel
- Monitoring cluster et trading
- Export Telegram
- Persistence SQLite
- WebSocket événementiel

## Architecture

### Fichiers principaux

- **systray_manager.py** (497 lignes)
  - Gestion du system tray
  - Icônes dynamiques avec PIL
  - Menu contextuel avec 5 options
  - Écoute WebSocket temps réel
  - Throttling anti-spam (30s par catégorie)

- **notification_center.py** (484 lignes)
  - Centre de notifications asynchrone
  - Queue prioritaire (CRITICAL > HIGH > NORMAL > LOW)
  - Filtrage par catégorie
  - TTL automatique (300s par défaut)
  - Export Telegram async
  - Historique SQLite

- **__init__.py**
  - Exports principaux
  - Version 1.0.0

- **config.example.py**
  - Configurations complètes
  - Thresholds d'alerte
  - Préférences par défaut

- **main.py**
  - Point d'entrée
  - Setup logging

## Installation

```bash
# 1. Créer l'environnement
python -m venv venv
.\venv\Scripts\activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Copier la config
cp config.example.py config.py
# Adapter config.py vos besoins
```

## Utilisation

### Démarrage basique

```bash
python main.py
```

### Usage en Python

```python
from systray_manager import TrayManager
from notification_center import NotificationCenter, NotificationPriority

# Tray Manager
manager = TrayManager()
manager.run()

# Ou Notification Center seul
import asyncio

async def demo():
    center = NotificationCenter()
    
    await center.add_notification(
        title="GPU Alert",
        message="Temperature: 85°C",
        category="cluster",
        level="WARNING",
        priority=NotificationPriority.HIGH.value
    )
    
    notif = await center.get_next_notification()
    print(f"Notification: {notif.title}")
    
    stats = await center.get_stats()
    print(f"Stats: {stats}")

asyncio.run(demo())
```

## Features détaillées

### System Tray

**Menu contextuel:**
- 📊 Cluster Status (nodes actifs/total)
- 💰 Trading Status (signaux en attente)
- 🔥 GPU Monitor (temp et utilisation)
- 🎤 Voice Toggle (ON/OFF)
- ─────── Separator
- Quit JARVIS

**Icône dynamique:**
- Vert (cercle): Status = OK
- Orange (cercle): WARNING (temp > 70°C ou < 5 nodes)
- Rouge (cercle): CRITICAL (temp > 80°C)

**Tooltip:**
```
JARVIS v10.6
5/6 nodes
GPU 45°C (60%)
RAM 12.5GB/24.0GB
Models: 8
Status: OK
```

### Notifications

**Niveaux:**
- INFO: Bulle grise (5s timeout)
- WARNING: Bulle orange (10s timeout)
- CRITICAL: Popup rouge + Telegram (non-bloquant)

**Anti-spam:**
- Max 1 notification/30s par catégorie
- Historique SQLite complet
- TTL configurable par notification

**Queue prioritaire:**
```python
CRITICAL (priority=0) → HIGH → NORMAL → LOW
```

### Catégories

```python
CLUSTER = "cluster"      # Events cluster/GPU
TRADING = "trading"      # Signaux trading
VOICE = "voice"         # Commandes vocales
SYSTEM = "system"       # Système général
ERROR = "error"         # Erreurs
```

### WebSocket

**Écoute sur:** `ws://127.0.0.1:9742`

**Format événement:**
```json
{
  "type": "cluster_update",
  "category": "cluster",
  "level": "WARNING",
  "title": "GPU Temperature",
  "message": "GPU temp: 75°C",
  "nodes_active": 5,
  "gpu_temp": 75.0,
  "gpu_utilization": 65.0,
  "notification": true
}
```

**Reconnexion automatique:**
- Exponential backoff (2^n, max 30s)
- Max 5 tentatives
- Ping/Pong tous les 20s

### Base de données

**Tables SQLite (jarvis.db):**

```sql
-- Préférences
CREATE TABLE preferences (
  id TEXT PRIMARY KEY,
  value TEXT,
  updated_at TIMESTAMP
)

-- Notifications
CREATE TABLE notifications (
  id INTEGER PRIMARY KEY,
  timestamp TIMESTAMP,
  level TEXT,
  category TEXT,
  title TEXT,
  message TEXT,
  priority INTEGER,
  ttl_seconds INTEGER,
  read INTEGER,
  sent_to_telegram INTEGER
)

-- Filtres
CREATE TABLE notification_filters (
  id TEXT PRIMARY KEY,
  category TEXT,
  enabled INTEGER,
  min_level TEXT
)
```

### Telegram Integration

**Configuration (config.py):**
```python
TELEGRAM_CONFIG = {
    "enabled": True,
    "token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "chat_id": "987654321",
    "export_critical_only": True
}
```

**Format message:**
```
🚨 GPU Temperature Alert
Category: cluster
Level: CRITICAL
─────────────────
GPU temperature reached 85°C
2026-03-04T14:23:15
```

## Configuration

### Copier et adapter `config.example.py`

```python
# WS_CONFIG
WS_CONFIG = {
    "host": "127.0.0.1",
    "port": 9742,
}

# ALERT_THRESHOLDS
ALERT_THRESHOLDS = {
    "gpu_temp_critical": 80,
    "min_nodes_active": 5,
}

# TELEGRAM_CONFIG
TELEGRAM_CONFIG = {
    "enabled": True,
    "token": "YOUR_TOKEN",
    "chat_id": "YOUR_CHAT_ID",
}
```

## Logging

**Fichiers log:**
- `F:/BUREAU/turbo/logs/tray.log` - System tray
- `F:/BUREAU/turbo/logs/notifications.log` - Notifications

**Level:** INFO

**Format:**
```
2026-03-04 14:23:15,123 - systray_manager - INFO - WebSocket connected
```

## Performance

- Threading asynchrone pour WebSocket
- Queue prioritaire O(n) à l'insertion
- Throttling par catégorie
- TTL auto-cleanup
- SQLite pour persistence

**Empreinte mémoire:**
- Base: ~50MB
- +10MB par 1000 notifications en queue

## Troubleshooting

### WebSocket ne se connecte pas
```
1. Vérifier que le serveur écoute sur 127.0.0.1:9742
2. Check firewall Windows
3. Logs: F:/BUREAU/turbo/logs/tray.log
```

### Notifications ne s'affichent pas
```
1. Vérifier notification_enabled = True
2. Check Windows Focus Assist settings
3. Vérifier plyer avec: python -c "from plyer import notification; notification(...)"
```

### Icône ne change pas
```
1. Les updates se font toutes les 5s
2. Check GPU temp updates via WebSocket
3. Forcer update: Quit et relancer
```

## Améliorations futures

- [ ] Tray menu avec sous-menus
- [ ] Sound alerts pour CRITICAL
- [ ] Desktop notifications avec actions
- [ ] Analytics sur fréquence alertes
- [ ] Multi-language support
- [ ] Custom icon themes
- [ ] Scheduling notifications
- [ ] Rate limiting dynamique

## Stats du code

| Métrique | Valeur |
|----------|--------|
| Total lignes | 981 |
| systray_manager.py | 497 |
| notification_center.py | 484 |
| Classes | 15+ |
| Fonctions async | 20+ |
| Error handling | Complet |

## Licence

JARVIS v10.6 - Propriétaire turbONE
