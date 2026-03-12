#!/usr/bin/env python3
"""JARVIS TTS Cache Manager — Gestion du cache Text-to-Speech."""
import json, sys, os, subprocess, time, glob
from datetime import datetime, timedelta

CACHE_DIRS = [
    os.path.expandvars(r"%TEMP%"),
    "C:/Users/franc/.openclaw/workspace/dev/tts_cache",
]
TTS_VOICE = "fr-FR-HenriNeural"
CACHE_DIR = "C:/Users/franc/.openclaw/workspace/dev/tts_cache"
MAX_AGE_DAYS = 7

TOP_PHRASES = [
    "Bonjour Franck",
    "Cluster en ligne, tous les noeuds operationnels",
    "Alerte, un noeud est hors ligne",
    "Signal trading detecte",
    "Rapport quotidien pret",
    "Backup termine avec succes",
    "Erreur detectee dans les logs",
    "Systeme optimise",
    "Nouvelle tache ajoutee",
    "Scan de securite termine",
    "Aucune anomalie detectee",
    "Trading autorise, capital suffisant",
    "Attention, limite de drawdown proche",
    "Email envoye avec succes",
    "Commande executee",
    "Connexion au cluster retablie",
    "Mise a jour terminee",
    "Bonne nuit Franck",
    "Tache terminee avec succes",
    "En attente d'instructions",
]

def get_cache_stats():
    total_size = 0
    total_files = 0
    old_files = 0
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    for cache_dir in CACHE_DIRS:
        if not os.path.exists(cache_dir):
            continue
        for f in os.listdir(cache_dir):
            if f.endswith((".mp3", ".wav", ".ogg")):
                fp = os.path.join(cache_dir, f)
                total_files += 1
                total_size += os.path.getsize(fp)
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime < cutoff:
                    old_files += 1

    return {"files": total_files, "size_mb": round(total_size / 1048576, 2), "old": old_files}

def clean_old_files():
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    removed = 0
    freed = 0

    for cache_dir in CACHE_DIRS:
        if not os.path.exists(cache_dir):
            continue
        for f in os.listdir(cache_dir):
            if f.endswith((".mp3", ".wav", ".ogg")):
                fp = os.path.join(cache_dir, f)
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime < cutoff:
                    size = os.path.getsize(fp)
                    try:
                        os.remove(fp)
                        removed += 1
                        freed += size
                    except: pass

    return removed, round(freed / 1048576, 2)

def pregen_phrases():
    os.makedirs(CACHE_DIR, exist_ok=True)
    generated = 0
    errors = 0

    for phrase in TOP_PHRASES:
        safe_name = phrase[:40].replace(" ", "_").replace(",", "").replace("'", "").lower()
        output = os.path.join(CACHE_DIR, f"{safe_name}.mp3")
        if os.path.exists(output):
            continue  # Already cached
        try:
            result = subprocess.run(
                ["edge-tts", "--voice", TTS_VOICE, "--text", phrase, "--write-media", output],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(output):
                generated += 1
                print(f"  Generated: {phrase[:50]}")
            else:
                errors += 1
        except Exception as e:
            errors += 1

    return generated, errors

if __name__ == "__main__":
    if "--stats" in sys.argv:
        stats = get_cache_stats()
        print(f"[TTS CACHE] {stats['files']} fichiers, {stats['size_mb']} MB")
        print(f"  Anciens (>{MAX_AGE_DAYS}j): {stats['old']}")
        print(f"  Top phrases: {len(TOP_PHRASES)}")
        cached = len([f for f in os.listdir(CACHE_DIR) if f.endswith(".mp3")]) if os.path.exists(CACHE_DIR) else 0
        print(f"  Pre-generes: {cached}/{len(TOP_PHRASES)}")

    elif "--clean" in sys.argv:
        removed, freed = clean_old_files()
        print(f"[TTS CACHE] Supprime: {removed} fichiers, {freed} MB liberes")

    elif "--pregen" in sys.argv:
        print(f"[TTS CACHE] Pre-generation de {len(TOP_PHRASES)} phrases...")
        generated, errors = pregen_phrases()
        print(f"  Generes: {generated} | Erreurs: {errors}")

    else:
        print("Usage: tts_cache_manager.py --stats | --clean | --pregen")
