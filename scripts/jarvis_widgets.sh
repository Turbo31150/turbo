#!/bin/bash
# JARVIS OS — Lancement des widgets Conky
# Usage: jarvis_widgets.sh [start|stop|restart]

CONKY_DIR="$HOME/.config/conky"
CONFIGS=("jarvis.conf" "jarvis-left.conf" "jarvis-bottom.conf")

case "${1:-start}" in
    start)
        # Tuer les anciens conky
        killall conky 2>/dev/null
        sleep 1
        # Lancer chaque widget
        for conf in "${CONFIGS[@]}"; do
            if [ -f "$CONKY_DIR/$conf" ]; then
                conky -c "$CONKY_DIR/$conf" -d &
                echo "Widget lancé: $conf"
                sleep 0.5
            fi
        done
        echo "$(pgrep -c conky) widgets JARVIS actifs"
        ;;
    stop)
        killall conky 2>/dev/null
        echo "Widgets JARVIS arrêtés"
        ;;
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        ;;
esac
