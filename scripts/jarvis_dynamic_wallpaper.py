"""jarvis_dynamic_wallpaper.py — Fond d'ecran dynamique JARVIS.

Regenere le wallpaper toutes les N minutes avec les donnees GPU/cluster
reelles integrees dans l'image HUD.

Usage:
    python scripts/jarvis_dynamic_wallpaper.py           # une fois
    python scripts/jarvis_dynamic_wallpaper.py --loop 5  # toutes les 5 min
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
CX, CY = W // 2, H // 2
OUTPUT = Path.home() / "Pictures" / "JARVIS" / "wallpaper.png"

# Couleurs
BG = (5, 8, 18)
CYAN = (0, 180, 235)
CYAN_DIM = (0, 80, 120)
CYAN_DARK = (0, 40, 65)
CYAN_GLOW = (0, 220, 255)
WHITE = (200, 220, 240)
GREEN = (0, 200, 100)
ORANGE = (220, 120, 0)
RED = (220, 50, 50)


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _load_fonts():
    try:
        return {
            "title": ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 64),
            "sub": ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-L.ttf", 20),
            "panel": ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 13),
            "data": ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf", 12),
            "tiny": ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", 10),
            "clock": ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", 36),
        }
    except Exception:
        d = ImageFont.load_default()
        return {"title": d, "sub": d, "panel": d, "data": d, "tiny": d, "clock": d}


def collect_data() -> dict:
    """Collecte les donnees systeme temps reel."""
    data = {}

    # GPU
    data["gpus"] = []
    output = _run(["nvidia-smi",
        "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,fan.speed,power.draw",
        "--format=csv,noheader,nounits"])
    for line in output.split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 8:
            data["gpus"].append({
                "id": parts[0], "name": parts[1][:18], "temp": int(parts[2]),
                "util": int(parts[3]), "vram_used": int(parts[4]), "vram_total": int(parts[5]),
                "fan": parts[6], "power": parts[7],
            })

    # CPU/RAM
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            data["load"] = f"{parts[0]} / {parts[1]} / {parts[2]}"
    except Exception:
        data["load"] = "?"

    output = _run(["free", "-h"])
    for line in output.split("\n"):
        if line.startswith("Mem:"):
            parts = line.split()
            data["ram"] = f"{parts[2]} / {parts[1]}"

    # Cluster
    data["m1"] = bool(_run(["curl", "-s", "--max-time", "1", "http://127.0.0.1:1234/api/v1/models"]))
    data["ol1"] = bool(_run(["curl", "-s", "--max-time", "1", "http://127.0.0.1:11434/api/tags"]))

    # Services
    output = _run("systemctl --user list-units 'jarvis-*' --no-pager --no-legend 2>/dev/null | grep -c 'active running'")
    data["services"] = int(output) if output.isdigit() else 0

    # Uptime
    data["uptime"] = _run(["uptime", "-p"]).replace("up ", "")

    # Disk
    output = _run(["df", "-h", "/"])
    for line in output.split("\n"):
        if line.startswith("/"):
            parts = line.split()
            data["disk"] = f"{parts[2]} / {parts[1]} ({parts[4]})"

    return data


def generate_wallpaper(data: dict):
    """Genere le wallpaper avec les donnees temps reel."""
    fonts = _load_fonts()
    img = Image.new("RGB", (W, H), BG)

    # Gradient radial
    for y in range(0, H, 2):
        for x in range(0, W, 3):
            dx, dy = x - CX, y - CY
            dist = math.sqrt(dx*dx + dy*dy)
            ratio = 1 - min(1, dist / 800)
            r = int(5 + 12 * ratio)
            g = int(8 + 20 * ratio)
            b = int(18 + 40 * ratio)
            for px in range(3):
                if x + px < W:
                    img.putpixel((x + px, y), (r, g, b))
                    if y + 1 < H:
                        img.putpixel((x + px, y + 1), (r, g, b))

    draw = ImageDraw.Draw(img, "RGBA")

    # Arcs HUD
    for radius in [130, 200, 280, 380]:
        alpha = max(15, 50 - radius // 8)
        for start in range(0, 360, 72):
            draw.arc([CX-radius, CY-radius, CX+radius, CY+radius],
                     start, start + 50, fill=(*CYAN_DIM, alpha), width=1)

    # Cercles
    for r in [110, 170, 260]:
        draw.ellipse([CX-r, CY-r, CX+r, CY+r], outline=(*CYAN_DARK, 40), width=1)

    # Titre
    draw.text((CX - 170, CY - 50), "J.A.R.V.I.S", fill=(*CYAN_GLOW, 220), font=fonts["title"])
    draw.line([(CX - 180, CY + 25), (CX + 180, CY + 25)], fill=(*CYAN, 60), width=1)
    draw.text((CX - 155, CY + 32), "Turbo AI Cluster — M1 La Créatrice", fill=(*WHITE, 140), font=fonts["sub"])

    # Heure au centre bas
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    draw.text((CX - 55, CY + 65), time_str, fill=(*CYAN_GLOW, 180), font=fonts["clock"])
    draw.text((CX - 80, CY + 105), now.strftime("%A %d %B %Y"), fill=(*CYAN_DIM, 120), font=fonts["panel"])

    # === PANNEAU GAUCHE: Systeme ===
    px, py = 40, 180
    draw.rectangle([(px, py), (px + 290, py + 280)], outline=(*CYAN_DIM, 35))
    draw.line([(px, py), (px + 290, py)], fill=(*CYAN, 70), width=2)
    draw.text((px + 10, py + 5), "SYSTEM MONITOR", fill=(*CYAN, 180), font=fonts["panel"])

    stats = [
        ("LOAD", data.get("load", "?")),
        ("RAM", data.get("ram", "?")),
        ("DISK", data.get("disk", "?")),
        ("UPTIME", data.get("uptime", "?")),
        ("SERVICES", f"{data.get('services', 0)} actifs"),
    ]
    for i, (label, value) in enumerate(stats):
        y = py + 30 + i * 48
        draw.text((px + 12, y), label, fill=(*CYAN_DIM, 150), font=fonts["tiny"])
        draw.text((px + 12, y + 13), str(value)[:35], fill=(*WHITE, 170), font=fonts["data"])

    # Cluster status
    y = py + 30 + 5 * 48
    m1_color = GREEN if data.get("m1") else RED
    ol1_color = GREEN if data.get("ol1") else RED
    draw.text((px + 12, y), "CLUSTER", fill=(*CYAN_DIM, 150), font=fonts["tiny"])
    draw.text((px + 12, y + 13), "M1:", fill=(*WHITE, 150), font=fonts["data"])
    draw.text((px + 40, y + 13), "OK" if data.get("m1") else "OFF", fill=(*m1_color, 200), font=fonts["data"])
    draw.text((px + 80, y + 13), "OL1:", fill=(*WHITE, 150), font=fonts["data"])
    draw.text((px + 115, y + 13), "OK" if data.get("ol1") else "OFF", fill=(*ol1_color, 200), font=fonts["data"])

    # === PANNEAU DROIT: GPUs ===
    px2 = W - 330
    draw.rectangle([(px2, py), (px2 + 290, py + 380)], outline=(*CYAN_DIM, 35))
    draw.line([(px2, py), (px2 + 290, py)], fill=(*CYAN, 70), width=2)
    draw.text((px2 + 10, py + 5), f"GPU CLUSTER [{len(data.get('gpus', []))}x NVIDIA]", fill=(*CYAN, 180), font=fonts["panel"])

    for i, g in enumerate(data.get("gpus", [])):
        y = py + 28 + i * 58
        # Nom
        draw.text((px2 + 12, y), f"GPU{g['id']} {g['name']}", fill=(*CYAN_DIM, 160), font=fonts["tiny"])
        # Temp
        temp_color = GREEN if g["temp"] < 60 else ORANGE if g["temp"] < 75 else RED
        draw.text((px2 + 12, y + 13), f"{g['temp']}°C", fill=(*temp_color, 200), font=fonts["data"])
        draw.text((px2 + 60, y + 13), f"{g['util']}%", fill=(*WHITE, 160), font=fonts["data"])
        # VRAM bar
        vram_pct = g["vram_used"] / g["vram_total"] * 100 if g["vram_total"] > 0 else 0
        bar_color = CYAN if vram_pct < 60 else ORANGE if vram_pct < 85 else RED
        draw.text((px2 + 100, y + 13), f"{g['vram_used']}/{g['vram_total']}MB", fill=(*CYAN_DIM, 130), font=fonts["data"])
        # Barre
        draw.rectangle([(px2 + 12, y + 30), (px2 + 275, y + 35)], outline=(*CYAN_DARK, 50))
        bar_w = int(263 * vram_pct / 100)
        draw.rectangle([(px2 + 12, y + 30), (px2 + 12 + bar_w, y + 35)], fill=(*bar_color, 80))

    # === PANNEAU BAS: Voice ===
    bx, by = 380, H - 160
    draw.rectangle([(bx, by), (bx + 500, by + 120)], outline=(*CYAN_DIM, 35))
    draw.line([(bx, by), (bx + 500, by)], fill=(*CYAN, 70), width=2)
    draw.text((bx + 10, by + 5), "VOICE CONTROL & ANALYTICS", fill=(*CYAN, 180), font=fonts["panel"])
    draw.text((bx + 12, by + 25), "898 VOICE COMMANDS  •  5 MODULES  •  VAD ACTIVE", fill=(*WHITE, 140), font=fonts["data"])
    draw.text((bx + 12, by + 42), "PIPELINE v3.1  •  WHISPER STT  •  PIPER TTS  •  VOSK WAKE", fill=(*CYAN_DIM, 110), font=fonts["data"])
    draw.text((bx + 12, by + 59), "124 STT CORRECTIONS  •  MACROS  •  IA FALLBACK", fill=(*CYAN_DIM, 100), font=fonts["data"])
    draw.text((bx + 12, by + 80), f"Dashboard: http://127.0.0.1:8088  •  Super+J Voice  •  Super+Shift+W Web", fill=(*CYAN_DARK, 80), font=fonts["data"])

    # Lignes decoratives
    for i in range(4):
        o = i * 12
        a = 25 - i * 5
        draw.line([(o, 0), (0, o)], fill=(*CYAN_DIM, a))
        draw.line([(W-o, 0), (W, o)], fill=(*CYAN_DIM, a))
        draw.line([(o, H), (0, H-o)], fill=(*CYAN_DIM, a))
        draw.line([(W-o, H), (W, H-o)], fill=(*CYAN_DIM, a))

    # Sauvegarder
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUTPUT), quality=95)


def apply_wallpaper():
    """Applique le wallpaper via gsettings."""
    uri = f"file://{OUTPUT}"
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                   capture_output=True, timeout=5)
    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
                   capture_output=True, timeout=5)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Dynamic Wallpaper")
    parser.add_argument("--loop", type=int, default=0, help="Intervalle en minutes (0=une fois)")
    args = parser.parse_args()

    if args.loop > 0:
        print(f"Wallpaper dynamique JARVIS — rafraichissement toutes les {args.loop} minutes")
        while True:
            try:
                data = collect_data()
                generate_wallpaper(data)
                apply_wallpaper()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Wallpaper mis a jour ({len(data.get('gpus', []))} GPUs)")
            except Exception as e:
                print(f"Erreur: {e}")
            time.sleep(args.loop * 60)
    else:
        data = collect_data()
        generate_wallpaper(data)
        apply_wallpaper()
        print(f"Wallpaper JARVIS genere avec donnees temps reel ({len(data.get('gpus', []))} GPUs)")


if __name__ == "__main__":
    main()
