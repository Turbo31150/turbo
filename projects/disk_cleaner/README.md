# 🧹 Disk Cleaner - Nettoyage et Organisation Intelligente

Script Python robuste et modulaire pour nettoyer, organiser et dédoublonner un disque dur avec système de **scoring de pertinence**.

## 🎯 Fonctionnalités

### ✅ Analyse Profonde & Dédoublonnage
- Scan récursif de dossiers
- Détection de doublons par **hash SHA-256** (contenu réel)
- Pas de faux positifs basés sur le nom

### 📊 Système de Scoring (0-100)
Le script analyse chaque fichier et lui attribue un **score de pertinence** :

**Critères de notation :**
- ✅ **Score élevé (60-100)** : Fichiers à garder
  - Images haute résolution
  - Documents récents
  - Code source bien formaté
  - Fichiers volumineux importants

- ⚠️ **Score moyen (30-59)** : Quarantaine (validation manuelle)
  - Fichiers moyennement pertinents
  - Documents anciens mais non vides

- 🗑️ **Score faible (0-29)** : À supprimer
  - Fichiers vides ou corrompus
  - Fichiers temporaires (.tmp, .log anciens)
  - Doublons
  - Fichiers suspects (backup, old, copy)

### 💾 Persistance & Mémoire (SQLite)
- Base de données SQLite pour sauvegarder tous les fichiers analysés
- Mémorisation des décisions (garder, supprimer, quarantaine)
- Re-scan optimisé : si un fichier a déjà été noté, action immédiate

### 📁 Organisation Automatique
Structure propre générée automatiquement :
```
Dossier_Trie/
├── Images/
│   ├── 2024/
│   ├── 2025/
│   └── 2026/
├── Documents/
│   └── 2026/
├── Code/
│   └── 2026/
├── Videos/
├── Audio/
├── Archives/
├── Autres/
├── _QUARANTINE/    # Score moyen (30-59)
└── _TRASH/         # Score faible (<30)
```

### 🛡️ Sécurité & UX
- ✅ **Mode Dry-Run (Simulation)** activé par défaut
- ✅ Barre de progression visuelle (tqdm)
- ✅ Gestion d'erreurs complète (try/except)
- ✅ Pas de plantage si fichiers système verrouillés
- ✅ Conflits de noms gérés automatiquement

### 🏗️ Architecture Orientée Objet
- `FileScanner` : Scan récursif et détection doublons
- `ScoreEngine` : Attribution des scores
- `ActionManager` : Organisation et déplacement
- `DatabaseManager` : Persistance SQLite
- Code commenté en français

## 🚀 Installation

```bash
# Cloner ou télécharger le script
cd F:\BUREAU\disk_cleaner

# Installer les dépendances
pip install -r requirements.txt
```

Dépendances : `tqdm` (barre de progression)

## 📖 Utilisation

### Mode Simulation (Dry-Run) - Par défaut

```bash
# Scanner un dossier (aucune modification réelle)
python disk_cleaner.py "C:\Mes Documents"
```

### Mode Exécution (Modifications réelles)

```bash
# Exécuter réellement les actions
python disk_cleaner.py "C:\Mes Documents" --execute
```

### Options Avancées

```bash
# Personnaliser les seuils de score
python disk_cleaner.py "C:\Mes Documents" --keep 70 --trash 20

# Spécifier le dossier de sortie
python disk_cleaner.py "C:\Mes Documents" --output "D:\Fichiers_Tries"

# Mode silencieux
python disk_cleaner.py "C:\Mes Documents" --quiet

# Spécifier la base de données
python disk_cleaner.py "C:\Mes Documents" --db "./ma_base.db"
```

### Aide Complète

```bash
python disk_cleaner.py --help
```

## 📊 Workflow Complet

### Étape 1 : Scan et Détection de Doublons
- Scan récursif du dossier source
- Calcul du hash SHA-256 pour chaque fichier
- Détection des doublons (même contenu)
- Barre de progression en temps réel

### Étape 2 : Attribution des Scores
- Analyse de chaque fichier selon 6 critères :
  1. **Taille** : Fichiers vides = 0, volumineux = bonus
  2. **Type MIME** : Images HD, documents, code source = bonus
  3. **Ancienneté** : Récents (<30j) = bonus, anciens (>1an) = malus
  4. **Extension** : .tmp, .log anciens = malus fort
  5. **Doublons** : -30 points
  6. **Nom** : "temp", "backup", "copy" = malus
- Score final : 0-100
- Sauvegarde en base de données

### Étape 3 : Organisation
- **Score ≥60** : Déplacement vers structure organisée (Type/Année/)
- **Score 30-59** : Quarantaine (_QUARANTINE/)
- **Score <30** : Poubelle (_TRASH/)
- Statistiques finales complètes

## 📊 Exemple de Sortie

