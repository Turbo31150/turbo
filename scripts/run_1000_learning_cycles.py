"""JARVIS — 1000 cycles d'apprentissage distribues sur le cluster.

Chaque cycle genere des paires training (input vocal -> output domino)
en utilisant M1/M2/M3/OL1 en parallele. Les resultats sont valides,
dedupliques et ajoutes au dataset JSONL.
"""
import sys, os, json, time, random, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.domino_pipelines import DOMINO_PIPELINES

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

JSONL_PATH = Path("F:/BUREAU/turbo/data/domino_learning_dataset.jsonl")
TARGET_CYCLES = int(os.environ.get("CYCLES", "1000"))
BATCH_SIZE = 10  # examples per cluster request
MAX_WORKERS = 6

# All domino IDs and categories for reference
DOMINO_IDS = [dp.id for dp in DOMINO_PIPELINES]
DOMINO_MAP = {dp.id: {"cat": dp.category, "triggers": dp.trigger_vocal, "desc": dp.description} for dp in DOMINO_PIPELINES}
CATEGORIES = list(set(dp.category for dp in DOMINO_PIPELINES))

# Cluster nodes
NODES = {
    "M1": {"url": "http://10.5.0.2:1234/api/v1/chat", "model": "qwen3-8b",
            "key": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7", "type": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-coder-v2-lite-instruct",
            "key": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4", "type": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "mistral-7b-instruct-v0.3",
            "key": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux", "type": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
             "key": None, "type": "ollama"},
}

# Variation templates for prompts
VARIATION_STYLES = [
    "familier avec tutoiement",
    "formel avec vouvoiement",
    "argot et abreviations",
    "phrases courtes imperatives",
    "questions naturelles",
    "phrases avec fautes de frappe courantes",
    "langage parle avec hesitations",
    "style SMS/texto",
    "phrases longues descriptives",
    "style professionnel technique",
]

CONTEXT_VARS = [
    "matin tot (6h)", "debut de journee (9h)", "pause cafe (10h30)",
    "avant dejeuner (12h)", "apres-midi focus (14h)", "fin de journee (17h)",
    "soir relax (20h)", "nuit urgence (23h)", "weekend detente",
    "jour ferie", "session trading active", "debug urgent",
    "presentation client", "session dev intense", "maintenance planifiee",
]


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER QUERY
# ══════════════════════════════════════════════════════════════════════════════

def query_lmstudio(node_name: str, prompt: str, max_tokens: int = 512, timeout: int = 25) -> str:
    """Query LM Studio node."""
    node = NODES[node_name]
    body = json.dumps({
        "model": node["model"],
        "input": f"/nothink\n{prompt}",
        "temperature": 0.7 + random.random() * 0.2,  # 0.7-0.9 for variety
        "max_output_tokens": max_tokens,
        "stream": False, "store": False,
    }).encode()
    req = urllib.request.Request(node["url"], data=body,
                                headers={"Content-Type": "application/json",
                                         "Authorization": node["key"]})
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = json.loads(resp.read())
    for item in reversed(data.get("output", [])):
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        return c["text"].strip()
    return ""


def query_ollama(prompt: str, max_tokens: int = 512, timeout: int = 20) -> str:
    """Query Ollama node."""
    body = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False,
        "options": {"temperature": 0.7 + random.random() * 0.2, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())["message"]["content"].strip()


def query_node(node_name: str, prompt: str) -> str:
    """Query any node."""
    if NODES[node_name]["type"] == "ollama":
        return query_ollama(prompt)
    return query_lmstudio(node_name, prompt)


# ══════════════════════════════════════════════════════════════════════════════
# TRAINING PAIR GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt(cycle: int) -> tuple[str, str]:
    """Build a prompt for training pair generation. Returns (prompt, node_name)."""
    # Pick random dominos to generate variations for
    dominos = random.sample(DOMINO_IDS, min(5, len(DOMINO_IDS)))
    style = random.choice(VARIATION_STYLES)
    context = random.choice(CONTEXT_VARS)
    node = random.choice(list(NODES.keys()))

    domino_info = "\n".join([
        f"- {did}: {DOMINO_MAP[did]['desc']} (category: {DOMINO_MAP[did]['cat']}, triggers: {DOMINO_MAP[did]['triggers'][:2]})"
        for did in dominos
    ])

    prompt = f"""Genere exactement {BATCH_SIZE} paires d'entrainement pour un assistant vocal francais JARVIS.
Style: {style}. Contexte: {context}.

Dominos cibles:
{domino_info}

Format STRICT — une ligne JSON par paire, RIEN d'autre:
{{"input":"phrase naturelle en francais","output":"domino:{dominos[0]}","category":"{DOMINO_MAP[dominos[0]]['cat']}"}}

Regles:
- Phrases NATURELLES comme un vrai humain parlerait
- Varier les formulations (pas de copier-coller des triggers)
- Inclure des variations: fautes, argot, abreviations selon le style
- Chaque ligne est un JSON valide independant
- PAS de markdown, PAS de ```json, PAS d'explication
- Utiliser UNIQUEMENT les domino IDs fournis ci-dessus"""

    return prompt, node


