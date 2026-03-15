#!/bin/bash
BACKUP_DIR="/home/turbo/jarvis/data/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

echo "[BACKUP] Starting JARVIS backup: $TIMESTAMP"
cp /home/turbo/jarvis/data/*.db "$BACKUP_DIR/"
cp /home/turbo/jarvis/.env "$BACKUP_DIR/env_backup_$TIMESTAMP"
cd "$BACKUP_DIR" && tar -czf "backup_$TIMESTAMP.tar.gz" *.db "env_backup_$TIMESTAMP"
rm *.db "env_backup_$TIMESTAMP"
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
echo "[BACKUP] Backup complete. Kept 7 days of history."
