#!/usr/bin/env python3
"""Windows TTS — Edge TTS Neural (Denise) + envoi Telegram.

Usage:
  python dev/win_tts.py --speak "Texte a dire"
  python dev/win_tts.py --speak "Texte" --telegram
  python dev/win_tts.py --speak "Texte" --save fichier.ogg
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# Config Telegram
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

# Voix par defaut — Edge TTS Neural (femme, francais)
DEFAULT_VOICE = "fr-FR-DeniseNeural"


def clean_text_for_speech(text):
    """Nettoie le texte pour la synthese vocale — pas de ponctuation ni symboles."""
    text = re.sub(r'[^\w\s\-àâäéèêëïîôùûüÿçœæÀÂÄÉÈÊËÏÎÔÙÛÜŸÇŒÆ]', ' ', text, flags=re.UNICODE)
    text = text.replace('_', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def speak_to_mp3(text, voice=DEFAULT_VOICE, output_path=None):
    """Genere un fichier MP3 avec Edge TTS Neural."""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")

    result = subprocess.run(
        ["edge-tts", "--voice", voice, "--text", text, "--write-media", output_path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return None, result.stderr
    return output_path, None


def mp3_to_ogg(mp3_path, ogg_path=None):
    """Convertit MP3 en OGG Opus (format Telegram Voice)."""
    if not ogg_path:
        ogg_path = mp3_path.replace(".mp3", ".ogg")

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, "-c:a", "libopus",
         "-b:a", "96k", "-ar", "48000", "-ac", "1",
         "-af", "volume=1.3,acompressor=threshold=-20dB:ratio=3:attack=5:release=50",
         ogg_path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return None, result.stderr
    return ogg_path, None


def send_voice_telegram(ogg_path, chat_id=TELEGRAM_CHAT_ID):
    """Envoie un fichier vocal OGG sur Telegram."""
    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice",
         "-F", f"chat_id={chat_id}",
         "-F", f"voice=@{ogg_path}"],
        capture_output=True, text=True, timeout=30
    )
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            voice = data["result"].get("voice", {})
            return {"ok": True, "duration": voice.get("duration", 0)}
        return {"ok": False, "error": data.get("description", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def speak_and_send(text, voice=DEFAULT_VOICE, telegram=False, save_path=None):
    """Pipeline complet: Edge TTS -> MP3 -> OGG Opus -> Telegram."""
    # 0. Nettoyer le texte
    text = clean_text_for_speech(text)
    if not text:
        return {"ok": False, "step": "clean", "error": "texte vide apres nettoyage"}

    # 1. Generer MP3 via Edge TTS
    mp3_path, err = speak_to_mp3(text, voice)
    if err:
        return {"ok": False, "step": "tts", "error": err}

    # 2. Convertir en OGG Opus (volume boost + compression)
    ogg_path = save_path if save_path else None
    ogg_path, err = mp3_to_ogg(mp3_path, ogg_path)
    if err:
        return {"ok": False, "step": "convert", "error": err}

    result = {"ok": True, "mp3": mp3_path, "ogg": ogg_path, "voice": voice}

    # 3. Envoyer sur Telegram
    if telegram:
        tg_result = send_voice_telegram(ogg_path)
        result["telegram"] = tg_result
        if tg_result.get("ok"):
            result["duration"] = tg_result.get("duration", 0)

    # Nettoyage MP3 temporaire
    if not save_path:
        try:
            os.remove(mp3_path)
        except OSError:
            pass

    return result


def main():
    parser = argparse.ArgumentParser(description="Edge TTS Neural + Telegram Voice")
    parser.add_argument("--speak", type=str, help="Texte a synthetiser")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE,
                        help=f"Voix Edge TTS (defaut: {DEFAULT_VOICE})")
    parser.add_argument("--telegram", action="store_true",
                        help="Envoyer le vocal sur Telegram")
    parser.add_argument("--save", type=str, help="Sauvegarder en fichier OGG")

    args = parser.parse_args()

    if args.speak:
        result = speak_and_send(
            args.speak,
            voice=args.voice,
            telegram=args.telegram,
            save_path=args.save
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
