#!/bin/bash
echo "⚠️ SECURE BOOT DÉTECTÉ ⚠️"
echo "Pour charger le module emuV (VRAM étendue), vous devez autoriser sa signature."
echo "Un mot de passe va vous être demandé (mettez 'jarvis' par exemple)."
echo "Au prochain redémarrage, un écran bleu (MOKManager) apparaîtra :"
echo "1. Choisissez 'Enroll MOK'"
echo "2. Choisissez 'Continue'"
echo "3. Entrez le mot de passe que vous allez taper maintenant"
echo "4. Choisissez 'Reboot'"
echo ""
sudo mokutil --import /opt/emuV/keys/MOK.der
