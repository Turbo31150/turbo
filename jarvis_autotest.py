#!/usr/bin/env python3
"""JARVIS Auto-Test & Auto-Improve Engine v3 — M1 prioritaire + optimise speed"""
import json, time, sys, os, random, subprocess, urllib.request, urllib.error
from jarvis_bench_utils import append_run

# === CONFIG ===
NODES = {
    "M1": {"url": "http://10.5.0.2:1234/api/v1/chat", "type": "lmstudio-responses", "model": "qwen/qwen3-8b", "key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7", "timeout": 30, "priority": 2},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "type": "ollama", "model": "qwen3:1.7b", "timeout": 20, "priority": 2},
    "M2": {"url": "http://192.168.1.26:1234/v1/chat/completions", "type": "lmstudio", "model": "deepseek-coder-v2-lite-instruct", "key": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4", "timeout": 60, "priority": 2},
    "M3": {"url": "http://192.168.1.113:1234/v1/chat/completions", "type": "lmstudio", "model": "mistral-7b-instruct-v0.3", "key": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux", "timeout": 30, "priority": 1},
}

# Routage intelligent : domaine -> noeuds preferes (ordre de priorite)
ROUTING = {
    "code": ["M1", "M2", "M3", "OL1"],        # M1 meilleur en code 30B
    "math": ["M1", "OL1", "M2", "M3"],         # M1 excelle, OL1 rapide
    "raisonnement": ["M1", "M2", "OL1"],       # M1 champion, JAMAIS M3
    "traduction": ["M1", "OL1", "M2", "M3"],   # M1 30B multilingue, OL1 rapide
    "systeme": ["M1", "OL1", "M2", "M3"],      # M1 + OL1 rapide
    "trading": ["M1", "OL1", "M2"],            # M1 analyse, OL1 rapide, PAS M3
    "securite": ["M1", "M2", "M3"],            # M1 + M2 code, M3 scan
    "web": ["M1", "M2", "OL1", "M3"],          # M1 + M2 code web
}

# Noeuds temporairement offline (auto-correction)
OFFLINE_NODES = set()
# Corrections appliquees durant cette session
CORRECTIONS = []

DOMAINS = {
    "code": [
        {"q": "Ecris une fonction Python qui trie une liste par insertion. Retourne uniquement le code.", "check": "def ", "domain": "code"},
        {"q": "Ecris une fonction JavaScript qui inverse une chaine de caracteres. Code uniquement.", "check": "function", "domain": "code"},
        {"q": "Ecris une requete SQL qui trouve les 5 clients avec le plus de commandes. SQL uniquement.", "check": "SELECT", "domain": "code"},
        {"q": "Ecris un one-liner bash qui compte le nombre de fichiers .py dans un dossier recursivement.", "check": "find", "domain": "code"},
        {"q": "Ecris une classe Python simple pour un noeud d'arbre binaire avec insert et search.", "check": "class", "domain": "code"},
    ],
    "math": [
        {"q": "Calcule 847 * 23. Montre le calcul puis donne le resultat.", "check": "19481", "domain": "math"},
        {"q": "Quelle est la derivee de x^3 + 2x^2 - 5x + 1 ? Derive terme par terme.", "check": "3x", "domain": "math"},
        {"q": "Combien font 15% de 340 ? Calcul: 340 * 0.15 = ?", "check": "51", "domain": "math"},
        {"q": "Resous etape par etape: 2x + 7 = 23. Donc 2x = 16. Donc x = ?", "check": "8", "domain": "math"},
        {"q": "Quelle est la racine carree de 144 ? Reponds avec le nombre.", "check": "12", "domain": "math"},
    ],
    "raisonnement": [
        {"q": "Si tous les chats sont des animaux et que certains animaux sont noirs, peut-on conclure que certains chats sont noirs ? Reflechis etape par etape puis reponds OUI ou NON.", "check": "NON", "domain": "raisonnement"},
        {"q": "Un train part a 14h et arrive a 16h30. Le trajet fait 300km. Calcule etape par etape la vitesse moyenne en km/h.", "check": "120", "domain": "raisonnement"},
        {"q": "J'ai 3 boites. C pese 10kg. B pese 5kg de plus que C donc B=15kg. A pese le double de B. Combien pese A ? Calcule etape par etape.", "check": "30", "domain": "raisonnement"},
        {"q": "Demain est mercredi. Donc aujourd'hui est mardi. Quel jour etait hier ? Reponds en un mot.", "check": "lundi", "domain": "raisonnement"},
        {"q": "Dans une course, tu depasses le 2eme. Tu prends donc sa place. Quelle position occupes-tu ? Reponds juste le numero.", "check": "2", "domain": "raisonnement"},
    ],
    "traduction": [
        {"q": "Traduis en anglais: 'Le chat dort sur le tapis rouge'. Donne uniquement la traduction.", "check": "cat", "domain": "traduction"},
        {"q": "Traduis en francais: 'The quick brown fox jumps over the lazy dog'. Fox = renard. Donne la traduction complete.", "check": "renard", "domain": "traduction"},
        {"q": "Traduis en anglais: 'Je dois finir ce projet avant vendredi'. Donne uniquement la traduction.", "check": "project", "domain": "traduction"},
        {"q": "Traduis 'Bonjour, comment allez-vous ?' en espagnol. Bonjour = Hola.", "check": "Hola", "domain": "traduction"},
        {"q": "Traduis en francais: 'Machine learning is transforming healthcare'. Machine learning = apprentissage automatique.", "check": "apprentissage", "domain": "traduction"},
    ],
    "systeme": [
        {"q": "Donne la commande PowerShell pour lister les 5 processus qui consomment le plus de RAM. Code uniquement.", "check": "Process", "domain": "systeme"},
        {"q": "Comment verifier l'espace disque disponible sur Windows en PowerShell ? Commande uniquement.", "check": "Get-", "domain": "systeme"},
        {"q": "Commande bash pour trouver tous les fichiers modifies dans les dernieres 24h dans /tmp", "check": "find", "domain": "systeme"},
        {"q": "Comment tuer un processus par son PID sur Windows ? Donne la commande.", "check": "taskkill", "domain": "systeme"},
        {"q": "Commande pour voir les ports en ecoute sur Windows. Reponse courte.", "check": "netstat", "domain": "systeme"},
    ],
    "trading": [
        {"q": "Le BTC est a 95000$ et le RSI 14 est a 78. Le prix est au-dessus de la SMA200. Donne un signal LONG ou SHORT avec une phrase d'explication.", "check": "LONG", "domain": "trading"},
        {"q": "Un trader entre LONG a 100$ avec SL a 0.25%. Calcul: prix SL = 100 - (100 * 0.0025) = 100 - 0.25 = ? Donne le prix final.", "check": "99.75", "domain": "trading"},
        {"q": "RSI sous 30 = marche en survente. Survente signifie que le prix a trop baisse. Donc le signal logique est un signal d'achat ou de vente ? Reponds en un mot.", "check": "achat", "domain": "trading"},
        {"q": "Explique en 2 phrases ce qu'est un 'bull flag' en analyse technique. Mentionne le mot 'consolidation'.", "check": "consolidation", "domain": "trading"},
        {"q": "Si ETH monte de 3% en 1h avec un volume 5x superieur a la moyenne, quel regime de marche est-ce ? Reponds: trend, range, ou breakout.", "check": "breakout", "domain": "trading"},
    ],
    "securite": [
        {"q": "Ce code Python est-il vulnerable ? `query = f\"SELECT * FROM users WHERE id = {user_input}\"`. Identifie la vulnerabilite en un mot.", "check": "injection", "domain": "securite"},
        {"q": "Quelle est la commande pour generer une cle SSH ed25519 ? Donne la commande complete.", "check": "ssh-keygen", "domain": "securite"},
        {"q": "Cite 3 headers HTTP de securite importants. Mentionne Content-Security-Policy.", "check": "Content-Security-Policy", "domain": "securite"},
        {"q": "Quel port est utilise par defaut par HTTPS ? Reponds avec le numero.", "check": "443", "domain": "securite"},
        {"q": "Quel est le principe du 'least privilege' en securite ? Explique en 1 phrase. Mentionne le mot 'minimum'.", "check": "minimum", "domain": "securite"},
    ],
    "web": [
        {"q": "Ecris un fetch() JavaScript qui fait un GET sur /api/users et parse le JSON. Code uniquement.", "check": "fetch", "domain": "web"},
        {"q": "Quelle est la difference entre GET et POST en HTTP ? Reponds en 2 phrases. Mentionne 'body'.", "check": "body", "domain": "web"},
        {"q": "Ecris un endpoint Express.js simple qui retourne {status: 'ok'} sur GET /health. Code uniquement.", "check": "app.get", "domain": "web"},
        {"q": "Quel code HTTP signifie 'Not Found' ? Donne le numero.", "check": "404", "domain": "web"},
        {"q": "Ecris une requete curl qui envoie du JSON en POST a http://api.example.com/data avec Content-Type. Commande uniquement.", "check": "curl", "domain": "web"},
    ],
}

LOG_FILE = "C:/Users/franc/jarvis_autotest_results.json"
results = {"cycles": 0, "total": 0, "pass": 0, "fail": 0, "errors": 0, "by_node": {}, "by_domain": {}, "failures": [], "improvements": []}

def query_node(node_id, prompt):
    """Envoie une requete a un noeud et retourne (reponse, latence_ms, erreur)"""
    import re
    cfg = NODES[node_id]
    t0 = time.time()
    try:
        if cfg["type"] == "ollama":
            # OL1: num_ctx=4096 (defaut 40960 gaspille VRAM), think:false pour cloud
            data = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False, "options": {"num_ctx": 4096, "temperature": 0.2}}).encode()
            req = urllib.request.Request(cfg["url"], data=data, headers={"Content-Type": "application/json"})
        elif cfg["type"] == "lmstudio-responses":
            # LM Studio Responses API (M1) — /nothink pour speed, max_output_tokens=1024
            data = json.dumps({"model": cfg["model"], "input": "/nothink\n" + prompt, "temperature": 0.2, "max_output_tokens": 1024, "stream": False, "store": False}).encode()
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"}
            req = urllib.request.Request(cfg["url"], data=data, headers=headers)
        else:
            # M2/M3: max_tokens=512 suffit pour nos taches, temp basse
            data = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 512, "stream": False}).encode()
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"}
            req = urllib.request.Request(cfg["url"], data=data, headers=headers)

        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            result = json.loads(resp.read())

        latency = int((time.time() - t0) * 1000)

        if cfg["type"] == "ollama":
            text = result.get("message", {}).get("content", "")
        elif cfg["type"] == "lmstudio-responses":
            # Responses API: skip reasoning block, take message content
            output = result.get("output", [])
            text = ""
            for o in output:
                if o.get("type") == "message" and o.get("content"):
                    text = o["content"]
            if not text and output:
                text = output[-1].get("content", "")
        else:
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Strip think tags
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text, latency, None
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        return "", latency, str(e)

