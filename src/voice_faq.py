#!/usr/bin/env python3
"""voice_faq.py — Reponses instantanees aux questions frequentes sur JARVIS et Linux.

Base de 100 questions-reponses avec fuzzy matching (difflib).
Integre dans voice_router.py comme fallback avant le moteur conversationnel.

Usage:
    python src/voice_faq.py --ask "c'est quoi jarvis"
    python src/voice_faq.py --search "gpu"
    python src/voice_faq.py --stats
    python src/voice_faq.py --list
"""
from __future__ import annotations

import difflib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

# Chemin racine JARVIS
_JARVIS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Modele de donnees
# ---------------------------------------------------------------------------
@dataclass
class FAQEntry:
    """Une entree question-reponse dans la base FAQ."""

    question: str
    answer: str
    category: str
    # Variantes de formulation pour ameliorer le fuzzy match
    aliases: list[str] = field(default_factory=list)
    # Nombre de fois ou cette FAQ a ete utilisee
    hit_count: int = 0


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
CAT_JARVIS = "jarvis"
CAT_LINUX = "linux"
CAT_CLUSTER = "cluster"
CAT_TECHNIQUE = "technique"


# ---------------------------------------------------------------------------
# Fonctions dynamiques (lecture de donnees en temps reel)
# ---------------------------------------------------------------------------
def _get_skills_count() -> str:
    """Lecture du nombre de skills depuis skills.json."""
    try:
        path = os.path.join(_JARVIS_ROOT, "data", "skills.json")
        with open(path, encoding="utf-8") as f:
            skills = json.load(f)
        return f"JARVIS dispose de {len(skills)} skills dans data/skills.json."
    except Exception:
        return "JARVIS dispose de plus de 200 skills (lecture skills.json indisponible)."


def _get_voice_profile() -> str:
    """Lecture du profil vocal actif."""
    try:
        from src.voice_profiles import get_active_profile
        profile = get_active_profile()
        if profile:
            return f"Le profil vocal actif est '{profile.get('name', 'default')}' — " \
                   f"langue: {profile.get('language', 'fr')}, " \
                   f"sensibilite: {profile.get('sensitivity', 'standard')}."
    except Exception:
        pass
    return "Le profil vocal actif est le profil par defaut (francais, sensibilite standard)."


def _get_last_report() -> str:
    """Resume du dernier daily report."""
    try:
        reports_dir = os.path.join(_JARVIS_ROOT, "data", "reports")
        if os.path.isdir(reports_dir):
            files = sorted(
                [f for f in os.listdir(reports_dir) if f.endswith(".json")],
                reverse=True,
            )
            if files:
                with open(os.path.join(reports_dir, files[0]), encoding="utf-8") as f:
                    report = json.load(f)
                date = report.get("date", files[0])
                status = report.get("status", "ok")
                return f"Dernier rapport: {date} — statut: {status}."
    except Exception:
        pass
    return "Aucun rapport recent trouve dans data/reports/."


