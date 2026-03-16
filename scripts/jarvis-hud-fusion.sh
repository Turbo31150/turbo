#!/bin/bash
# JARVIS HUD Fusion Script
# Force Electron/Canvas to be the Desktop Layer

export TURBO_DIR="/home/turbo/jarvis-linux-repo"
cd "$TURBO_DIR/electron"

# Launch Electron with Super-User access and No Sandbox
sudo ELECTRON_DISABLE_SANDBOX=1 npm start -- --no-sandbox --disable-setuid-sandbox &

# Wait for window to appear
sleep 10

# Find JARVIS window and pin it to the desktop layer
WID=$(wmctrl -l | grep "JARVIS" | awk '{print $1}')
if [ ! -z "$WID" ]; then
    wmctrl -i -r $WID -b add,below
    wmctrl -i -r $WID -e 0,0,0,-1,-1
    # Make it sticky on all workspaces
    wmctrl -i -r $WID -b add,sticky
    echo "JARVIS Window $WID fused to desktop layer."
else
    echo "JARVIS Window not found for fusion."
fi