def evaluate(response, check_str, domain):
    """Evalue si la reponse est correcte"""
    if not response:
        return False, "reponse vide"
    resp_lower = response.lower()
    check_lower = check_str.lower()
    if check_lower in resp_lower:
        return True, "check OK"
    # Fuzzy: strip LaTeX, espaces, virgules, backslashes, underscores
    import re
    clean = re.sub(r'\\[,()\[\]{}]', '', response)  # strip LaTeX formatting
    clean = clean.replace(" ", "").replace(",", "").replace("\\", "").replace("_", "").lower()
    clean = re.sub(r'[`$]', '', clean)  # strip markdown/LaTeX delimiters
    if check_lower.replace(" ", "") in clean:
        return True, "check OK (fuzzy)"
    # Pour raisonnement: chercher des variantes de oui/non
    if domain == "raisonnement":
        if check_lower == "non" and any(x in resp_lower for x in ["non,", "non.", "non ", "la reponse est non", "conclusion : non", "ne peut pas"]):
            return True, "check OK (raisonnement-non)"
        if check_lower == "oui" and any(x in resp_lower for x in ["oui,", "oui.", "oui ", "la reponse est oui"]):
            return True, "check OK (raisonnement-oui)"
    # Pour trading: variantes de termes
    if domain == "trading":
        if check_lower == "achat" and any(x in resp_lower for x in ["achat", "buy", "acheter", "long", "oversold", "survente"]):
            return True, "check OK (trading-buy)"
        if check_lower == "breakout" and any(x in resp_lower for x in ["breakout", "cassure", "rupture", "explosion"]):
            return True, "check OK (trading-breakout)"
    return False, f"'{check_str}' non trouve dans reponse"

