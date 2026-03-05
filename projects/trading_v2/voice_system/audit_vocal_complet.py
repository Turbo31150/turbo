"""
AUDIT COMPLET COCKPIT VOCAL V2 - Test exhaustif de toutes les capacites
Teste: Intent M2, latence, actions manquantes, controle Windows total
"""
import sys, os, time, json, requests

sys.path.insert(0, r'F:\BUREAU\TRADING_V2_PRODUCTION\voice_system')
sys.path.insert(0, r'F:\BUREAU\TRADING_V2_PRODUCTION\scripts')

M2_URL = "http://192.168.1.26:1234/v1/chat/completions"
M2_MODEL = "openai/gpt-oss-20b"

# Import commander pour le prompt systeme
from commander_v2 import analyze_intent_with_m2, local_fallback

# ============================================================
# CATEGORIES DE TESTS
# ============================================================

TESTS = {
    "TRADING": [
        ("Lance un scan du marche", "RUN_SCAN"),
        ("Demarre la pipeline 10 cycles", "RUN_PIPELINE"),
        ("Arme le trident", "RUN_TRIDENT"),
        ("Lance le sniper breakout", "RUN_SNIPER"),
        ("Surveille RIVER", "MONITOR_RIVER"),
        ("Donne-moi les positions", "STATUS_REPORT"),
        ("Stop tout urgence", "STOP_ALL"),
    ],
    "APPS": [
        ("Ouvre Chrome", "OPEN_APP"),
        ("Lance le bloc-notes", "OPEN_APP"),
        ("Ouvre le gestionnaire de taches", "OPEN_APP"),
        ("Lance l'explorateur de fichiers", "OPEN_APP"),
        ("Ouvre PowerShell", "OPEN_APP"),
        ("Lance Discord", "OPEN_APP"),
        ("Ouvre TradingView", "OPEN_APP"),
        ("Lance le terminal", "OPEN_APP"),
    ],
    "FENETRES": [
        ("Mets la fenetre a gauche", "SNAP_LEFT"),
        ("Fenetre a droite", "SNAP_RIGHT"),
        ("Maximise la fenetre", "MAXIMIZE"),
        ("Minimise ca", "MINIMIZE"),
        ("Ferme cette fenetre", "CLOSE_WINDOW"),
        ("Change de fenetre", "SWITCH_WINDOW"),
        ("Montre le bureau", "DESKTOP"),
    ],
    "NAVIGATION_WEB": [
        ("Va sur google.com", "OPEN_URL"),
        ("Ouvre youtube", "OPEN_URL"),
        ("Va sur le site de MEXC", "OPEN_URL"),
        ("Ouvre tradingview.com", "OPEN_URL"),
        ("Cherche bitcoin sur google", None),  # Complexe - peut-etre pas supporte
        ("Ouvre un nouvel onglet", None),       # Ctrl+T - manquant?
        ("Ferme l'onglet actuel", None),        # Ctrl+W - manquant?
        ("Onglet suivant", None),               # Ctrl+Tab - manquant?
        ("Onglet precedent", None),             # Ctrl+Shift+Tab - manquant?
        ("Actualise la page", None),            # F5 - manquant?
        ("Retour en arriere", None),            # Alt+Left - manquant?
    ],
    "SAISIE_TEXTE": [
        ("Ecris bonjour tout le monde", "TYPE_TEXT"),
        ("Tape Analyse du marche crypto 2026", "TYPE_TEXT"),
        ("Valide", "PRESS_ENTER"),
        ("Appuie sur Echap", None),             # PRESS_KEY esc
        ("Appuie sur la touche espace", None),  # PRESS_KEY space
        ("Efface tout", None),                  # Ctrl+A + Delete
        ("Retour arriere", None),               # Backspace
    ],
    "CLIPBOARD": [
        ("Copie ca", "COPY"),
        ("Colle ici", "PASTE"),
        ("Tout selectionner", "SELECT_ALL"),
        ("Annule", "UNDO"),
        ("Sauvegarde", "SAVE"),
        ("Couper", None),                       # CUT - dans os_pilot mais pas dans commander?
        ("Refaire", None),                      # REDO
        ("Rechercher", None),                   # FIND / Ctrl+F
    ],
    "SYSTEME": [
        ("Monte le volume", "VOLUME_UP"),
        ("Baisse le son", "VOLUME_DOWN"),
        ("Coupe le son", "VOLUME_MUTE"),
        ("Fais un screenshot", "SCREENSHOT"),
        ("Etat du systeme", "CHECK_SYSTEM"),
        ("Quel heure est-il", None),            # Non supporte
        ("Verrouille l'ecran", None),           # Win+L - manquant?
        ("Ouvre les parametres Windows", None),  # Win+I - manquant?
        ("Ouvre le panneau de notifications", None),  # Win+N - manquant?
        ("Affiche les bureaux virtuels", None),  # Win+Tab - manquant?
        ("Nouveau bureau virtuel", None),       # Win+Ctrl+D - manquant?
    ],
    "FICHIERS_DOSSIERS": [
        ("Ouvre le dossier Bureau", None),       # Explorer path
        ("Va dans le disque F", None),           # Explorer F:\
        ("Ouvre le dossier TRADING_V2", None),   # Explorer specific path
        ("Cree un nouveau dossier", None),       # Ctrl+Shift+N
        ("Renomme ce fichier", None),            # F2
        ("Supprime ce fichier", None),           # Delete
        ("Proprietes du fichier", None),         # Alt+Enter
    ],
    "SOURIS": [
        ("Clique", "CLICK"),
        ("Double-clique", "DOUBLE_CLICK"),
        ("Clic droit", "RIGHT_CLICK"),
        ("Descends la page", "SCROLL_DOWN"),
        ("Monte la page", "SCROLL_UP"),
        ("Deplace la souris en haut a droite", None),  # Move XY - manquant?
        ("Clique aux coordonnees 500 300", None),      # Click XY - manquant?
    ],
    "COMMANDES_COMPLEXES": [
        ("Ouvre Chrome et va sur google", None),         # Multi-action
        ("Copie tout et colle dans le bloc-notes", None),# Pipeline
        ("Fais un screenshot et envoie-le sur Telegram", None),  # Pipeline
        ("Analyse le BTC et dis-moi le prix", None),    # Trading + TTS
        ("Mets Chrome a gauche et TradingView a droite", None),  # Multi-fenetre
    ],
}

