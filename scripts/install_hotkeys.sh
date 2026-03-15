#!/bin/bash
# Installation des raccourcis clavier globaux JARVIS via gsettings/dconf
# Idempotent : peut etre relance sans probleme
# Methode GNOME native via custom-keybindings dans dconf

set -euo pipefail

JARVIS_HOME="/home/turbo/jarvis"
SKILL_SCRIPT="${JARVIS_HOME}/scripts/execute_skill.sh"

echo "=== JARVIS Hotkey Installer ==="
echo "Installation des raccourcis clavier globaux..."

# Verifier que le script execute_skill.sh est executable
chmod +x "$SKILL_SCRIPT"

# Chemin de base pour les custom keybindings GNOME
KEYBINDING_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

# Definition des raccourcis : nom|commande|binding
declare -a HOTKEYS=(
    "JARVIS Rapport Systeme|${SKILL_SCRIPT} rapport_systeme_linux|<Super>1"
    "JARVIS Maintenance Complete|${SKILL_SCRIPT} maintenance_complete_linux|<Super>2"
    "JARVIS Diagnostic Reseau|${SKILL_SCRIPT} diagnostic_reseau_linux|<Super>3"
    "JARVIS Cluster Check|${SKILL_SCRIPT} cluster_check_linux|<Super>4"
    "JARVIS Mode Dev|${SKILL_SCRIPT} mode_dev_linux|<Super>5"
    "JARVIS Doc Vocale|xdg-open ${JARVIS_HOME}/docs/voice_commands_reference.html|<Super>F1"
    "JARVIS Dashboard|xdg-open http://127.0.0.1:8088|<Super>F2"
    "JARVIS Nettoyage Profond|${SKILL_SCRIPT} nettoyage_profond_linux|<Super>F5"
    "JARVIS Self Diagnostic|${SKILL_SCRIPT} jarvis_self_diagnostic|<Super>F12"
    "JARVIS Focus Mode|${SKILL_SCRIPT} focus_mode_linux|<Super>Escape"
)

# Prefix pour les custom keybindings JARVIS (custom100-custom109)
CUSTOM_START=100

echo "Enregistrement de ${#HOTKEYS[@]} raccourcis clavier..."

# Recuperer les keybindings existants et fusionner
EXISTING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "@as []")

# Construire la liste des chemins de nos raccourcis
OUR_PATHS=""
for i in "${!HOTKEYS[@]}"; do
    CUSTOM_NUM=$((CUSTOM_START + i))
    OUR_PATHS="${OUR_PATHS}'${KEYBINDING_PATH}/custom${CUSTOM_NUM}/', "
done

# Recuperer la liste existante, nettoyer les anciens JARVIS, ajouter les notres
EXISTING_CLEAN=$(echo "$EXISTING" | sed "s/@as //g" | tr -d "[]' " | tr ',' '\n' | grep -v "^$" | grep -v "/custom1[0-9][0-9]/" || true)

# Reconstruire la liste complete
ALL_PATHS=""
# Ajouter les existants (sans les custom100+)
while IFS= read -r line; do
    if [ -n "$line" ]; then
        ALL_PATHS="${ALL_PATHS}'${line}', "
    fi
done <<< "$EXISTING_CLEAN"

# Ajouter nos raccourcis
for i in "${!HOTKEYS[@]}"; do
    CUSTOM_NUM=$((CUSTOM_START + i))
    ALL_PATHS="${ALL_PATHS}'${KEYBINDING_PATH}/custom${CUSTOM_NUM}/', "
done

# Retirer la virgule finale et formatter
ALL_PATHS=$(echo "$ALL_PATHS" | sed 's/, $//')
FINAL_LIST="[${ALL_PATHS}]"

# Enregistrer la liste des keybindings
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$FINAL_LIST"

# Configurer chaque raccourci
for i in "${!HOTKEYS[@]}"; do
    IFS='|' read -r NAME COMMAND BINDING <<< "${HOTKEYS[$i]}"
    CUSTOM_NUM=$((CUSTOM_START + i))
    SCHEMA="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
    PATH_KEY="${KEYBINDING_PATH}/custom${CUSTOM_NUM}/"

    gsettings set "${SCHEMA}:${PATH_KEY}" name "$NAME"
    gsettings set "${SCHEMA}:${PATH_KEY}" command "$COMMAND"
    gsettings set "${SCHEMA}:${PATH_KEY}" binding "$BINDING"

    echo "  [OK] ${BINDING} → ${NAME}"
done

echo ""
echo "=== Raccourcis installes ==="
echo ""
echo "Raccourcis actifs :"
echo "  Super+1    → Rapport systeme Linux"
echo "  Super+2    → Maintenance complete Linux"
echo "  Super+3    → Diagnostic reseau Linux"
echo "  Super+4    → Cluster check Linux"
echo "  Super+5    → Mode dev Linux"
echo "  Super+F1   → Documentation vocale HTML"
echo "  Super+F2   → Dashboard web (port 8088)"
echo "  Super+F5   → Nettoyage profond Linux"
echo "  Super+F12  → Self diagnostic JARVIS"
echo "  Super+Esc  → Mode focus (DND)"
echo ""
echo "Raccourcis pre-existants (non modifies) :"
echo "  Super+J    → Pipeline vocal"
echo "  Super+G    → GPU monitor"
echo ""
echo "Logs : ${JARVIS_HOME}/logs/hotkey_skills.log"
echo "=== Installation terminee ==="

rm -f /tmp/jarvis_keybindings.txt