```
==================================================================
🧹 DISK CLEANER - Nettoyage et Organisation Intelligente
==================================================================

📂 Répertoire source: C:\Mes Documents
🎯 Mode: DRY-RUN (Simulation)
📊 Seuils: Garder ≥60, Trash <30

==================================================================
ÉTAPE 1/3 : SCAN ET DÉTECTION DE DOUBLONS
==================================================================

🔍 Scan du répertoire: C:\Mes Documents
📁 Nombre de fichiers détectés: 1523
Scan en cours: 100%|████████████████| 1523/1523 [00:12<00:00, 125.2 fichier/s]
✅ Scan terminé: 1523 fichiers analysés

==================================================================
ÉTAPE 2/3 : ATTRIBUTION DES SCORES
==================================================================

Calcul des scores: 100%|█████████████| 1523/1523 [00:03<00:00, 456.8 fichier/s]

==================================================================
ÉTAPE 3/3 : ORGANISATION DES FICHIERS
==================================================================

Organisation: 100%|████████████████| 1523/1523 [00:01<00:00, 892.3 fichier/s]

==================================================================
📊 STATISTIQUES FINALES
==================================================================

📁 Fichiers analysés: 1523
🔄 Doublons détectés: 234
💾 Espace total: 3.47 GB

📈 Distribution des scores:
   ✅ Score élevé (≥60): 892 fichiers
   ⚠️  Score moyen (30-59): 398 fichiers
   🗑️  Score faible (<30): 233 fichiers

🎯 Actions effectuées:
   📁 Déplacés: 892
   ⚠️  Quarantaine: 398
   🗑️  Poubelle: 233
   ❌ Erreurs: 0

⚠️  MODE DRY-RUN: Aucune modification réelle effectuée.
   Pour exécuter réellement, relancez avec --execute

==================================================================

✅ Nettoyage terminé.
```

## 🗄️ Base de Données SQLite

### Tables

1. **files** : Tous les fichiers analysés
   - path, name, size, extension, mime_type
   - hash_sha256 (pour dédoublonnage)
   - score, score_reasons (JSON)
   - is_duplicate, duplicate_of
   - timestamps (created, modified, scanned)

2. **decisions** : Log de toutes les décisions
   - file_id, action (MOVED, QUARANTINE, TRASH)
   - reason, executed, executed_at

### Consulter la Base

```bash
# Ouvrir la base de données
sqlite3 disk_cleaner.db

# Voir les fichiers avec score faible
SELECT name, size, score FROM files WHERE score < 30 ORDER BY score;

# Voir les doublons
SELECT name, size, duplicate_of FROM files WHERE is_duplicate = 1;

# Statistiques par extension
SELECT extension, COUNT(*), AVG(score)
FROM files
GROUP BY extension
ORDER BY COUNT(*) DESC;
```

## 🔧 Configuration Avancée

Modifier `Config` dans le script pour personnaliser :

```python
@dataclass
class Config:
    # Seuils de scoring
    score_threshold_keep: int = 60  # Garder si ≥60
    score_threshold_trash: int = 30  # Trash si <30

    # Comportement
    dry_run: bool = True  # Mode simulation
    organize_by_year: bool = True  # Organisation par année
    organize_by_type: bool = True  # Organisation par type

    # Performance
    chunk_size: int = 8192  # Taille chunks lecture
    max_file_size: int = 100 * 1024 * 1024  # 100 MB max
```

## ⚠️ Avertissements

1. **Testez d'abord en mode Dry-Run** :
   ```bash
   python disk_cleaner.py /mon/dossier
   ```

2. **Vérifiez la quarantaine** avant de supprimer :
   - Les fichiers en quarantaine (_QUARANTINE) nécessitent validation manuelle
   - Vérifiez le contenu avant de supprimer

3. **Sauvegardez vos données importantes** :
   - Faites une sauvegarde avant d'exécuter en mode --execute
   - Le script ne peut pas récupérer les fichiers supprimés

4. **Permissions** :
   - Certains fichiers système peuvent être verrouillés
   - Le script gère les erreurs sans planter

## 🎓 Cas d'Usage

### Nettoyage de disque saturé
```bash
python disk_cleaner.py "C:\" --execute --trash 20
```

### Organisation photos
```bash
python disk_cleaner.py "D:\Photos" --execute --keep 50
```

### Suppression des doublons
```bash
# 1. Mode simulation pour voir les doublons
python disk_cleaner.py "C:\Documents"

# 2. Exécution réelle
python disk_cleaner.py "C:\Documents" --execute
```

### Nettoyage de vieux logs
```bash
python disk_cleaner.py "C:\Logs" --execute --trash 40
```

## 🐛 Troubleshooting

### Erreur "Permission denied"
- Certains fichiers système sont protégés
- Le script continue sans planter
- Les erreurs sont comptabilisées dans les stats

### Fichiers non détectés
- Vérifiez que `max_file_size` est suffisant (défaut: 100 MB)
- Les fichiers trop gros sont ignorés par défaut

### Base de données verrouillée
```bash
# Fermer les connexions ouvertes
rm disk_cleaner.db
python disk_cleaner.py /mon/dossier
```

## 📝 Licence

Ce script est fourni "tel quel" sans garantie.
Utilisez-le à vos propres risques.

## 👨‍💻 Auteur

**Claude Code** - Architecte Logiciel Senior
- Spécialisation : Python, Automatisation, File System Management
- Date : 2026-02-03
- Version : 1.0.0

## 🔄 Améliorations Futures

- [ ] Support multi-threading pour scan plus rapide
- [ ] Interface graphique (GUI) optionnelle
- [ ] Export statistiques en CSV/JSON
- [ ] Scoring basé sur Machine Learning
- [ ] Support cloud storage (Google Drive, Dropbox)
- [ ] Scheduling automatique (cron jobs)

---

**Profitez d'un disque propre et organisé ! 🎉**