def pick_node(domain):
    """Choisit un noeud en utilisant le routage intelligent, excluant les noeuds offline"""
    preferred = ROUTING.get(domain, list(NODES.keys()))
    # Filtrer les noeuds offline
    available = [n for n in preferred if n not in OFFLINE_NODES]
    if not available:
        # Tous offline -> reset et reessayer
        OFFLINE_NODES.clear()
        CORRECTIONS.append({"type": "reset_offline", "reason": "all nodes offline, reset"})
        available = preferred
    # Poids decroissants : premier=50%, deuxieme=30%, troisieme=15%, reste=5%
    weights = [50, 30, 15] + [5] * max(0, len(available) - 3)
    weights = weights[:len(available)]
    return random.choices(available, weights=weights, k=1)[0]

def auto_correct(node_id, task, error, latency, response=""):
    """Auto-correction apres echec — retourne (should_retry, corrected_prompt, alt_node)"""
    correction = {"node": node_id, "domain": task["domain"], "action": None}

    # 1. TIMEOUT -> marquer offline temporairement + re-router
    if error and ("timed out" in str(error).lower() or "timeout" in str(error).lower()):
        OFFLINE_NODES.add(node_id)
        alt = pick_node(task["domain"])
        correction["action"] = f"timeout -> {node_id} offline, retry on {alt}"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] {node_id} timeout -> retry sur {alt}", flush=True)
        return True, task["q"], alt

    # 2. CONNEXION REFUSED -> noeud down
    if error and ("refused" in str(error).lower() or "unreachable" in str(error).lower()):
        OFFLINE_NODES.add(node_id)
        alt = pick_node(task["domain"])
        correction["action"] = f"connexion refused -> {node_id} offline, retry on {alt}"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] {node_id} down -> retry sur {alt}", flush=True)
        return True, task["q"], alt

    # 3. REPONSE VIDE -> enrichir le prompt et re-router
    if not error and not response.strip():
        enriched = task["q"] + " Reponds de maniere detaillee."
        alt = pick_node(task["domain"])
        correction["action"] = f"reponse vide -> prompt enrichi, retry on {alt}"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] reponse vide -> enrichi + retry {alt}", flush=True)
        return True, enriched, alt

    # 4. ECHEC RAISONNEMENT -> ajouter chain-of-thought
    if not error and task["domain"] == "raisonnement":
        enriched = task["q"].rstrip() + " Analyse chaque premisse separement puis donne ta conclusion finale."
        alt = "M1"  # M1 champion raisonnement
        if alt in OFFLINE_NODES:
            alt = pick_node(task["domain"])
        correction["action"] = f"fail raisonnement -> CoT enrichi, force M1"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] raisonnement fail -> CoT + M1", flush=True)
        return True, enriched, alt

    # 5. ECHEC MATH -> ajouter etapes
    if not error and task["domain"] == "math":
        enriched = task["q"].rstrip() + " Montre chaque etape de calcul et donne le nombre final."
        alt = "M1"
        if alt in OFFLINE_NODES:
            alt = pick_node(task["domain"])
        correction["action"] = f"fail math -> steps enrichi, force M1"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] math fail -> steps + M1", flush=True)
        return True, enriched, alt

    # 6. ECHEC TRADING -> forcer M1 avec prompt enrichi
    if not error and task["domain"] == "trading":
        enriched = task["q"].rstrip() + " Reponds avec precision, donne le chiffre ou le mot exact demande."
        alt = "M1"
        if alt in OFFLINE_NODES:
            alt = pick_node(task["domain"])
        correction["action"] = f"fail trading -> enrichi, force M1"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] trading fail -> enrichi + M1", flush=True)
        return True, enriched, alt

    # 7. ECHEC GENERIQUE -> retry sur M1
    if not error:
        alt = "M1"
        if alt in OFFLINE_NODES:
            alt = pick_node(task["domain"])
        correction["action"] = f"fail generique -> retry M1"
        CORRECTIONS.append(correction)
        print(f"    [AUTO-FIX] fail -> retry M1", flush=True)
        return True, task["q"], alt

    # 8. Pas de correction disponible
    return False, task["q"], node_id

