#!/usr/bin/env python3
"""
Insertion de 200 corrections vocales pour améliorer la reconnaissance Whisper en français.
Catégories : homophones, applications, termes IA/cluster, commandes système,
phrases complètes, chiffres/unités, noms propres JARVIS.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jarvis.db")

# --- 1. Homophones français (50) ---
homophones = [
    ("et teint", "éteint"),
    ("et teins", "éteins"),
    ("et tein", "éteint"),
    ("fer mé", "ferme"),
    ("fer me", "ferme"),
    ("fair me", "ferme"),
    ("ou vr", "ouvre"),
    ("ou vre", "ouvre"),
    ("mais a jour", "mets à jour"),
    ("met a jour", "mets à jour"),
    ("mais à jour", "mets à jour"),
    ("ré démare", "redémarre"),
    ("re démare", "redémarre"),
    ("redémar", "redémarre"),
    ("re de marre", "redémarre"),
    ("allume", "allume"),
    ("a lume", "allume"),
    ("a rrête", "arrête"),
    ("arrêt", "arrête"),
    ("aret", "arrête"),
    ("supprime", "supprime"),
    ("su prime", "supprime"),
    ("su prim", "supprime"),
    ("in stalle", "installe"),
    ("in stal", "installe"),
    ("dés installe", "désinstalle"),
    ("des installe", "désinstalle"),
    ("dé connecte", "déconnecte"),
    ("de connecte", "déconnecte"),
    ("re connecte", "reconnecte"),
    ("ré connecte", "reconnecte"),
    ("affiche", "affiche"),
    ("a fiche", "affiche"),
    ("cher che", "cherche"),
    ("re cherche", "recherche"),
    ("ex écute", "exécute"),
    ("éxécute", "exécute"),
    ("télé charge", "télécharge"),
    ("tele charge", "télécharge"),
    ("télé charger", "télécharge"),
    ("con figure", "configure"),
    ("con figurer", "configure"),
    ("véri fie", "vérifie"),
    ("veri fit", "vérifie"),
    ("vérifi", "vérifie"),
    ("net toi", "nettoie"),
    ("net toie", "nettoie"),
    ("net oie", "nettoie"),
    ("re lance", "relance"),
    ("ré initialise", "réinitialise"),
]

# --- 2. Noms d'applications mal transcrits (30) ---
applications = [
    ("vé esse code", "vscode"),
    ("vie esse code", "vscode"),
    ("v s code", "vscode"),
    ("spoty faille", "spotify"),
    ("spot y faille", "spotify"),
    ("dis cord", "discord"),
    ("disse corde", "discord"),
    ("libre office", "libreoffice"),
    ("libre ofice", "libreoffice"),
    ("thunder bird", "thunderbird"),
    ("tondeur birde", "thunderbird"),
    ("nau ti luce", "nautilus"),
    ("nautiluce", "nautilus"),
    ("gimp", "gimp"),
    ("jaimpe", "gimp"),
    ("aude a city", "audacity"),
    ("au da city", "audacity"),
    ("vé elle cé", "vlc"),
    ("v l c", "vlc"),
    ("blendeur", "blender"),
    ("blaindeur", "blender"),
    ("steam", "steam"),
    ("stim", "steam"),
    ("kodi", "kodi"),
    ("coddy", "kodi"),
    ("obs studio", "obs"),
    ("obesse studio", "obs"),
    ("filzilla", "filezilla"),
    ("file zilla", "filezilla"),
    ("trans mission", "transmission"),
]

# --- 3. Termes techniques IA/cluster (30) ---
ai_cluster = [
    ("elle aime studio", "lm studio"),
    ("aile aime studio", "lm studio"),
    ("aile ème studio", "lm studio"),
    ("o lama", "ollama"),
    ("au lama", "ollama"),
    ("haut lama", "ollama"),
    ("ouisper", "whisper"),
    ("whisper", "whisper"),
    ("ouispère", "whisper"),
    ("jé pé u", "gpu"),
    ("ji pi you", "gpu"),
    ("vérame", "vram"),
    ("vie rame", "vram"),
    ("zia ram", "zram"),
    ("zi rame", "zram"),
    ("clostaire", "cluster"),
    ("clouster", "cluster"),
    ("qlosstère", "cluster"),
    ("pine cône", "pinecone"),
    ("paille tork", "pytorch"),
    ("paye torch", "pytorch"),
    ("tenser flot", "tensorflow"),
    ("tence heure flo", "tensorflow"),
    ("langue chaîne", "langchain"),
    ("langle chaîne", "langchain"),
    ("huguine face", "huggingface"),
    ("ugine face", "huggingface"),
    ("transe formeur", "transformer"),
    ("enne vidéa", "nvidia"),
    ("aime dé", "amd"),
]

# --- 4. Commandes système mal transcrites (30) ---
system_commands = [
    ("système cé té elle", "systemctl"),
    ("system cé té elle", "systemctl"),
    ("système contrôle", "systemctl"),
    ("journal cé té elle", "journalctl"),
    ("journal contrôle", "journalctl"),
    ("aime vé cé", "nmcli"),
    ("aine aime cé elle aille", "nmcli"),
    ("essai essai aiche", "ssh"),
    ("esse esse hache", "ssh"),
    ("eu effe double", "ufw"),
    ("u f w", "ufw"),
    ("paille tonne", "python"),
    ("paille thon", "python"),
    ("pi thon", "python"),
    ("dé pé ka gé", "dpkg"),
    ("dé paquet age", "dpkg"),
    ("apte gète", "apt-get"),
    ("apte guette", "apt-get"),
    ("snape", "snap"),
    ("flat pack", "flatpak"),
    ("fla pack", "flatpak"),
    ("doker", "docker"),
    ("do quaire", "docker"),
    ("doqueur", "docker"),
    ("crontabe", "crontab"),
    ("crone tab", "crontab"),
    ("aiche top", "htop"),
    ("h top", "htop"),
    ("aine top", "ntop"),
    ("aïe pé", "ip"),
]

# --- 5. Phrases complètes corrigées (30) ---
full_phrases = [
    ("ouvre le terminale", "ouvre le terminal"),
    ("montre les logue", "montre les logs"),
    ("montre les loges", "montre les logs"),
    ("vérifie leclustère", "vérifie le cluster"),
    ("vérifie le clustère", "vérifie le cluster"),
    ("les mets à jour", "mets à jour"),
    ("fais un bac up", "fais un backup"),
    ("fait un bac cup", "fais un backup"),
    ("affiche les procéssuce", "affiche les processus"),
    ("montre la températur", "montre la température"),
    ("quel processeur", "quel cpu"),
    ("combien de mémouar", "combien de mémoire"),
    ("combien de mémoir", "combien de mémoire"),
    ("quelle heure et il", "quelle heure est-il"),
    ("quelle heure ait il", "quelle heure est-il"),
    ("lance le serveure", "lance le serveur"),
    ("arrête le serveure", "arrête le serveur"),
    ("montre le tableau de bor", "montre le tableau de bord"),
    ("ouvre un navigateure", "ouvre un navigateur"),
    ("ferme toute les fenêtres", "ferme toutes les fenêtres"),
    ("mets le son a fond", "mets le son à fond"),
    ("coupe le micro", "coupe le micro"),
    ("allume la camérat", "allume la caméra"),
    ("active le mode sombr", "active le mode sombre"),
    ("désactive le mode sombr", "désactive le mode sombre"),
    ("montre l'espace disque", "montre l'espace disque"),
    ("affiche les service actif", "affiche les services actifs"),
    ("redémarre le réso", "redémarre le réseau"),
    ("redémarre le réseaux", "redémarre le réseau"),
    ("lance une analyse de sécurité", "lance une analyse de sécurité"),
]

# --- 6. Chiffres et unités (15) ---
numbers_units = [
    ("cinquante pour cent", "50%"),
    ("cent pour cent", "100%"),
    ("vingt pour cent", "20%"),
    ("trente pour cent", "30%"),
    ("quarante pour cent", "40%"),
    ("soixante pour cent", "60%"),
    ("soixante-dix pour cent", "70%"),
    ("quatre-vingt pour cent", "80%"),
    ("quatre-vingt-dix pour cent", "90%"),
    ("dix pour cent", "10%"),
    ("cinq pour cent", "5%"),
    ("zéro pour cent", "0%"),
    ("un giga", "1 Go"),
    ("deux gigas", "2 Go"),
    ("huit gigas", "8 Go"),
]

# --- 7. Noms propres JARVIS (15) ---
jarvis_names = [
    ("jar visse", "jarvis"),
    ("jarre vice", "jarvis"),
    ("jar vis", "jarvis"),
    ("aime un", "m1"),
    ("aime deux", "m2"),
    ("aime trois", "m3"),
    ("eau aile un", "ol1"),
    ("eau elle un", "ol1"),
    ("eau aile deux", "ol2"),
    ("eau elle deux", "ol2"),
    ("eau aile trois", "ol3"),
    ("eau elle trois", "ol3"),
    ("la créa trice", "la créatrice"),
    ("le contrôle heure", "le contrôleur"),
    ("le pont", "le pont"),
]

# Correspondance catégorie → liste
ALL_CATEGORIES = [
    ("homophone", homophones),
    ("application", applications),
    ("ai_cluster", ai_cluster),
    ("system_command", system_commands),
    ("full_phrase", full_phrases),
    ("number_unit", numbers_units),
    ("jarvis_name", jarvis_names),
]


def main():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    # Récupérer les corrections existantes pour éviter les doublons
    cur.execute("SELECT wrong FROM voice_corrections")
    existing = {row[0] for row in cur.fetchall()}

    inserted = 0
    skipped = 0

    for category, corrections in ALL_CATEGORIES:
        for wrong, correct in corrections:
            if wrong in existing:
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO voice_corrections (wrong, correct, category, hit_count) "
                "VALUES (?, ?, ?, 0)",
                (wrong, correct, category),
            )
            existing.add(wrong)
            inserted += 1

    db.commit()

    # Afficher le résumé
    cur.execute("SELECT COUNT(*) FROM voice_corrections")
    total = cur.fetchone()[0]

    cur.execute("SELECT category, COUNT(*) FROM voice_corrections GROUP BY category ORDER BY COUNT(*) DESC")
    stats = cur.fetchall()

    print(f"Corrections insérées : {inserted}")
    print(f"Doublons ignorés     : {skipped}")
    print(f"Total en base        : {total}")
    print()
    print("Répartition par catégorie :")
    for cat, count in stats:
        print(f"  {cat:20s} : {count}")

    db.close()


if __name__ == "__main__":
    main()
