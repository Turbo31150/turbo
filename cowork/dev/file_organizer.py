#!/usr/bin/env python3
"""file_organizer.py

Organisateur de fichiers pour le Bureau et le répertoire Downloads.

Fonctionnalités :
* Analyse (``--scan DIR``) – liste les fichiers présents, les classe par type
  (images, documents, vidéos, archives, code, autres).
* ``--preview DIR`` – montre quels fichiers seraient déplacés et vers quels sous‑dossiers
  (mode dry‑run, aucune modification réelle).
* ``--organize DIR`` – crée les sous‑dossiers correspondants et déplace les fichiers.
* ``--undo`` – restaure le dernier jeu d'opérations de déplacement en lisant le
  journal ``.organizer_log.json`` situé dans le même répertoire que ce script.

Le script utilise uniquement la bibliothèque standard : ``shutil``, ``pathlib``,
``json`` et ``argparse``.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration des catégories de fichiers
# ---------------------------------------------------------------------------
FILE_TYPES: Dict[str, Tuple[str, ...]] = {
    "images": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"),
    "documents": (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".odt"),
    "videos": (".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"),
    "archives": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"),
    "code": (".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go", ".rb", ".php", ".html", ".css", ".json", ".yaml", ".yml"),
}

DEFAULT_CATEGORY = "others"
LOG_FILE = Path(__file__).with_name(".organizer_log.json")

# ---------------------------------------------------------------------------
# Helpers – catégorisation
# ---------------------------------------------------------------------------

def categorize(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    for cat, extensions in FILE_TYPES.items():
        if ext in extensions:
            return cat
    return DEFAULT_CATEGORY

def scan_directory(base_dir: Path) -> Dict[str, List[Path]]:
    """Return a dict mapping category -> list of files found directly under *base_dir* (non‑recursive)."""
    result: Dict[str, List[Path]] = {}
    for item in base_dir.iterdir():
        if item.is_file():
            cat = categorize(item)
            result.setdefault(cat, []).append(item)
    return result

# ---------------------------------------------------------------------------
# Reporting utilities
# ---------------------------------------------------------------------------
def print_scan(scan: Dict[str, List[Path]]):
    for cat, files in sorted(scan.items()):
        print(f"{cat.capitalize():<12}: {len(files)} fichier(s)")
        for f in files:
            print(f"   {f.name}")

def build_moves(scan: Dict[str, List[Path]], base_dir: Path) -> List[Tuple[Path, Path]]:
    """Return a list of tuples (src, dst) for each file in *scan*.
    Destination directories are ``base_dir / category``; they are created later.
    """
    moves = []
    for cat, files in scan.items():
        target_dir = base_dir / cat
        for src in files:
            dst = target_dir / src.name
            moves.append((src, dst))
    return moves

def preview_moves(moves: List[Tuple[Path, Path]]):
    if not moves:
        print("[file_organizer] Aucun fichier à déplacer.")
        return
    print("[file_organizer] Pré‑visualisation des déplacements :")
    for src, dst in moves:
        print(f"  {src.name}  →  {dst}")
    print(f"Total : {len(moves)} déplacement(s).")

# ---------------------------------------------------------------------------
# Execution – réellement déplacer / enregistrer le log
# ---------------------------------------------------------------------------
def execute_moves(moves: List[Tuple[Path, Path]]):
    performed = []
    for src, dst in moves:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            performed.append((str(src), str(dst)))
        except Exception as e:
            print(f"[file_organizer] Erreur lors du déplacement de {src}: {e}")
    # Save log for possible undo
    if performed:
        log_entry = {"timestamp": datetime.utcnow().isoformat() + "Z", "moves": performed}
        try:
            # Append to JSON log (list of entries)
            if LOG_FILE.is_file():
                with LOG_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = []
            data.append(log_entry)
            with LOG_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[file_organizer] Impossible d'écrire le journal : {e}")
    return performed

# ---------------------------------------------------------------------------
# Undo – restaurer le dernier jeu de déplacements
# ---------------------------------------------------------------------------
from datetime import datetime

def undo_last():
    if not LOG_FILE.is_file():
        print("[file_organizer] Aucun journal trouvé – aucune action à annuler.")
        return
    try:
        with LOG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[file_organizer] Erreur de lecture du journal : {e}")
        return
    if not data:
        print("[file_organizer] Le journal est vide – rien à annuler.")
        return
    last_entry = data.pop()  # remove the last run
    moves = last_entry.get("moves", [])
    if not moves:
        print("[file_organizer] Aucun déplacement à annuler dans la dernière entrée.")
    else:
        print("[file_organizer] Annulation du dernier jeu de déplacements …")
        for dst_str, src_str in moves:  # note: we stored (src, dst) – now we reverse
            src = Path(src_str)
            dst = Path(dst_str)
            if dst.is_file():
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(src))
                    print(f"  Restitué : {dst.name} → {src.parent}")
                except Exception as e:
                    print(f"[file_organizer] Erreur lors du retour de {dst}: {e}")
    # Write back the truncated log
    try:
        with LOG_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[file_organizer] Erreur d'écriture du journal après annulation : {e}")

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Organisateur de fichiers (Bureau / Downloads).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", metavar="DIR", help="Lister et catégoriser les fichiers du répertoire indiqué")
    group.add_argument("--preview", metavar="DIR", help="Afficher les déplacements prévus (dry‑run)")
    group.add_argument("--organize", metavar="DIR", help="Déplacer réellement les fichiers selon les catégories")
    group.add_argument("--undo", action="store_true", help="Annuler le dernier jeu de déplacements")
    args = parser.parse_args()

    if args.scan:
        base = Path(args.scan).expanduser().resolve()
        if not base.is_dir():
            print(f"[file_organizer] Répertoire invalide : {base}")
            sys.exit(1)
        scan = scan_directory(base)
        print_scan(scan)
    elif args.preview:
        base = Path(args.preview).expanduser().resolve()
        if not base.is_dir():
            print(f"[file_organizer] Répertoire invalide : {base}")
            sys.exit(1)
        scan = scan_directory(base)
        moves = build_moves(scan, base)
        preview_moves(moves)
    elif args.organize:
        base = Path(args.organize).expanduser().resolve()
        if not base.is_dir():
            print(f"[file_organizer] Répertoire invalide : {base}")
            sys.exit(1)
        scan = scan_directory(base)
        moves = build_moves(scan, base)
        if not moves:
            print("[file_organizer] Aucun fichier à organiser.")
            return
        print("[file_organizer] Déplacement des fichiers…")
        performed = execute_moves(moves)
        print(f"[file_organizer] Opération terminée – {len(performed)} fichier(s) déplacé(s).")
    elif args.undo:
        undo_last()

if __name__ == "__main__":
    main()
