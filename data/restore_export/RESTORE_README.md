# JARVIS System Restore

Generated: 2026-03-07 15:44:17
Source: jarvis.db

## Contents

| File | Description |
|------|-------------|
| restore.sh | Full restore script (pip + configs + schemas) |
| *.json | Individual config entries |

## Quick Restore

```bash
cd F:/BUREAU/turbo
bash restore/restore.sh
# Then fill in .env.restore with your secrets and rename to .env
```

## Manual Restore

1. Copy database files to their paths
2. Run `pip install -r requirements.txt`
3. Fill in `.env` with your API keys
4. Run `python scripts/restore_system.py --check data/jarvis.db`

## Stored Config: 37 entries
