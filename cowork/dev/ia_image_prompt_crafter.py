#!/usr/bin/env python3
"""ia_image_prompt_crafter.py — AI image prompt enrichment and optimization.
COWORK #235 — Batch 106: IA Generative

Usage:
    python dev/ia_image_prompt_crafter.py --craft "un chat sur la lune"
    python dev/ia_image_prompt_crafter.py --style cyberpunk
    python dev/ia_image_prompt_crafter.py --optimize
    python dev/ia_image_prompt_crafter.py --history
    python dev/ia_image_prompt_crafter.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "image_prompt_crafter.db"

STYLE_TEMPLATES = {
    "photorealistic": {
        "lighting": "natural lighting, golden hour, soft shadows",
        "composition": "rule of thirds, depth of field, bokeh background",
        "technical": "8K UHD, DSLR quality, sharp focus, high detail",
        "negative": "blurry, low quality, distorted, watermark, text"
    },
    "cyberpunk": {
        "lighting": "neon lights, purple and cyan glow, volumetric fog",
        "composition": "dynamic angle, wide shot, urban perspective",
        "technical": "digital art, highly detailed, concept art, artstation",
        "negative": "bright, cheerful, natural, rural, simple"
    },
    "fantasy": {
        "lighting": "magical glow, ethereal light, mystical atmosphere",
        "composition": "epic scale, dramatic perspective, painterly",
        "technical": "digital painting, fantasy art, detailed, vibrant colors",
        "negative": "modern, urban, technology, minimalist"
    },
    "anime": {
        "lighting": "cel shading, vibrant, clean lines",
        "composition": "manga style, dynamic pose, expressive",
        "technical": "anime art, studio quality, detailed, sharp lines",
        "negative": "photorealistic, 3D render, western cartoon"
    },
    "oil_painting": {
        "lighting": "chiaroscuro, dramatic lighting, warm tones",
        "composition": "classical composition, renaissance style, balanced",
        "technical": "oil on canvas, impasto technique, masterful brushwork",
        "negative": "digital, flat colors, modern, minimalist"
    },
    "minimalist": {
        "lighting": "clean, even lighting, white background",
        "composition": "centered, negative space, geometric",
        "technical": "clean design, vector-like, modern art",
        "negative": "cluttered, detailed, busy, complex"
    },
    "watercolor": {
        "lighting": "soft diffused light, pastel tones",
        "composition": "organic flow, loose edges, artistic",
        "technical": "watercolor painting, wet-on-wet, paper texture",
        "negative": "sharp edges, digital, photorealistic"
    },
    "steampunk": {
        "lighting": "warm amber glow, gas lamp lighting, sepia tones",
        "composition": "Victorian era, industrial detail, clockwork",
        "technical": "detailed illustration, brass and copper, intricate machinery",
        "negative": "modern, minimalist, clean, digital"
    }
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS prompts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        original TEXT NOT NULL,
        style TEXT,
        enriched TEXT NOT NULL,
        negative_prompt TEXT,
        lighting TEXT,
        composition TEXT,
        technical TEXT,
        word_count_original INTEGER,
        word_count_enriched INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS prompt_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        prompt_id INTEGER,
        details TEXT,
        FOREIGN KEY (prompt_id) REFERENCES prompts(id)
    )""")
    db.commit()
    return db

def enrich_prompt(description, style="photorealistic"):
    """Enrich a simple description with artistic details."""
    template = STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["photorealistic"])
    parts = [
        description.strip(),
        template["lighting"],
        template["composition"],
        template["technical"],
    ]
    enriched = ", ".join(parts)
    negative = template["negative"]
    return enriched, negative, template

