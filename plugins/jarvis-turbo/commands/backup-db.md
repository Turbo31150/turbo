---
name: backup-db
description: Backup des bases de donnees JARVIS (etoile.db, trading.db, jarvis.db)
---

Lance un backup des bases de donnees critiques JARVIS.

## Execution

```bash
python3 -c "
import shutil, datetime, os
ts = datetime.datetime.now().strftime('%Y-%m-%d_%H%M')
backups = [
    ('F:/BUREAU/etoile.db', f'F:/BUREAU/backups/etoile_backup_{ts}.db'),
    ('F:/BUREAU/carV1/database/trading_latest.db', f'F:/BUREAU/carV1/backups/trading_backup_{ts}.db'),
    ('F:/BUREAU/turbo/data/jarvis.db', f'F:/BUREAU/turbo/data/backups/jarvis_backup_{ts}.db'),
]
for src, dst in backups:
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        size = os.path.getsize(dst) / (1024*1024)
        print(f'OK: {os.path.basename(src)} -> {dst} ({size:.1f} MB)')
    else:
        print(f'SKIP: {src} (non trouve)')
" 2>&1
```

Affiche le resultat de chaque backup avec la taille des fichiers.
