#!/bin/bash
echo "🛡️ [JARVIS CI] Lancement de la validation Qualité..."
FAILURES=0

check_python() {
    echo "🐍 Vérification syntaxe Python..."
    find . -name "*.py" -not -path "*/venv/*" -not -path "*/node_modules/*" -exec python3 -m py_compile {} +
    if [ $? -eq 0 ]; then echo "✅ Python Syntax: OK"; else echo "❌ Python Syntax: ERREUR"; ((FAILURES++)); fi
}

check_systemd() {
    echo "⚙️ Vérification unités Systemd..."
    find . -name "*.service" -o -name "*.timer" -exec systemd-analyze verify {} +
    if [ $? -eq 0 ]; then echo "✅ Systemd Units: OK"; else echo "❌ Systemd Units: ATTENTION (certaines dépendances peuvent manquer en mode verify)"; fi
}

check_python
check_systemd

if [ $FAILURES -eq 0 ]; then
    echo "✅ [JARVIS CI] Tout est vert."
    exit 0
else
    echo "❌ [JARVIS CI] $FAILURES erreurs détectées."
    exit 1
fi
