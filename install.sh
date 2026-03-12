#!/bin/bash
set -e

echo "🔥 [JARVIS-TURBO] Initialisation du déploiement automatique..."

PROJECT_DIR="/home/turbo/jarvis-m1-ops"
cd "$PROJECT_DIR"

# 1. Vérification Python & Venv
if [ ! -d ".venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv .venv
fi

# 2. Installation des dépendances via uv (si possible) ou pip
source .venv/bin/activate
if command -v uv >/dev/null 2>&1; then
    echo "⚡ Utilisation de 'uv' pour une installation ultra-rapide..."
    uv pip install requests psutil websockets flask flask-cors python-dotenv faster-whisper openwakeword onnxruntime-gpu
else
    echo "🐍 Installation via pip..."
    pip install requests psutil websockets flask flask-cors python-dotenv faster-whisper openwakeword onnxruntime-gpu
fi

# 3. Initialisation de la mémoire SQL
echo "💾 Initialisation de la couche mémoire..."
python3 -c "import sqlite3; conn=sqlite3.connect('memory/long_term.db'); conn.execute('CREATE TABLE IF NOT EXISTS memory (timestamp TEXT, category TEXT, content TEXT)'); conn.commit(); conn.close()"

# 4. Vérification Hardware
echo "🖥️ Audit Hardware rapide..."
nvidia-smi -L || echo "⚠️ Aucun GPU détecté ou driver manquant."
zramctl || echo "⚠️ ZRAM non configuré."

# 5. Services Systemd
echo "⚙️ Configuration des services JARVIS..."
mkdir -p systemd
# Le lien vers ~/.config/systemd/user/ est déjà géré par la Target globale

echo "✅ [JARVIS-TURBO] Déploiement terminé. Prêt pour orchestration v3.0."
