"""Test pipeline Telegram JARVIS — 1000 cycles Q/R avec mesure vitesse + qualite."""
import json, time, urllib.request, sys, random, statistics

M1_URL = "http://127.0.0.1:1234/v1/chat/completions"
OL1_URL = "http://127.0.0.1:11434/api/chat"
TG_TOKEN = None
TG_CHAT = None

# Load .env
try:
    with open("F:/BUREAU/turbo/.env") as f:
        for line in f:
            if line.startswith("TELEGRAM_TOKEN="):
                TG_TOKEN = line.strip().split("=", 1)[1]
            elif line.startswith("TELEGRAM_CHAT="):
                TG_CHAT = line.strip().split("=", 1)[1]
except:
    pass

SYSTEM_PROMPT = """/nothink
Tu es JARVIS, assistant personnel de Turbo. Reponds en francais, concis et direct (2-5 phrases).

ENTREES VOCALES: Les messages viennent souvent de transcription vocale — fautes, pas de ponctuation, mots colles, abreviations. Comprends l'INTENTION, ignore les fautes, reponds a ce que l'utilisateur VEUT.
Exemples: "teste xca va koi de bo" = test + salutation | "lis me mail" = lire emails | "scan treding" = scanner marche crypto

REGLES:
- Francais uniquement
- Reponds a TOUT: questions generales, code, trading, systeme, conversation
- Max 400 mots, va droit au but"""

# Test prompts: (input, expected_intent, category)
TEST_PROMPTS = [
    # Voice-style messy inputs
    ("teste xca va koi de bo", "salutation/test", "voice_messy"),
    ("lis me mail", "lire emails", "voice_messy"),
    ("scan treding", "scanner marche", "voice_messy"),
    ("ouvre crome", "ouvrir navigateur", "voice_messy"),
    ("kel heur il e", "donner heure", "voice_messy"),
    ("fé un rezume de ma journer", "resume journee", "voice_messy"),
    ("comman va le cluster", "statut cluster", "voice_messy"),
    ("di moi le pri du bitcoin", "prix BTC", "voice_messy"),
    ("c koi un api rest", "expliquer API REST", "voice_messy"),
    ("envoi un msg a claire", "envoyer message", "voice_messy"),
    ("met une alarme dan 5 min", "alarme/timer", "voice_messy"),
    ("montre moi les log", "afficher logs", "voice_messy"),
    ("redemarr le serveur", "redemarrer service", "voice_messy"),
    ("ta vu le match ier soir", "conversation sport", "voice_messy"),
    ("je sui fatiger", "conversation perso", "voice_messy"),
    # Clean text inputs
    ("Bonjour JARVIS", "salutation", "clean"),
    ("Quelle est la meteo aujourd'hui ?", "meteo", "clean"),
    ("Explique-moi les decorateurs Python", "explication code", "clean"),
    ("Analyse le marche crypto", "analyse trading", "clean"),
    ("Combien font 15% de 3500", "calcul", "clean"),
    ("Quels sont les GPU du cluster ?", "info systeme", "clean"),
    ("Ecris un script Python qui tri une liste", "code", "clean"),
    ("Donne-moi un signal trading sur SOL", "trading", "clean"),
    ("Raconte-moi une blague", "divertissement", "clean"),
    ("Quelles sont les news tech du jour ?", "actualites", "clean"),
    # Edge cases
    ("", "vide", "edge"),
    ("?", "question vague", "edge"),
    ("ok", "confirmation", "edge"),
    ("oui", "confirmation", "edge"),
    ("merci", "remerciement", "edge"),
    ("lol", "reaction", "edge"),
    ("...", "silence", "edge"),
    ("a", "lettre seule", "edge"),
    ("test", "test simple", "edge"),
    ("yo", "salutation informelle", "edge"),
]