# ============================================================
# EXECUTION DES TESTS
# ============================================================

print("=" * 70)
print("  AUDIT COMPLET - COCKPIT VOCAL V2")
print("  Test de", sum(len(v) for v in TESTS.values()), "commandes")
print("=" * 70)

results = {
    "OK": [],           # M2 comprend et action existe
    "WRONG_INTENT": [], # M2 comprend mal
    "TIMEOUT": [],      # M2 ne repond pas a temps
    "MISSING": [],      # Action non supportee dans le systeme
    "PARTIAL": [],      # M2 comprend mais action incomplete
}

total_latency = 0
total_tests = 0

for category, commands in TESTS.items():
    print(f"\n{'='*70}")
    print(f"  CATEGORIE: {category}")
    print(f"{'='*70}")

    for cmd, expected in commands:
        total_tests += 1
        t0 = time.time()

        # Query M2
        intent = analyze_intent_with_m2(cmd)
        dt = time.time() - t0
        total_latency += dt

        action = intent.get("action", "UNKNOWN")
        params = intent.get("params", "")

        # Fallback local
        used_fallback = False
        if action == "UNKNOWN":
            fb = local_fallback(cmd)
            if fb:
                action = fb["action"]
                params = fb.get("params", "")
                used_fallback = True

        # Evaluer le resultat
        if expected is None:
            # Commande qu'on SAIT non supportee
            if action == "UNKNOWN":
                tag = "MISSING"
                results["MISSING"].append((category, cmd, action, params, dt))
            else:
                tag = "BONUS"  # M2 a trouve une action quand meme!
                results["OK"].append((category, cmd, action, params, dt))
        elif action == "UNKNOWN":
            tag = "TIMEOUT" if dt > 10 else "MISSING"
            results[tag].append((category, cmd, action, params, dt))
        elif expected and action == expected:
            tag = "OK"
            results["OK"].append((category, cmd, action, params, dt))
        elif expected and action != expected:
            # Verifier si c'est quand meme une action valide
            tag = "WRONG"
            results["WRONG_INTENT"].append((category, cmd, f"got={action} expected={expected}", params, dt))
        else:
            tag = "OK"
            results["OK"].append((category, cmd, action, params, dt))

        fb_tag = " [FB]" if used_fallback else ""
        print(f"  {tag:7s} | {dt:4.1f}s | {cmd:50s} -> {action}({params}){fb_tag}")

    # Pause entre categories pour ne pas surcharger M2
    time.sleep(1)