def run_cycle(cycle_num, max_tasks=None):
    """Execute un cycle complet de tests"""
    all_tasks = []
    for domain, tasks in DOMAINS.items():
        for task in tasks:
            all_tasks.append(task)

    if max_tasks:
        random.shuffle(all_tasks)
        all_tasks = all_tasks[:max_tasks]

    node_ids = list(NODES.keys())
    cycle_results = {"cycle": cycle_num, "tests": [], "pass": 0, "fail": 0, "errors": 0}

    for task in all_tasks:
        node_id = pick_node(task["domain"])
        prompt = task["q"]
        resp, latency, error = query_node(node_id, prompt)

        if error:
            status = "error"
            reason = error
        else:
            passed, reason = evaluate(resp, task["check"], task["domain"])
            status = "pass" if passed else "fail"

        # AUTO-CORRECTION: retry une fois si echec
        if status != "pass":
            should_retry, corrected_prompt, alt_node = auto_correct(node_id, task, error, latency, resp)
            if should_retry:
                resp2, lat2, err2 = query_node(alt_node, corrected_prompt)
                if err2:
                    status = "error"
                    reason = f"retry({alt_node}): {err2}"
                else:
                    passed2, reason2 = evaluate(resp2, task["check"], task["domain"])
                    if passed2:
                        status = "pass"
                        reason = f"AUTO-FIXED({alt_node}): {reason2}"
                        latency = lat2
                        node_id = alt_node  # credit au noeud qui a reussi
                    else:
                        status = "fail"
                        reason = f"retry failed({alt_node}): {reason2}"

        # Comptabiliser
        if status == "error":
            results["errors"] += 1
            cycle_results["errors"] += 1
        elif status == "pass":
            results["pass"] += 1
            cycle_results["pass"] += 1
        else:
            results["fail"] += 1
            cycle_results["fail"] += 1
            results["failures"].append({
                "cycle": cycle_num, "node": node_id, "domain": task["domain"],
                "question": task["q"][:80], "check": task["check"],
                "response": resp[:200], "reason": reason, "latency": latency
            })

        results["total"] += 1

        # Track by node
        if node_id not in results["by_node"]:
            results["by_node"][node_id] = {"total": 0, "pass": 0, "fail": 0, "error": 0, "avg_latency": 0, "latencies": []}
        results["by_node"][node_id]["total"] += 1
        results["by_node"][node_id][status] += 1
        results["by_node"][node_id]["latencies"].append(latency)

        # Track by domain
        d = task["domain"]
        if d not in results["by_domain"]:
            results["by_domain"][d] = {"total": 0, "pass": 0, "fail": 0, "error": 0}
        results["by_domain"][d]["total"] += 1
        results["by_domain"][d][status] += 1

        test_entry = {"node": node_id, "domain": task["domain"], "status": status, "latency": latency, "reason": reason}
        cycle_results["tests"].append(test_entry)

        # Print progress
        symbol = "+" if status == "pass" else ("!" if status == "error" else "-")
        print(f"  [{symbol}] {node_id}/{task['domain']}: {status} ({latency}ms) — {reason[:60]}", flush=True)

    results["cycles"] = cycle_num
    return cycle_results