def query_m1(prompt, timeout=15):
    body = json.dumps({
        "model": "qwen3-8b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "/nothink\n" + prompt}
        ],
        "temperature": 0.2, "max_tokens": 256, "stream": False
    }).encode()
    req = urllib.request.Request(M1_URL, data=body, headers={"Content-Type": "application/json"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"].strip()
            # Clean thinking tokens
            import re
            text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
            text = re.sub(r'^/no_?think\s*', '', text).strip()
            latency = time.time() - start
            return text, latency, None
    except Exception as e:
        return None, time.time() - start, str(e)

def query_ol1(prompt, timeout=10):
    body = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False
    }).encode()
    req = urllib.request.Request(OL1_URL, data=body, headers={"Content-Type": "application/json"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            text = data.get("message", {}).get("content", "").strip()
            import re
            text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
            latency = time.time() - start
            return text, latency, None
    except Exception as e:
        return None, time.time() - start, str(e)

def send_telegram(text):
    if not TG_TOKEN or not TG_CHAT:
        return False
    body = json.dumps({"chat_id": int(TG_CHAT), "text": text[:4000]}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("ok", False)
    except:
        return False

def score_response(prompt, response, category):
    """Score response quality 0-100."""
    if not response:
        return 0
    score = 50  # base
    # Penalty for empty/too short
    if len(response) < 5:
        return 10
    # Bonus for French
    fr_markers = ["je", "tu", "le", "la", "les", "de", "du", "un", "une", "est", "et", "en", "pour", "que", "qui", "sur", "pas", "avec"]
    fr_count = sum(1 for w in fr_markers if f" {w} " in f" {response.lower()} ")
    score += min(fr_count * 3, 20)
    # Penalty for English-heavy response
    en_markers = ["the", "is", "are", "you", "this", "that", "with", "for", "and", "but", "not", "have"]
    en_count = sum(1 for w in en_markers if f" {w} " in f" {response.lower()} ")
    score -= min(en_count * 5, 30)
    # Penalty for thinking tokens leaked
    if "<think>" in response or "/nothink" in response:
        score -= 30
    # Bonus for appropriate length (25-300 chars)
    if 25 <= len(response) <= 300:
        score += 15
    elif len(response) > 1000:
        score -= 10
    # Bonus for not being an error
    if not response.startswith("[Erreur") and not response.startswith("Error"):
        score += 5
    # Penalty for refusal
    refusal = ["je ne peux pas", "je suis incapable", "i cannot", "i can't", "as an ai"]
    if any(r in response.lower() for r in refusal):
        score -= 20
    return max(0, min(100, score))

def run_tests(cycles=1000, send_tg_every=100):
    print(f"=== TEST PIPELINE TELEGRAM JARVIS — {cycles} cycles ===\n")

    m1_latencies = []
    m1_scores = []
    m1_errors = 0
    m1_empty = 0

    categories = {"voice_messy": [], "clean": [], "edge": []}

    total_start = time.time()

    for i in range(cycles):
        prompt_data = TEST_PROMPTS[i % len(TEST_PROMPTS)]
        prompt, expected, category = prompt_data

        if not prompt:  # skip empty edge case for M1
            if category == "edge":
                continue

        text, latency, error = query_m1(prompt)

        if error:
            m1_errors += 1
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{cycles}] ERROR: {error[:60]}")
            continue

        if not text or len(text) < 2:
            m1_empty += 1
            continue

        m1_latencies.append(latency)
        quality = score_response(prompt, text, category)
        m1_scores.append(quality)
        if category in categories:
            categories[category].append(quality)

        # Print sample every 50 cycles
        if (i + 1) % 50 == 0:
            elapsed = time.time() - total_start
            avg_lat = statistics.mean(m1_latencies[-50:]) if m1_latencies else 0
            avg_q = statistics.mean(m1_scores[-50:]) if m1_scores else 0
            print(f"  [{i+1}/{cycles}] avg_lat={avg_lat:.2f}s avg_q={avg_q:.0f}/100 errors={m1_errors} elapsed={elapsed:.0f}s")
            print(f"    Q: {prompt[:50]}")
            print(f"    A: {text[:80]}")

        # Send sample to Telegram periodically
        if send_tg_every and (i + 1) % send_tg_every == 0:
            report = f"Test {i+1}/{cycles}\nLatence moy: {statistics.mean(m1_latencies):.2f}s\nQualite moy: {statistics.mean(m1_scores):.0f}/100\nErreurs: {m1_errors}"
            send_telegram(report)

    total_time = time.time() - total_start

    # Final report
    print(f"\n{'='*60}")
    print(f"RESULTATS — {cycles} cycles en {total_time:.1f}s")
    print(f"{'='*60}")

    if m1_latencies:
        print(f"\nLATENCE M1:")
        print(f"  Moyenne:  {statistics.mean(m1_latencies):.2f}s")
        print(f"  Mediane:  {statistics.median(m1_latencies):.2f}s")
        print(f"  Min:      {min(m1_latencies):.2f}s")
        print(f"  Max:      {max(m1_latencies):.2f}s")
        print(f"  P95:      {sorted(m1_latencies)[int(len(m1_latencies)*0.95)]:.2f}s")
        if len(m1_latencies) > 1:
            print(f"  Ecart-type: {statistics.stdev(m1_latencies):.2f}s")

    if m1_scores:
        print(f"\nQUALITE REPONSES:")
        print(f"  Moyenne:  {statistics.mean(m1_scores):.0f}/100")
        print(f"  Mediane:  {statistics.median(m1_scores):.0f}/100")
        print(f"  Min:      {min(m1_scores)}/100")
        print(f"  Max:      {max(m1_scores)}/100")

    print(f"\nPAR CATEGORIE:")
    for cat, scores in categories.items():
        if scores:
            print(f"  {cat}: {statistics.mean(scores):.0f}/100 ({len(scores)} tests)")

    print(f"\nERREURS: {m1_errors} | VIDES: {m1_empty} | SUCCES: {len(m1_latencies)}")
    print(f"DEBIT: {len(m1_latencies)/total_time:.1f} req/s")

    # Send final report to Telegram
    final_msg = (
        f"TEST PIPELINE COMPLET\n"
        f"{cycles} cycles en {total_time:.0f}s\n"
        f"Latence: {statistics.mean(m1_latencies):.2f}s moy / {statistics.median(m1_latencies):.2f}s med\n"
        f"Qualite: {statistics.mean(m1_scores):.0f}/100\n"
        f"Erreurs: {m1_errors} | Vides: {m1_empty}\n"
        f"Debit: {len(m1_latencies)/total_time:.1f} req/s"
    ) if m1_latencies and m1_scores else "TEST ECHOUE - aucune reponse"
    send_telegram(final_msg)
    print(f"\nRapport envoye sur Telegram.")

    return m1_latencies, m1_scores

if __name__ == "__main__":
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    run_tests(cycles=cycles)
