@echo off
TITLE VOICE COMMANDER V2 - TRADING AI
color 0A
echo ==================================================
echo    ACTIVATION DU CONTROLE VOCAL - TRADING V2
echo ==================================================
echo.
echo  1. Connexion au Cluster M2 (GPT-OSS-20B)...
echo  2. Initialisation TTS Windows...
echo  3. Chargement OS Pilot...
echo.
echo  Commandes disponibles:
echo    Trading: scan, pipeline, trident, sniper, river, status, stop
echo    Windows: ouvre [app], gauche, droite, ferme, bureau, volume
echo    Saisie:  ecris [texte], screenshot, capture
echo.
echo  Securite: Souris dans un coin = STOP immediat
echo ==================================================
echo.

cd /d F:\BUREAU\TRADING_V2_PRODUCTION\voice_system
python commander_v2.py

pause
