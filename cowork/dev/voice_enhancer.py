#!/usr/bin/env python3
"""voice_enhancer.py — Améliore la qualité des fichiers audio TTS.

Fonctionnalités principales :
  --enhance   Applique des filtres ffmpeg (normalisation du volume, noise gate,
               compresseur) et génère trois variantes (lent, normal, rapide).
  --test      Exécute un test rapide en générant un ton sinusoidal, le passe
               dans le pipeline d'amélioration et montre le résultat.
  --compare   Compare les fichiers produits et renvoie un JSON contenant les
               chemins vers les versions générées.
  --settings  Affiche les paramètres de filtres utilisés (ffmpeg filter
               chain).
  --help      Affiche l'aide de la ligne de commande.

Le script n'utilise que la bibliothèque standard Python, mais fait appel à
ffmpeg via `subprocess`. ffmpeg doit être installé et disponible dans le PATH.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

# ------------------------------------------------------------
# Configuration des filtres ffmpeg (modifiable via --settings)
# ------------------------------------------------------------
DEFAULT_FILTERS = [
    "loudnorm=I=-16:TP=-1.5:LRA=11",  # normalisation du volume
    "afftdn=nf=-25",                  # réduction du bruit
    "compand=attacks=0:points=-80/-80|-30/-30|0/-20:soft-knee=6:gain=5",  # compresseur
]


def run_ffmpeg(input_path: Path, output_path: Path, extra_filters: List[str] = None) -> None:
    """Exécute ffmpeg avec les filtres définis.
    Lève une exception si ffmpeg retourne un code d'erreur.
    """
    if not input_path.is_file():
        raise FileNotFoundError(f"Fichier d'entrée introuvable : {input_path}")
    filters = ",".join(DEFAULT_FILTERS + (extra_filters or []))
    cmd = [
        "ffmpeg",
        "-y",  # overwrite
        "-i", str(input_path),
        "-af", filters,
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg a échoué : {result.stderr}")


def enhance(input_file: str, output_dir: str) -> List[Path]:
    """Applique les filtres et crée trois versions avec vitesses différentes.
    Retourne la liste des chemins générés.
    """
    inp = Path(input_file)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Versions : lent (0.8x), normal (1.0x), rapide (1.2x)
    speed_factors = {
        "slow": 0.8,
        "normal": 1.0,
        "fast": 1.2,
    }
    generated = []
    for label, factor in speed_factors.items():
        tmp_path = out_dir / f"{inp.stem}_{label}.wav"
        # 1️⃣ Appliquer les filtres de base
        run_ffmpeg(inp, tmp_path)
        # 2️⃣ Ajuster la vitesse si nécessaire (ffmpeg atempo fonctionne sur mp3/ogg, on utilise
        #    le filtre asetrate + atempo pour wav)
        if factor != 1.0:
            final_path = out_dir / f"{inp.stem}_{label}_adj.wav"
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(tmp_path),
                "-filter_complex",
                f"[0:a]asetrate=44100*{factor},atempo={factor}[a]",
                "-map", "[a]",
                str(final_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"ffmpeg (speed) a échoué : {res.stderr}")
            generated.append(final_path)
            tmp_path.unlink(missing_ok=True)
        else:
            generated.append(tmp_path)
    return generated


def test_pipeline() -> Dict[str, str]:
    """Génère un ton sinusoidal 1 s, le traite et renvoie les chemins.
    """
    tmp_dir = Path("tmp_voice_test")
    tmp_dir.mkdir(exist_ok=True)
    src = tmp_dir / "tone.wav"
    # Générer le ton avec ffmpeg
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(src)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg (tone) a échoué : {res.stderr}")
    out_dir = tmp_dir / "out"
    out_paths = enhance(str(src), str(out_dir))
    return {"input": str(src), "outputs": [str(p) for p in out_paths]}


def compare_files(paths: List[Path]) -> str:
    """Retourne un JSON string contenant les métadonnées de chaque fichier.
    """
    data = []
    for p in paths:
        try:
            # obtenir la durée avec ffprobe (via ffmpeg -i)
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(p)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            duration = float(res.stdout.strip()) if res.returncode == 0 else None
        except Exception:
            duration = None
        data.append({"path": str(p), "size_bytes": p.stat().st_size, "duration_sec": duration})
    return json.dumps(data, ensure_ascii=False, indent=2)


def show_settings() -> str:
    """Affiche les filtres ffmpeg par défaut sous forme JSON."""
    return json.dumps({"filters": DEFAULT_FILTERS}, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Améliore la qualité des fichiers vocaux TTS via ffmpeg.")
    subparsers = parser.add_subparsers(dest="command")

    # enhance
    p_enh = subparsers.add_parser("--enhance", help="Applique les filtres et génère 3 versions.")
    p_enh.add_argument("--input", required=True, help="Chemin du fichier audio source (wav/ogg/mp3).")
    p_enh.add_argument("--output-dir", default="enhanced", help="Dossier où enregistrer les fichiers générés.")

    # test
    subparsers.add_parser("--test", help="Exécute un test rapide du pipeline.")

    # compare
    p_cmp = subparsers.add_parser("--compare", help="Compare les fichiers produits (JSON).")
    p_cmp.add_argument("--files", nargs="+", required=True, help="Liste des fichiers à comparer.")

    # settings
    subparsers.add_parser("--settings", help="Affiche les paramètres de filtres utilisés.")

    args = parser.parse_args()

    if args.command == "--enhance":
        try:
            out_paths = enhance(args.input, args.output_dir)
            print(json.dumps({"generated": [str(p) for p in out_paths]}, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Erreur : {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "--test":
        try:
            result = test_pipeline()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Erreur lors du test : {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "--compare":
        try:
            paths = [Path(p) for p in args.files]
            print(compare_files(paths))
        except Exception as e:
            print(f"Erreur lors de la comparaison : {e}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "--settings":
        print(show_settings())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