def parse_training_pairs(raw: str) -> list[dict]:
    """Parse raw LLM output into valid training pairs."""
    pairs = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        # Clean common issues
        line = line.rstrip(",")
        try:
            obj = json.loads(line)
            # Validate structure
            if "input" in obj and "output" in obj:
                inp = obj["input"].strip()
                out = obj["output"].strip()
                # Validate output format
                if out.startswith("domino:") and out.replace("domino:", "") in DOMINO_IDS:
                    pairs.append({
                        "input": inp,
                        "output": out,
                        "category": obj.get("category", "unknown"),
                    })
        except json.JSONDecodeError:
            continue
    return pairs


def run_cycle(cycle_id: int) -> list[dict]:
    """Run a single learning cycle."""
    prompt, node = build_prompt(cycle_id)
    try:
        raw = query_node(node, prompt)
        pairs = parse_training_pairs(raw)
        return pairs
    except Exception as e:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION
# ══════════════════════════════════════════════════════════════════════════════

def load_existing() -> set:
    """Load existing training inputs for dedup."""
    existing = set()
    if JSONL_PATH.exists():
        for line in JSONL_PATH.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    obj = json.loads(line)
                    existing.add(obj.get("input", "").lower().strip())
                except json.JSONDecodeError:
                    pass
    return existing


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print(f"JARVIS — 1000 CYCLES D'APPRENTISSAGE DISTRIBUES")
    print(f"Noeuds: {', '.join(NODES.keys())} | Batch: {BATCH_SIZE}/cycle")
    print(f"Dominos: {len(DOMINO_IDS)} | Categories: {len(CATEGORIES)}")
    print("=" * 70)

    existing = load_existing()
    print(f"Dataset existant: {len(existing)} exemples uniques")

    START = time.time()
    total_generated = 0
    total_valid = 0
    total_dupes = 0
    total_errors = 0
    cycle = 0
    wave = 0
    node_stats = {n: {"ok": 0, "fail": 0, "pairs": 0} for n in NODES}

    # Open file for appending
    with open(JSONL_PATH, "a", encoding="utf-8") as f:

        while cycle < TARGET_CYCLES:
            wave += 1
            batch_cycles = min(MAX_WORKERS, TARGET_CYCLES - cycle)
            wave_start = time.time()

            # Launch parallel cycles
            with ThreadPoolExecutor(max_workers=batch_cycles) as pool:
                futures = {}
                for i in range(batch_cycles):
                    prompt, node = build_prompt(cycle + i)
                    fut = pool.submit(query_node, node, prompt)
                    futures[fut] = (cycle + i, node)

                wave_pairs = []
                for fut in as_completed(futures):
                    cid, node = futures[fut]
                    try:
                        raw = fut.result()
                        pairs = parse_training_pairs(raw)
                        total_generated += len(pairs)
                        node_stats[node]["ok"] += 1
                        node_stats[node]["pairs"] += len(pairs)

                        # Dedup
                        for p in pairs:
                            key = p["input"].lower().strip()
                            if key not in existing and len(key) > 5:
                                existing.add(key)
                                wave_pairs.append(p)
                                total_valid += 1
                            else:
                                total_dupes += 1
                    except Exception as e:
                        node_stats[node]["fail"] += 1
                        total_errors += 1

            # Write valid pairs
            for p in wave_pairs:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
            f.flush()

            cycle += batch_cycles
            wave_ms = (time.time() - wave_start) * 1000
            elapsed = time.time() - START

            # Progress report every 10 waves
            if wave % 10 == 0 or cycle >= TARGET_CYCLES:
                rate = total_valid / elapsed if elapsed > 0 else 0
                print(f"  Wave {wave:4d} | Cycle {cycle:4d}/{TARGET_CYCLES} | "
                      f"+{len(wave_pairs)} valid | Total: {total_valid} unique | "
                      f"Dupes: {total_dupes} | Errors: {total_errors} | "
                      f"{wave_ms:.0f}ms | {rate:.1f} ex/s")

    elapsed = time.time() - START

    # Final report
    print(f"\n{'='*70}")
    print(f"RAPPORT FINAL — {TARGET_CYCLES} CYCLES")
    print(f"{'='*70}")
    print(f"  Cycles executes:  {cycle}")
    print(f"  Generes bruts:    {total_generated}")
    print(f"  Valides uniques:  {total_valid}")
    print(f"  Doublons filtres: {total_dupes}")
    print(f"  Erreurs:          {total_errors}")
    print(f"  Dataset total:    {len(existing)} exemples")
    print(f"  Temps total:      {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"  Debit:            {total_valid/elapsed:.1f} exemples/s")
    print()
    print(f"  Stats par noeud:")
    for n, s in sorted(node_stats.items()):
        total = s["ok"] + s["fail"]
        pct = s["ok"] / total * 100 if total > 0 else 0
        print(f"    {n:4s}: {s['ok']:3d} OK / {s['fail']:2d} FAIL ({pct:.0f}%) | {s['pairs']:4d} paires")
    print(f"  {'='*60}")


if __name__ == "__main__":
    main()
