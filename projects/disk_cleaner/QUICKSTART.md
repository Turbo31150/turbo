# 🚀 Quick Start - Disk Cleaner

## Installation (1 commande)

```bash
pip install tqdm
```

## Test Rapide (3 étapes)

### 1. Créer un environnement de test

```bash
python test_disk_cleaner.py
```

Cela crée automatiquement un dossier de test avec :
- 5 fichiers vides (score: 0)
- 6 fichiers temporaires (score: bas)
- 3 images (score: élevé)
- 3 documents (score: élevé)
- 3 fichiers de code (score: élevé)
- 3 doublons (score: bas)
- 2 fichiers anciens (score: bas)

### 2. Mode Simulation (Dry-Run)

```bash
python disk_cleaner.py "/Users\<user>\AppData\Local\Temp\disk_cleaner_test_XXXXX"
```

Remplacez le chemin par celui affiché à l'étape 1.

**Résultat attendu :**
- Scan de ~25 fichiers
- Scores calculés automatiquement
- Actions proposées (MAIS PAS EXÉCUTÉES)
- Statistiques détaillées

### 3. Mode Exécution (Modifications réelles)

```bash
python disk_cleaner.py "/Users\<user>\AppData\Local\Temp\disk_cleaner_test_XXXXX" --execute
```

**Résultat :**
- Fichiers score élevé → `Dossier_Trie/{Type}/{Année}/`
- Fichiers score moyen → `Dossier_Trie/_QUARANTINE/`
- Fichiers score bas → `Dossier_Trie/_TRASH/`

## Utilisation Réelle

### Scanner votre disque (Simulation)

```bash
python disk_cleaner.py "/Mes Documents"
```

### Exécuter réellement

```bash
python disk_cleaner.py "/Mes Documents" --execute
```

### Personnaliser les seuils

```bash
# Garder si score ≥70, trash si <20
python disk_cleaner.py "/Mes Documents" --keep 70 --trash 20
```

## Options Utiles

```bash
# Spécifier le dossier de sortie
python disk_cleaner.py "/Source" --output "D:\Trie"

# Mode silencieux
python disk_cleaner.py "/Source" --quiet

# Aide complète
python disk_cleaner.py --help
```

## Nettoyer les Tests

```bash
python test_disk_cleaner.py --cleanup
```

## 📊 Comprendre les Scores

| Score | Action | Exemples |
|-------|--------|----------|
| **80-100** | ✅ Garder | Images HD, code récent, documents importants |
| **60-79** | ✅ Garder | Documents, images moyennes |
| **30-59** | ⚠️ Quarantaine | Fichiers moyens, à valider |
| **0-29** | 🗑️ Trash | Vides, tmp, logs anciens, doublons |

## 🗄️ Consulter la Base de Données

```bash
sqlite3 disk_cleaner.db

# Voir les fichiers avec score bas
SELECT name, score FROM files WHERE score < 30;

# Voir les doublons
SELECT name, duplicate_of FROM files WHERE is_duplicate = 1;

# Statistiques
SELECT extension, COUNT(*), AVG(score) FROM files GROUP BY extension;
```

## ⚠️ Important

1. **Testez TOUJOURS en mode Dry-Run d'abord**
2. **Vérifiez la quarantaine** avant de supprimer
3. **Sauvegardez vos données importantes**

## 🐛 Problèmes Courants

### "Permission denied"
→ Certains fichiers système sont protégés (normal, le script continue)

### Fichiers trop gros ignorés
→ Par défaut, limite à 100 MB. Modifiez `max_file_size` dans le code

### Base de données verrouillée
```bash
rm disk_cleaner.db
python disk_cleaner.py /mon/dossier
```

## 📚 Documentation Complète

Voir `README.md` pour :
- Architecture détaillée
- Critères de scoring
- Configuration avancée
- Cas d'usage

---

**Profitez d'un disque propre ! 🎉**