def do_craft(description, style="photorealistic"):
    db = init_db()
    if style not in STYLE_TEMPLATES:
        style = "photorealistic"

    enriched, negative, template = enrich_prompt(description, style)

    cursor = db.execute("""INSERT INTO prompts (ts, original, style, enriched, negative_prompt,
                          lighting, composition, technical, word_count_original, word_count_enriched)
                          VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (datetime.now().isoformat(), description, style, enriched, negative,
                         template["lighting"], template["composition"], template["technical"],
                         len(description.split()), len(enriched.split())))
    prompt_id = cursor.lastrowid

    db.execute("INSERT INTO prompt_history (ts, action, prompt_id, details) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), "craft", prompt_id, f"style={style}"))
    db.commit()

    result = {
        "action": "craft",
        "prompt_id": prompt_id,
        "original": description,
        "style": style,
        "enriched_prompt": enriched,
        "negative_prompt": negative,
        "breakdown": {
            "lighting": template["lighting"],
            "composition": template["composition"],
            "technical": template["technical"]
        },
        "word_count": {
            "original": len(description.split()),
            "enriched": len(enriched.split())
        },
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_style(style_name=None):
    if style_name and style_name in STYLE_TEMPLATES:
        info = STYLE_TEMPLATES[style_name]
        return {
            "action": "style_detail",
            "style": style_name,
            "lighting": info["lighting"],
            "composition": info["composition"],
            "technical": info["technical"],
            "negative": info["negative"],
            "ts": datetime.now().isoformat()
        }
    return {
        "action": "list_styles",
        "styles": {k: {"lighting": v["lighting"][:40], "technical": v["technical"][:40]}
                   for k, v in STYLE_TEMPLATES.items()},
        "total": len(STYLE_TEMPLATES),
        "ts": datetime.now().isoformat()
    }

def do_optimize():
    db = init_db()
    last = db.execute("SELECT original, enriched, style FROM prompts ORDER BY id DESC LIMIT 1").fetchone()
    tips = [
        "Place the subject first in the prompt",
        "Add specific lighting details (golden hour, studio light, etc.)",
        "Include composition keywords (rule of thirds, close-up, etc.)",
        "Specify quality tags (8K, detailed, sharp focus)",
        "Use negative prompts to exclude unwanted elements",
        "Keep prompts under 75 tokens for best results (SDXL)",
        "Be specific about colors and materials",
        "Reference art styles and artists for consistency"
    ]
    result = {
        "action": "optimize",
        "tips": tips,
        "last_prompt": {
            "original": last[0],
            "enriched": last[1][:200],
            "style": last[2]
        } if last else None,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_history():
    db = init_db()
    rows = db.execute("SELECT id, ts, original, style, word_count_enriched FROM prompts ORDER BY id DESC LIMIT 20").fetchall()
    history = [{"id": r[0], "ts": r[1], "original": r[2][:80], "style": r[3], "enriched_words": r[4]} for r in rows]
    total = db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    style_dist = db.execute("SELECT style, COUNT(*) FROM prompts GROUP BY style ORDER BY COUNT(*) DESC").fetchall()
    result = {
        "action": "history",
        "total_prompts": total,
        "style_distribution": {r[0]: r[1] for r in style_dist},
        "recent": history,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    result = {
        "status": "ok",
        "total_prompts": total,
        "available_styles": list(STYLE_TEMPLATES.keys()),
        "total_styles": len(STYLE_TEMPLATES),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="IA Image Prompt Crafter — COWORK #235")
    parser.add_argument("--craft", type=str, metavar="DESC", help="Craft an enriched image prompt")
    parser.add_argument("--style", type=str, help="Set/show style")
    parser.add_argument("--optimize", action="store_true", help="Show optimization tips")
    parser.add_argument("--history", action="store_true", help="Show prompt history")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.craft:
        style = args.style or "photorealistic"
        print(json.dumps(do_craft(args.craft, style), ensure_ascii=False, indent=2))
    elif args.style:
        print(json.dumps(do_style(args.style), ensure_ascii=False, indent=2))
    elif args.optimize:
        print(json.dumps(do_optimize(), ensure_ascii=False, indent=2))
    elif args.history:
        print(json.dumps(do_history(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