# ---------------------------------------------------------------------------
# Base de donnees FAQ (100 entrees)
# ---------------------------------------------------------------------------
def _build_default_faq() -> list[FAQEntry]:
    """Construit la base FAQ par defaut avec 100 questions-reponses."""
    entries: list[FAQEntry] = []

    # =======================================================================
    # 1. FAQ JARVIS (30)
    # =======================================================================
    entries.extend([
        FAQEntry(
            "c'est quoi jarvis",
            "JARVIS est ton assistant IA Linux avec plus de 200 skills, "
            "335 commandes vocales, 613 handlers MCP, un cluster de 4 noeuds IA "
            "et 10 GPU. Il gere tout : systeme, reseau, trading, dev, vocal.",
            CAT_JARVIS,
            ["jarvis c'est quoi", "qu'est-ce que jarvis", "presente jarvis",
             "definition jarvis", "a quoi sert jarvis"],
        ),
        FAQEntry(
            "combien de skills",
            _get_skills_count(),
            CAT_JARVIS,
            ["nombre de skills", "skills disponibles", "combien de competences",
             "liste des skills"],
        ),
        FAQEntry(
            "quels raccourcis",
            "Les 15 raccourcis Super+ : Super+T (terminal), Super+E (fichiers), "
            "Super+B (navigateur), Super+C (code), Super+D (bureau), "
            "Super+L (verrouiller), Super+M (moniteur), Super+S (parametres), "
            "Super+A (applications), Super+1-9 (workspace), Super+Fleches (snap fenetre), "
            "Super+Tab (switcher), Super+Space (lanceur), Super+P (affichage), "
            "Super+V (clipboard).",
            CAT_JARVIS,
            ["raccourcis clavier", "super plus", "raccourcis super",
             "quels sont les raccourcis", "liste raccourcis"],
        ),
        FAQEntry(
            "quel profil actif",
            _get_voice_profile(),
            CAT_JARVIS,
            ["profil vocal actif", "profil vocal", "quel profil", "mon profil"],
        ),
        FAQEntry(
            "dernier rapport",
            _get_last_report(),
            CAT_JARVIS,
            ["rapport du jour", "daily report", "resume rapport",
             "dernier daily report"],
        ),
        FAQEntry(
            "combien de commandes vocales",
            "JARVIS supporte environ 335 commandes vocales reparties en 5 modules : "
            "desktop control (305), window manager (114), souris (30+), "
            "dictee (94), lecteur ecran (12).",
            CAT_JARVIS,
            ["nombre de commandes", "combien de commandes", "total commandes vocales"],
        ),
        FAQEntry(
            "comment fonctionne le routeur vocal",
            "Le voice_router essaie chaque module par priorite : aliases → corrections SQL "
            "→ multi-intent → context engine → modules (desktop, fenetres, souris, dictee, "
            "ecran) → FAQ → IA fallback → moteur conversationnel.",
            CAT_JARVIS,
            ["voice router", "routeur vocal", "routage vocal",
             "comment marche le routage"],
        ),
        FAQEntry(
            "combien de modules",
            "JARVIS comporte 246 modules Python dans src/ (93 000 lignes), "
            "dont 21 modules linux_*.py pour le controle systeme.",
            CAT_JARVIS,
            ["nombre de modules", "modules jarvis", "taille du code"],
        ),
        FAQEntry(
            "combien de bases de donnees",
            "JARVIS utilise 64 bases SQLite (160 MB total), dont etoile.db "
            "(42 tables, 13 500 lignes) et learned_actions.db (41 dominos).",
            CAT_JARVIS,
            ["bases de donnees", "sqlite", "combien de db", "databases"],
        ),
        FAQEntry(
            "combien de tests",
            "JARVIS a 2 281 fonctions de test dans 77+ fichiers, avec une "
            "couverture de 85.5% sur src/.",
            CAT_JARVIS,
            ["nombre de tests", "couverture tests", "test coverage"],
        ),
        FAQEntry(
            "qu'est-ce que les dominos",
            "Les dominos sont 41 pipelines conversationnels appris dans "
            "learned_actions.db. Chaque domino a des triggers textuels et un "
            "plan multi-etapes. Match fuzzy (seuil 0.75).",
            CAT_JARVIS,
            ["dominos jarvis", "learned actions", "actions apprises"],
        ),
        FAQEntry(
            "comment ajouter un skill",
            "Ajoute une entree dans data/skills.json avec name, description, "
            "triggers et steps. Ou utilise le handler MCP 'learned_action_save' "
            "pour creer un domino conversationnel.",
            CAT_JARVIS,
            ["ajouter skill", "creer skill", "nouveau skill", "add skill"],
        ),
        FAQEntry(
            "comment lancer jarvis",
            "Utilise 'bash projects/linux/jarvis-ctl.sh start' pour demarrer "
            "tous les services JARVIS, ou 'docker compose up -d' pour Docker.",
            CAT_JARVIS,
            ["demarrer jarvis", "lancer jarvis", "start jarvis",
             "comment demarrer"],
        ),
        FAQEntry(
            "comment arreter jarvis",
            "Utilise 'bash projects/linux/jarvis-ctl.sh stop' pour arreter "
            "tous les services JARVIS.",
            CAT_JARVIS,
            ["arreter jarvis", "stop jarvis", "couper jarvis"],
        ),
        FAQEntry(
            "status jarvis",
            "Utilise 'bash projects/linux/jarvis-ctl.sh status' pour voir le "
            "statut de tous les services JARVIS.",
            CAT_JARVIS,
            ["etat jarvis", "jarvis status", "comment va jarvis",
             "statut jarvis"],
        ),
        FAQEntry(
            "qu'est-ce que le canvas",
            "Le Canvas est l'interface web standalone de JARVIS sur le port 18800. "
            "C'est un proxy HTTP avec autolearn engine (canvas/direct-proxy.js).",
            CAT_JARVIS,
            ["canvas jarvis", "interface web", "port 18800", "canvas c'est quoi"],
        ),
        FAQEntry(
            "qu'est-ce que openclaw",
            "OpenClaw est le systeme de 40 agents + 56 dynamiques avec 11 crons "
            "et une gateway sur le port 18789.",
            CAT_JARVIS,
            ["openclaw c'est quoi", "openclaw", "agents openclaw"],
        ),
        FAQEntry(
            "combien de workflows n8n",
            "JARVIS utilise 63 workflows n8n pour l'automatisation.",
            CAT_JARVIS,
            ["n8n workflows", "workflows", "nombre workflows"],
        ),
        FAQEntry(
            "combien d'endpoints api",
            "JARVIS expose 517 endpoints REST et 613 handlers MCP.",
            CAT_JARVIS,
            ["api endpoints", "endpoints rest", "handlers mcp",
             "nombre endpoints"],
        ),
        FAQEntry(
            "comment fonctionne la correction vocale",
            "73 regles de correction STT specifiques Linux transforment les "
            "erreurs de reconnaissance (ex: 'ouvre fire fox' → 'ouvre firefox'). "
            "Stockees en base SQL, appliquees avant le routage.",
            CAT_JARVIS,
            ["correction vocale", "correction stt", "regles stt",
             "erreurs reconnaissance"],
        ),
        FAQEntry(
            "comment fonctionne le multi-intent",
            "Le parseur multi-intent detecte les separateurs ('et', 'puis', "
            "'apres') dans les phrases vocales et decompose en sous-commandes "
            "executees sequentiellement.",
            CAT_JARVIS,
            ["multi intent", "multi commandes", "plusieurs commandes",
             "commandes chainees"],
        ),
        FAQEntry(
            "qu'est-ce que le context engine",
            "Le voice_context_engine enrichit les commandes ambigues en commandes "
            "precises grace au contexte (fenetre active, historique, heure).",
            CAT_JARVIS,
            ["context engine", "contexte vocal", "enrichissement contextuel"],
        ),
        FAQEntry(
            "qu'est-ce que le voice learning",
            "Le voice_learning analyse les commandes qui echouent et apprend "
            "automatiquement de nouvelles associations commande → action.",
            CAT_JARVIS,
            ["apprentissage vocal", "voice learning", "auto-apprentissage vocal"],
        ),
        FAQEntry(
            "qu'est-ce que les voice macros",
            "Les voice macros permettent d'enregistrer des sequences de commandes "
            "vocales et de les rejouer avec un seul mot-cle.",
            CAT_JARVIS,
            ["macros vocales", "voice macros", "enregistrer macro"],
        ),
        FAQEntry(
            "comment fonctionne le fallback ia",
            "Quand aucun module ne reconnait la commande, JARVIS envoie a "
            "qwen3:1.7b (Ollama, ultra-rapide) puis LM Studio en fallback "
            "pour une reponse conversationnelle.",
            CAT_JARVIS,
            ["fallback ia", "ia fallback", "reponse ia", "mode conversationnel"],
        ),
        FAQEntry(
            "quels slash commands",
            "43 slash commands : /cluster-check, /gpu-status, /thermal, "
            "/heal-cluster, /consensus, /quick-ask, /web-search, /trading-scan, "
            "/audit, /model-swap, /deploy, etc.",
            CAT_JARVIS,
            ["slash commands", "commandes slash", "liste slash"],
        ),
        FAQEntry(
            "comment faire un audit",
            "Lance 'uv run python scripts/system_audit.py --quick' pour un "
            "audit rapide, ou utilise la slash command /audit.",
            CAT_JARVIS,
            ["audit systeme", "system audit", "lancer audit"],
        ),
        FAQEntry(
            "comment voir les logs jarvis",
            "Les logs JARVIS sont dans data/logs/. Utilise aussi journalctl "
            "--user -u jarvis-* pour les services systemd.",
            CAT_JARVIS,
            ["logs jarvis", "voir logs", "journaux jarvis"],
        ),
        FAQEntry(
            "qu'est-ce que le cowork",
            "COWORK est le systeme de collaboration multi-agents avec 409 scripts "
            "dans cowork/dev/. Pipeline autonome pour le developpement.",
            CAT_JARVIS,
            ["cowork c'est quoi", "cowork agents", "collaboration agents"],
        ),
        FAQEntry(
            "comment fonctionne le trading",
            "Le module trading scanne les signaux crypto via des strategies "
            "(RSI, MACD, Bollinger, etc.), backteste et execute via les exchanges. "
            "Lance avec /trading-scan ou le script gpu_pipeline.py.",
            CAT_JARVIS,
            ["trading jarvis", "signaux trading", "crypto trading",
             "trading scan"],
        ),
    ])

    # =======================================================================
    # 2. FAQ Linux (30)
    # =======================================================================
    entries.extend([
        FAQEntry(
            "comment installer un paquet",
            "sudo apt install nom-du-paquet (Debian/Ubuntu) ou "
            "sudo dnf install nom-du-paquet (Fedora/RHEL).",
            CAT_LINUX,
            ["installer paquet", "apt install", "installer logiciel",
             "installer programme"],
        ),
        FAQEntry(
            "comment redemarrer un service",
            "sudo systemctl restart nom.service — ou 'systemctl status nom.service' "
            "pour voir son etat.",
            CAT_LINUX,
            ["redemarrer service", "restart service", "relancer service",
             "systemctl restart"],
        ),
        FAQEntry(
            "ou sont les logs",
            "/var/log/ pour les logs systeme classiques, ou 'journalctl' pour "
            "les logs systemd. journalctl -xe pour les erreurs recentes.",
            CAT_LINUX,
            ["ou sont les logs", "fichiers log", "journaux systeme",
             "var log", "journalctl"],
        ),
        FAQEntry(
            "comment voir l'espace disque",
            "df -h pour l'espace disque par partition, du -sh /chemin pour la "
            "taille d'un dossier.",
            CAT_LINUX,
            ["espace disque", "disque plein", "df", "taille disque",
             "espace libre"],
        ),
        FAQEntry(
            "comment trouver un fichier",
            "find / -name 'nom' pour chercher partout, ou locate nom (plus rapide "
            "mais necessite updatedb).",
            CAT_LINUX,
            ["trouver fichier", "chercher fichier", "find", "locate",
             "ou est le fichier"],
        ),
        FAQEntry(
            "comment voir les processus",
            "ps aux pour la liste complete, top ou htop pour le monitoring "
            "en temps reel, pidof nom pour un PID specifique.",
            CAT_LINUX,
            ["voir processus", "liste processus", "ps aux", "htop",
             "processus en cours"],
        ),
        FAQEntry(
            "comment tuer un processus",
            "kill PID pour un arret propre, kill -9 PID pour forcer, "
            "killall nom ou pkill nom pour tuer par nom.",
            CAT_LINUX,
            ["tuer processus", "kill processus", "arreter processus",
             "kill -9"],
        ),
        FAQEntry(
            "comment voir la memoire",
            "free -h pour la memoire RAM et swap, ou cat /proc/meminfo "
            "pour les details.",
            CAT_LINUX,
            ["memoire ram", "free", "ram disponible", "utilisation memoire",
             "memoire libre"],
        ),
        FAQEntry(
            "comment changer les permissions",
            "chmod 755 fichier (rwxr-xr-x), chmod +x script.sh pour le rendre "
            "executable, chown user:group fichier pour changer le proprietaire.",
            CAT_LINUX,
            ["permissions fichier", "chmod", "chown", "rendre executable",
             "droits fichier"],
        ),
        FAQEntry(
            "comment editer un fichier",
            "nano fichier (simple), vim fichier (avance), ou code fichier "
            "(VS Code). Pour les fichiers systeme: sudo nano /etc/fichier.",
            CAT_LINUX,
            ["editer fichier", "modifier fichier", "nano", "vim",
             "ouvrir fichier texte"],
        ),
        FAQEntry(
            "comment voir les ports ouverts",
            "ss -tulnp ou netstat -tulnp pour les ports en ecoute, "
            "lsof -i :PORT pour un port specifique.",
            CAT_LINUX,
            ["ports ouverts", "ports ecoute", "netstat", "ss",
             "quel port"],
        ),
        FAQEntry(
            "comment monter une cle usb",
            "sudo mount /dev/sdX1 /mnt/usb — identifie le device avec lsblk. "
            "Ou utilise udisksctl mount -b /dev/sdX1.",
            CAT_LINUX,
            ["monter cle usb", "mount usb", "cle usb", "monter disque"],
        ),
        FAQEntry(
            "comment voir l'adresse ip",
            "ip addr show ou ip a pour les interfaces reseau, "
            "curl ifconfig.me pour l'IP publique.",
            CAT_LINUX,
            ["adresse ip", "mon ip", "ip addr", "quelle ip",
             "ip publique"],
        ),
        FAQEntry(
            "comment ajouter un utilisateur",
            "sudo adduser nom (interactif) ou sudo useradd -m nom (minimal). "
            "sudo passwd nom pour definir le mot de passe.",
            CAT_LINUX,
            ["ajouter utilisateur", "creer utilisateur", "adduser",
             "nouvel utilisateur"],
        ),
        FAQEntry(
            "comment mettre a jour le systeme",
            "sudo apt update && sudo apt upgrade -y (Debian/Ubuntu), "
            "sudo dnf upgrade -y (Fedora).",
            CAT_LINUX,
            ["mise a jour", "update systeme", "apt upgrade",
             "mettre a jour linux"],
        ),
        FAQEntry(
            "comment voir la version linux",
            "uname -a pour le kernel, cat /etc/os-release pour la distribution, "
            "lsb_release -a pour les details.",
            CAT_LINUX,
            ["version linux", "quel linux", "quelle distribution",
             "version kernel", "uname"],
        ),
        FAQEntry(
            "comment configurer le firewall",
            "sudo ufw enable pour activer, sudo ufw allow 22 pour ouvrir SSH, "
            "sudo ufw status pour voir les regles.",
            CAT_LINUX,
            ["firewall", "ufw", "pare-feu", "ouvrir port",
             "configurer firewall"],
        ),
        FAQEntry(
            "comment creer un service systemd",
            "Cree un fichier .service dans /etc/systemd/system/, puis "
            "sudo systemctl daemon-reload && sudo systemctl enable --now nom.service.",
            CAT_LINUX,
            ["creer service", "systemd service", "nouveau service",
             "fichier service"],
        ),
        FAQEntry(
            "comment voir les disques",
            "lsblk pour l'arborescence des disques, fdisk -l pour les partitions, "
            "blkid pour les UUID.",
            CAT_LINUX,
            ["voir disques", "lsblk", "disques disponibles", "partitions",
             "fdisk"],
        ),
        FAQEntry(
            "comment programmer une tache cron",
            "crontab -e pour editer, format: minute heure jour mois jour_semaine commande. "
            "Exemple: '0 * * * * /script.sh' pour chaque heure.",
            CAT_LINUX,
            ["cron", "crontab", "programmer tache", "tache planifiee",
             "tache automatique"],
        ),
        FAQEntry(
            "comment compresser un dossier",
            "tar -czf archive.tar.gz dossier/ pour compresser, "
            "tar -xzf archive.tar.gz pour extraire. zip -r archive.zip dossier/.",
            CAT_LINUX,
            ["compresser", "tar", "zip", "archiver", "decompresser"],
        ),
        FAQEntry(
            "comment voir l'uptime",
            "uptime pour le temps de fonctionnement et la charge, "
            "ou w pour uptime + utilisateurs connectes.",
            CAT_LINUX,
            ["uptime", "depuis quand", "temps fonctionnement",
             "charge systeme"],
        ),
        FAQEntry(
            "comment redemarrer linux",
            "sudo reboot ou sudo shutdown -r now pour redemarrer, "
            "sudo shutdown -h now pour eteindre.",
            CAT_LINUX,
            ["redemarrer linux", "reboot", "eteindre linux", "shutdown",
             "redemarrer machine"],
        ),
        FAQEntry(
            "comment voir la carte graphique",
            "lspci | grep -i vga pour le modele, nvidia-smi pour les GPU NVIDIA "
            "(utilisation, temperature, VRAM).",
            CAT_LINUX,
            ["carte graphique", "gpu", "nvidia-smi", "quelle gpu",
             "vram"],
        ),
        FAQEntry(
            "comment configurer ssh",
            "sudo apt install openssh-server, puis sudo systemctl enable ssh. "
            "Config dans /etc/ssh/sshd_config. Cle: ssh-keygen -t ed25519.",
            CAT_LINUX,
            ["configurer ssh", "ssh", "connexion ssh", "cle ssh",
             "serveur ssh"],
        ),
        FAQEntry(
            "comment voir les variables d'environnement",
            "env ou printenv pour tout voir, echo $NOM pour une variable, "
            "export NOM=valeur pour definir.",
            CAT_LINUX,
            ["variables environnement", "env", "export", "path",
             "variable path"],
        ),
        FAQEntry(
            "comment creer un alias bash",
            "Ajoute 'alias nom=\"commande\"' dans ~/.bashrc, puis source ~/.bashrc. "
            "Exemple: alias ll='ls -la'.",
            CAT_LINUX,
            ["alias bash", "creer alias", "raccourci terminal",
             "bashrc"],
        ),
        FAQEntry(
            "comment voir les connexions reseau",
            "ss -tuanp pour toutes les connexions, nmcli pour NetworkManager, "
            "ip route pour les routes.",
            CAT_LINUX,
            ["connexions reseau", "reseau", "nmcli", "ip route",
             "connexions actives"],
        ),
        FAQEntry(
            "comment installer docker",
            "curl -fsSL https://get.docker.com | sudo sh, puis "
            "sudo usermod -aG docker $USER && newgrp docker.",
            CAT_LINUX,
            ["installer docker", "docker", "docker install",
             "configurer docker"],
        ),
        FAQEntry(
            "comment copier via scp",
            "scp fichier user@host:/chemin pour envoyer, "
            "scp user@host:/fichier . pour recevoir. Ajoute -r pour les dossiers.",
            CAT_LINUX,
            ["scp", "copier ssh", "transferer fichier", "copie distante"],
        ),
    ])

    # =======================================================================
    # 3. FAQ Cluster (20)
    # =======================================================================
    entries.extend([
        FAQEntry(
            "c'est quoi m1",
            "M1 (La Creatrice) est le noeud principal du cluster : "
            "Ryzen 5700X3D, 6 GPU (46 GB VRAM), 32 GB RAM. "
            "Heberge LM Studio + Ollama + tous les services JARVIS.",
            CAT_CLUSTER,
            ["m1 c'est quoi", "noeud m1", "la creatrice", "machine principale"],
        ),
        FAQEntry(
            "c'est quoi m2",
            "M2 est le deuxieme noeud du cluster, dedie au reasoning avec "
            "deepseek-r1-0528-qwen3-8b (44 tok/s). IP: 192.168.1.26.",
            CAT_CLUSTER,
            ["m2 c'est quoi", "noeud m2", "machine m2"],
        ),
        FAQEntry(
            "c'est quoi m3",
            "M3 est le troisieme noeud du cluster, fallback reasoning avec "
            "deepseek-r1-0528-qwen3-8b. IP: 192.168.1.113.",
            CAT_CLUSTER,
            ["m3 c'est quoi", "noeud m3", "machine m3"],
        ),
        FAQEntry(
            "c'est quoi ollama",
            "Ollama est un serveur de modeles IA local qui permet de faire "
            "tourner des LLM (qwen3, deepseek, etc.) en local. "
            "API sur 127.0.0.1:11434.",
            CAT_CLUSTER,
            ["ollama c'est quoi", "a quoi sert ollama", "ollama",
             "serveur ollama"],
        ),
        FAQEntry(
            "c'est quoi lm studio",
            "LM Studio est un serveur d'inference IA local avec interface graphique. "
            "API compatible OpenAI sur 127.0.0.1:1234.",
            CAT_CLUSTER,
            ["lm studio c'est quoi", "lm studio", "lmstudio"],
        ),
        FAQEntry(
            "comment changer de modele",
            "Utilise /model-swap ou le skill model_manager pour changer le modele "
            "IA actif sur un noeud du cluster.",
            CAT_CLUSTER,
            ["changer modele", "swap modele", "model swap",
             "charger un modele"],
        ),
        FAQEntry(
            "quels modeles disponibles",
            "Modeles principaux : qwen3-8b (M1, champion local 46tok/s), "
            "gpt-oss-20b (M1B, deep), deepseek-r1 (M2/M3, reasoning), "
            "gpt-oss:120b-cloud (OL1, champion cloud), qwen3:1.7b (ultra-rapide).",
            CAT_CLUSTER,
            ["modeles disponibles", "liste modeles", "quels modeles",
             "modeles ia"],
        ),
        FAQEntry(
            "comment voir l'etat du cluster",
            "Utilise /cluster-check ou le handler MCP lm_cluster_status "
            "pour voir la sante de tous les noeuds.",
            CAT_CLUSTER,
            ["etat cluster", "cluster health", "sante cluster",
             "cluster status"],
        ),
        FAQEntry(
            "combien de gpu",
            "Le cluster dispose de 10 GPU pour un total de 78 GB de VRAM. "
            "M1 a 6 GPU (46 GB VRAM).",
            CAT_CLUSTER,
            ["nombre gpu", "combien de cartes", "vram totale",
             "gpu cluster"],
        ),
        FAQEntry(
            "comment surveiller la temperature gpu",
            "Utilise /thermal, nvidia-smi, ou le timer systemd jarvis-thermal "
            "(toutes les 5 min). Warning a 75C, critique a 85C.",
            CAT_CLUSTER,
            ["temperature gpu", "thermal", "gpu chaud", "surchauffe gpu"],
        ),
        FAQEntry(
            "comment guerir le cluster",
            "Utilise /heal-cluster pour lancer le self-healer. Il detecte les "
            "noeuds en panne et tente de les relancer automatiquement.",
            CAT_CLUSTER,
            ["guerir cluster", "heal cluster", "reparer cluster",
             "cluster en panne"],
        ),
        FAQEntry(
            "comment fonctionne le load balancer",
            "Le load balancer (src/load_balancer.py) distribue les requetes IA "
            "entre les noeuds selon leur charge, latence et score.",
            CAT_CLUSTER,
            ["load balancer", "equilibrage charge", "repartition requetes"],
        ),
        FAQEntry(
            "comment fonctionne le consensus",
            "Le mode consensus (src/consensus.py) envoie la meme requete a "
            "plusieurs noeuds et fusionne les reponses pour plus de fiabilite. "
            "Lance avec /consensus.",
            CAT_CLUSTER,
            ["consensus", "mode consensus", "multi-noeud"],
        ),
        FAQEntry(
            "c'est quoi le bridge",
            "Le bridge (src/collab_bridge.py) connecte les noeuds du cluster "
            "pour la collaboration multi-agents et le partage de contexte.",
            CAT_CLUSTER,
            ["bridge c'est quoi", "collab bridge", "pont cluster"],
        ),
        FAQEntry(
            "combien de noeuds",
            "Le cluster JARVIS a 4 noeuds IA : M1 (principal), M1B (deep), "
            "M2 (reasoning), M3 (fallback). Plus OL1 cloud (Ollama).",
            CAT_CLUSTER,
            ["nombre noeuds", "combien de machines", "noeuds cluster",
             "taille cluster"],
        ),
        FAQEntry(
            "quel est le champion",
            "Le champion local est qwen3-8b sur M1 (46 tok/s, score 98.4/100). "
            "Le champion cloud est gpt-oss:120b (51 tok/s, score 100/100).",
            CAT_CLUSTER,
            ["champion", "meilleur modele", "modele le plus rapide",
             "quel modele utiliser"],
        ),
        FAQEntry(
            "comment ajouter un noeud",
            "Configure le noeud dans src/config.py (section NODES), installe "
            "LM Studio ou Ollama, puis verifie avec /cluster-check.",
            CAT_CLUSTER,
            ["ajouter noeud", "nouveau noeud", "ajouter machine",
             "etendre cluster"],
        ),
        FAQEntry(
            "pourquoi 127.0.0.1 et pas localhost",
            "JARVIS utilise toujours 127.0.0.1 au lieu de localhost pour eviter "
            "le lag de resolution IPv6 sur certains systemes.",
            CAT_CLUSTER,
            ["localhost", "127.0.0.1", "pourquoi pas localhost",
             "ipv6 lag"],
        ),
        FAQEntry(
            "c'est quoi nothink",
            "/nothink est un prefix obligatoire pour qwen3 et gpt-oss sur M1. "
            "Il desactive le mode 'thinking' pour des reponses plus rapides. "
            "Ne pas utiliser pour deepseek-r1.",
            CAT_CLUSTER,
            ["nothink", "prefix nothink", "slash nothink",
             "pourquoi nothink"],
        ),
        FAQEntry(
            "comment voir les modeles ollama",
            "ollama list pour les modeles installes, ollama ps pour ceux charges "
            "en VRAM, ollama pull nom pour en telecharger un nouveau.",
            CAT_CLUSTER,
            ["modeles ollama", "ollama list", "ollama models",
             "modeles installes"],
        ),
    ])

    # =======================================================================
    # 4. FAQ Technique (20)
    # =======================================================================
    entries.extend([
        FAQEntry(
            "c'est quoi un domino",
            "Un domino est un pipeline multi-etapes conversationnel. Chaque etape "
            "appelle un outil MCP, attend le resultat, et passe au suivant. "
            "41 dominos dans learned_actions.db.",
            CAT_TECHNIQUE,
            ["domino c'est quoi", "pipeline domino", "domino definition",
             "a quoi sert un domino"],
        ),
        FAQEntry(
            "c'est quoi le brain",
            "Le brain (src/brain.py) analyse les patterns d'utilisation, "
            "detecte les anomalies et optimise les routages. Il apprend des "
            "commandes reussies et echouees.",
            CAT_TECHNIQUE,
            ["brain c'est quoi", "cerveau jarvis", "brain analyse",
             "a quoi sert le brain"],
        ),
        FAQEntry(
            "comment fonctionne l'apprentissage",
            "Pipeline d'apprentissage : 1) Log chaque commande vocale dans "
            "voice_analytics, 2) Le brain analyse les patterns, 3) Les reussites "
            "deviennent des dominos, 4) Le drift_detector surveille les regressions.",
            CAT_TECHNIQUE,
            ["apprentissage", "pipeline apprentissage", "comment jarvis apprend",
             "auto-apprentissage"],
        ),
        FAQEntry(
            "c'est quoi le drift detector",
            "Le drift_detector (src/drift_detector.py) surveille les metriques "
            "et detecte les degradations de performance (derive du modele, "
            "latence accrue, erreurs en hausse).",
            CAT_TECHNIQUE,
            ["drift detector", "derive", "detection derive",
             "surveillance performance"],
        ),
        FAQEntry(
            "c'est quoi le circuit breaker",
            "Le circuit breaker (src/circuit_breaker.py) coupe les appels vers "
            "un service en panne pour eviter la cascade d'erreurs. Il se "
            "reactive automatiquement apres un delai.",
            CAT_TECHNIQUE,
            ["circuit breaker", "disjoncteur", "protection panne"],
        ),
        FAQEntry(
            "c'est quoi le service mesh",
            "Le service mesh (src/service_mesh.py) gere la decouverte, le "
            "routage et la resilience des micro-services JARVIS.",
            CAT_TECHNIQUE,
            ["service mesh", "mesh", "micro-services"],
        ),
        FAQEntry(
            "c'est quoi l'event bus",
            "L'event bus (src/event_bus.py) est le bus d'evenements interne. "
            "Les modules publient et souscrivent a des evenements pour communiquer "
            "de facon decoupplee.",
            CAT_TECHNIQUE,
            ["event bus", "bus evenements", "pub sub",
             "communication modules"],
        ),
        FAQEntry(
            "c'est quoi mcp",
            "MCP (Model Context Protocol) est le protocole standardise pour "
            "les outils IA. JARVIS expose 613 handlers MCP via src/mcp_server.py "
            "sur un serveur SSE.",
            CAT_TECHNIQUE,
            ["mcp c'est quoi", "model context protocol", "protocole mcp",
             "handlers mcp"],
        ),
        FAQEntry(
            "c'est quoi le feature flags",
            "Les feature flags (src/feature_flags.py) permettent d'activer/desactiver "
            "des fonctionnalites sans redemarrer JARVIS.",
            CAT_TECHNIQUE,
            ["feature flags", "flags", "activer fonctionnalite",
             "desactiver fonctionnalite"],
        ),
        FAQEntry(
            "c'est quoi le rate limiter",
            "Le rate limiter (src/rate_limiter.py) controle le debit des requetes "
            "pour eviter la surcharge des APIs et des noeuds du cluster.",
            CAT_TECHNIQUE,
            ["rate limiter", "limitation debit", "rate limiting",
             "anti-surcharge"],
        ),
        FAQEntry(
            "c'est quoi le retry policy",
            "Le retry policy (src/retry_policy.py) gere les tentatives de "
            "reessai avec backoff exponentiel quand un appel echoue.",
            CAT_TECHNIQUE,
            ["retry policy", "politique reessai", "retry", "reessai"],
        ),
        FAQEntry(
            "c'est quoi la prediction engine",
            "La prediction engine (src/prediction_engine.py) anticipe les "
            "prochaines commandes probables basee sur l'historique et le contexte.",
            CAT_TECHNIQUE,
            ["prediction engine", "prediction", "anticiper commandes",
             "prediction vocale"],
        ),
        FAQEntry(
            "c'est quoi le quality gate",
            "Le quality gate (src/quality_gate.py) valide chaque reponse IA "
            "avant de la renvoyer: coherence, longueur, toxicite, pertinence.",
            CAT_TECHNIQUE,
            ["quality gate", "controle qualite", "validation reponse"],
        ),
        FAQEntry(
            "c'est quoi le secret vault",
            "Le secret vault (src/secret_vault.py) stocke les credentials "
            "et API keys de facon chiffree. Ne jamais committer les .env.",
            CAT_TECHNIQUE,
            ["secret vault", "coffre secrets", "credentials",
             "api keys"],
        ),
        FAQEntry(
            "c'est quoi l'observability",
            "L'observability (src/observability.py) collecte les metriques, "
            "traces et logs pour monitorer la sante de JARVIS en temps reel.",
            CAT_TECHNIQUE,
            ["observability", "observabilite", "monitoring",
             "metriques jarvis"],
        ),
        FAQEntry(
            "c'est quoi le auto healer",
            "L'auto healer (src/auto_healer_linux.py) detecte et repare "
            "automatiquement les problemes systeme : services en panne, "
            "disque plein, memoire saturee.",
            CAT_TECHNIQUE,
            ["auto healer", "auto-guerison", "reparation automatique",
             "self healing"],
        ),
        FAQEntry(
            "c'est quoi le vram optimizer",
            "Le vram optimizer (src/vram_optimizer.py) gere l'allocation VRAM "
            "entre les modeles IA : decharge les inactifs, priorise le champion.",
            CAT_TECHNIQUE,
            ["vram optimizer", "optimisation vram", "gestion vram",
             "memoire gpu"],
        ),
        FAQEntry(
            "c'est quoi platform dispatch",
            "Le platform dispatch (src/platform_dispatch.py) route automatiquement "
            "vers linux_*.py sur Linux et win_*.py sur Windows. Si le module "
            "n'existe pas, un stub est retourne.",
            CAT_TECHNIQUE,
            ["platform dispatch", "dispatch plateforme", "linux windows",
             "multi-plateforme"],
        ),
        FAQEntry(
            "c'est quoi le task planner",
            "Le task planner (src/agent_task_planner.py) decompose les taches "
            "complexes en sous-taches, les ordonne et les distribue aux agents.",
            CAT_TECHNIQUE,
            ["task planner", "planificateur", "decomposition taches",
             "sous-taches"],
        ),
        FAQEntry(
            "c'est quoi le reflection engine",
            "Le reflection engine (src/reflection_engine.py) fait de "
            "l'auto-evaluation : il revoit les reponses de JARVIS et propose "
            "des ameliorations.",
            CAT_TECHNIQUE,
            ["reflection engine", "auto-evaluation", "reflection",
             "amelioration automatique"],
        ),
    ])

    return entries


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------
class VoiceFAQ:
    """Systeme de FAQ vocale avec fuzzy matching pour reponses instantanees.

    Fournit des reponses immediates aux questions frequentes sur JARVIS,
    Linux, le cluster et les concepts techniques, AVANT le fallback IA.
    """

    MATCH_THRESHOLD: float = 0.6

    def __init__(self) -> None:
        self._entries: list[FAQEntry] = _build_default_faq()
        self._hit_log: list[dict[str, Any]] = []

    # --- Recherche principale ---

    def find_answer(self, question: str) -> dict[str, Any] | None:
        """Trouve la meilleure reponse par fuzzy match (difflib, seuil 0.6).

        Args:
            question: la question posee par l'utilisateur.

        Returns:
            dict avec question, answer, category, confidence — ou None.
        """
        normalized = question.lower().strip()
        if not normalized:
            return None

        best_score: float = 0.0
        best_entry: FAQEntry | None = None

        for entry in self._entries:
            # Comparer avec la question principale
            score = difflib.SequenceMatcher(
                None, normalized, entry.question.lower(),
            ).ratio()

            # Comparer aussi avec chaque alias
            for alias in entry.aliases:
                alias_score = difflib.SequenceMatcher(
                    None, normalized, alias.lower(),
                ).ratio()
                if alias_score > score:
                    score = alias_score

            # Bonus: si la question est contenue dans l'entree ou vice-versa
            if normalized in entry.question.lower() or entry.question.lower() in normalized:
                score = max(score, 0.75)
            for alias in entry.aliases:
                if normalized in alias.lower() or alias.lower() in normalized:
                    score = max(score, 0.70)

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= self.MATCH_THRESHOLD:
            best_entry.hit_count += 1
            result = {
                "question": best_entry.question,
                "answer": best_entry.answer,
                "category": best_entry.category,
                "confidence": round(best_score, 3),
                "hit_count": best_entry.hit_count,
            }
            self._hit_log.append({
                "query": question,
                "matched": best_entry.question,
                "confidence": best_score,
                "timestamp": time.time(),
            })
            return result

        return None

    def add_faq(self, question: str, answer: str, category: str,
                aliases: list[str] | None = None) -> FAQEntry:
        """Ajoute une nouvelle entree FAQ.

        Args:
            question: la question principale.
            answer: la reponse.
            category: jarvis, linux, cluster ou technique.
            aliases: variantes de formulation optionnelles.

        Returns:
            L'entree FAQ creee.
        """
        entry = FAQEntry(
            question=question.lower().strip(),
            answer=answer,
            category=category,
            aliases=[a.lower().strip() for a in (aliases or [])],
        )
        self._entries.append(entry)
        return entry

    def search_faq(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Recherche dans la FAQ par mots-cles (retourne les N meilleurs resultats).

        Args:
            query: termes de recherche.
            max_results: nombre max de resultats.

        Returns:
            Liste de dicts triee par pertinence decroissante.
        """
        normalized = query.lower().strip()
        if not normalized:
            return []

        scored: list[tuple[float, FAQEntry]] = []

        for entry in self._entries:
            # Score combine: fuzzy match + presence de mots-cles
            score = difflib.SequenceMatcher(
                None, normalized, entry.question.lower(),
            ).ratio()

            # Bonus mots-cles dans la question, les aliases et la reponse
            query_words = set(normalized.split())
            text_pool = (
                entry.question.lower() + " " +
                " ".join(entry.aliases) + " " +
                entry.answer.lower()
            )
            matching_words = sum(1 for w in query_words if w in text_pool)
            if query_words:
                keyword_bonus = matching_words / len(query_words) * 0.3
                score += keyword_bonus

            scored.append((score, entry))

        # Trier par score decroissant
        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[dict[str, Any]] = []
        for score, entry in scored[:max_results]:
            if score < 0.2:
                break
            results.append({
                "question": entry.question,
                "answer": entry.answer,
                "category": entry.category,
                "relevance": round(score, 3),
            })

        return results

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques de la FAQ.

        Returns:
            dict avec total, par categorie, top questions, derniers hits.
        """
        # Compteurs par categorie
        by_category: dict[str, int] = {}
        for entry in self._entries:
            by_category[entry.category] = by_category.get(entry.category, 0) + 1

        # Top questions (les plus demandees)
        top = sorted(self._entries, key=lambda e: e.hit_count, reverse=True)
        top_questions = [
            {"question": e.question, "hits": e.hit_count, "category": e.category}
            for e in top[:10]
            if e.hit_count > 0
        ]

        return {
            "total_faq": len(self._entries),
            "by_category": by_category,
            "total_hits": sum(e.hit_count for e in self._entries),
            "top_questions": top_questions,
            "recent_hits": self._hit_log[-10:],
        }


# ---------------------------------------------------------------------------
# Instance globale (singleton)
# ---------------------------------------------------------------------------
voice_faq = VoiceFAQ()


def find_faq_answer(question: str) -> dict[str, Any] | None:
    """Point d'entree pour le voice_router — cherche une reponse FAQ.

    Args:
        question: la question vocale de l'utilisateur.

    Returns:
        dict compatible voice_router ou None si pas de match.
    """
    result = voice_faq.find_answer(question)
    if result:
        return {
            "success": True,
            "method": "voice_faq",
            "result": result["answer"],
            "confidence": min(result["confidence"], 0.85),
            "module": "src.voice_faq",
            "faq_question": result["question"],
            "faq_category": result["category"],
        }
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="JARVIS Voice FAQ")
    parser.add_argument("--ask", help="Poser une question")
    parser.add_argument("--search", help="Rechercher dans la FAQ")
    parser.add_argument("--stats", action="store_true", help="Statistiques FAQ")
    parser.add_argument("--list", action="store_true", help="Lister toutes les FAQ")
    parser.add_argument("--category", help="Filtrer par categorie")
    args = parser.parse_args()

    if args.ask:
        result = find_faq_answer(args.ask)
        if result:
            print(f"[{result['faq_category'].upper()}] {result['faq_question']}")
            print(f"  → {result['result']}")
            print(f"  (confiance: {result['confidence']:.1%})")
        else:
            print(f"Aucune reponse trouvee pour: {args.ask}")

    elif args.search:
        results = voice_faq.search_faq(args.search, max_results=10)
        if results:
            for i, r in enumerate(results, 1):
                print(f"{i}. [{r['category'].upper()}] {r['question']}")
                print(f"   → {r['answer'][:100]}...")
                print(f"   (pertinence: {r['relevance']:.1%})")
                print()
        else:
            print(f"Aucun resultat pour: {args.search}")

    elif args.stats:
        stats = voice_faq.get_stats()
        print("=" * 50)
        print("JARVIS Voice FAQ — Statistiques")
        print("=" * 50)
        print(f"  Total FAQ       : {stats['total_faq']}")
        for cat, count in stats["by_category"].items():
            print(f"  {cat:15s} : {count}")
        print(f"  Total hits      : {stats['total_hits']}")
        if stats["top_questions"]:
            print("\nTop questions:")
            for q in stats["top_questions"]:
                print(f"  [{q['hits']}x] {q['question']}")

    elif args.list:
        cat_filter = args.category.lower() if args.category else None
        current_cat = ""
        for entry in voice_faq._entries:
            if cat_filter and entry.category != cat_filter:
                continue
            if entry.category != current_cat:
                current_cat = entry.category
                print(f"\n{'=' * 50}")
                print(f" {current_cat.upper()} ({sum(1 for e in voice_faq._entries if e.category == current_cat)} questions)")
                print(f"{'=' * 50}")
            print(f"  Q: {entry.question}")
            print(f"  R: {entry.answer[:100]}{'...' if len(entry.answer) > 100 else ''}")
            print()

    else:
        parser.print_help()