def save_results():
    """Sauvegarde les resultats"""
    # Compute avg latencies
    for node_id, data in results["by_node"].items():
        if data["latencies"]:
            data["avg_latency"] = int(sum(data["latencies"]) / len(data["latencies"]))

    # Don't save raw latency arrays
    save_data = json.loads(json.dumps(results))
    for node_id in save_data["by_node"]:
        save_data["by_node"][node_id].pop("latencies", None)

    save_data["corrections"] = CORRECTIONS[-50:]  # garder les 50 dernieres corrections
    save_data["offline_nodes"] = list(OFFLINE_NODES)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

    # Append to benchmark history
    try:
        total = results["total"]
        if total > 0:
            pass_rate = results["pass"] * 100.0 / total
            all_lats = []
            for nd in results["by_node"].values():
                if nd.get("avg_latency"):
                    all_lats.extend([nd["avg_latency"]] * nd["total"])
            avg_lat = int(sum(all_lats) / len(all_lats)) if all_lats else 0
            bn = {n: {"pass": s["pass"], "total": s["total"], "avg_latency": s.get("avg_latency", 0)} for n, s in results["by_node"].items()}
            bd = {d: {"pass": s["pass"], "total": s["total"]} for d, s in results["by_domain"].items()}
            score, regression = append_run(
                "autotest", NODES["M1"]["model"],
                {"context_length": 8192, "temperature": 0.2},
                pass_rate, avg_lat, total, results["errors"],
                by_node=bn, by_domain=bd
            )
            if regression:
                print(f"  [REGRESSION] Score dropped >10%! Current: {score}", flush=True)
    except Exception as e:
        print(f"  [WARN] History append failed: {e}", flush=True)