# ============================================================
# RAPPORT FINAL
# ============================================================

print("\n" + "=" * 70)
print("  RAPPORT D'AUDIT VOCAL")
print("=" * 70)

avg_lat = total_latency / total_tests if total_tests > 0 else 0
print(f"\n  Tests totaux:     {total_tests}")
print(f"  OK:               {len(results['OK'])} ({100*len(results['OK'])//total_tests}%)")
print(f"  Mauvais intent:   {len(results['WRONG_INTENT'])}")
print(f"  Timeout:          {len(results['TIMEOUT'])}")
print(f"  Non supporte:     {len(results['MISSING'])}")
print(f"  Latence moyenne:  {avg_lat:.1f}s")

if results["WRONG_INTENT"]:
    print(f"\n  --- INTENTS INCORRECTS ---")
    for cat, cmd, info, params, dt in results["WRONG_INTENT"]:
        print(f"  [{cat}] \"{cmd}\" -> {info}")

if results["MISSING"]:
    print(f"\n  --- ACTIONS MANQUANTES (a ajouter) ---")
    for cat, cmd, action, params, dt in results["MISSING"]:
        print(f"  [{cat}] \"{cmd}\"")

# Suggestions
print(f"\n{'='*70}")
print("  SUGGESTIONS D'AMELIORATION")
print(f"{'='*70}")

suggestions = [
    ("NAVIGATEUR", "Ajouter: NEW_TAB (Ctrl+T), CLOSE_TAB (Ctrl+W), NEXT_TAB (Ctrl+Tab), PREV_TAB (Ctrl+Shift+Tab), REFRESH (F5), BACK (Alt+Left), FORWARD (Alt+Right)"),
    ("FICHIERS", "Ajouter: OPEN_FOLDER (explorer path), NEW_FOLDER (Ctrl+Shift+N), RENAME (F2), DELETE (Delete), PROPERTIES (Alt+Enter)"),
    ("SYSTEME", "Ajouter: LOCK_SCREEN (Win+L), SETTINGS (Win+I), NOTIFICATIONS (Win+N), VIRTUAL_DESKTOPS (Win+Tab), NEW_DESKTOP (Win+Ctrl+D)"),
    ("SOURIS", "Ajouter: MOVE_MOUSE(x,y), CLICK_AT(x,y) pour controle positionnel"),
    ("MULTI-ACTION", "Ajouter: Pipeline de commandes sequentielles (ex: 'ouvre chrome ET va sur google')"),
    ("CLAVIER", "Ajouter: PRESS_KEY generique (esc, space, backspace, f1-f12, tab), HOTKEY generique (ctrl+t, ctrl+w, alt+left)"),
    ("SEARCH", "Ajouter: SEARCH_WEB (ouvrir navigateur + taper query), SEARCH_FILES (Win+S)"),
]

for name, desc in suggestions:
    print(f"\n  [{name}]")
    print(f"  {desc}")

print(f"\n{'='*70}")
print("  AUDIT TERMINE")
print(f"{'='*70}")