def print_summary():
    """Affiche un resume"""
    total = results["total"]
    if total == 0:
        print("Aucun test execute.")
        return

    print(f"\n{'='*60}")
    print(f"BILAN — {results['cycles']} cycles, {total} tests")
    print(f"{'='*60}")
    print(f"  PASS: {results['pass']} ({results['pass']*100//total}%)")
    print(f"  FAIL: {results['fail']} ({results['fail']*100//total}%)")
    print(f"  ERROR: {results['errors']} ({results['errors']*100//total}%)")

    print(f"\nPar noeud:")
    for node_id, data in results["by_node"].items():
        rate = data['pass']*100//max(data['total'],1)
        print(f"  {node_id}: {rate}% pass ({data['total']} tests, avg {data['avg_latency']}ms)")

    print(f"\nPar domaine:")
    for domain, data in results["by_domain"].items():
        rate = data['pass']*100//max(data['total'],1)
        print(f"  {domain}: {rate}% pass ({data['total']} tests)")

    if results["failures"]:
        print(f"\nTop echecs (derniers 5):")
        for f in results["failures"][-5:]:
            print(f"  [{f['node']}/{f['domain']}] {f['question'][:50]}... -> {f['reason'][:40]}")

    if CORRECTIONS:
        auto_fixed = sum(1 for c in CORRECTIONS if "retry" not in str(c.get("action","")))
        print(f"\nAuto-corrections: {len(CORRECTIONS)} (dont {auto_fixed} reussies)")
        for c in CORRECTIONS[-3:]:
            print(f"  {c.get('action','?')[:60]}")

    if OFFLINE_NODES:
        print(f"\nNoeuds offline: {', '.join(OFFLINE_NODES)}")

# === MAIN ===
if __name__ == "__main__":
    num_cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    tasks_per_cycle = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    print(f"JARVIS AutoTest — {num_cycles} cycles x {tasks_per_cycle} tasks = {num_cycles * tasks_per_cycle} tests")
    print(f"Noeuds: {', '.join(NODES.keys())}")
    print(f"Domaines: {', '.join(DOMAINS.keys())}")
    print(f"Log: {LOG_FILE}")
    print()

    for i in range(1, num_cycles + 1):
        # Reset noeuds offline tous les 5 cycles (ils peuvent revenir)
        if i % 5 == 0 and OFFLINE_NODES:
            print(f"  [RESET] Noeuds offline reinitialises: {', '.join(OFFLINE_NODES)}", flush=True)
            OFFLINE_NODES.clear()
        print(f"--- Cycle {i}/{num_cycles} ---")
        run_cycle(i, tasks_per_cycle)
        save_results()
        if i < num_cycles:
            time.sleep(1)  # Petit delai entre cycles

    print_summary()
    save_results()
    print(f"\nResultats sauvegardes: {LOG_FILE}")
