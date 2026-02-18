#!/usr/bin/env python3
"""
Generateur de 100 exemples d'entrainement supplementaires pour JARVIS - Trading Crypto
Specialise MEXC Futures avec outils MCP reels
"""

import json
import random
from pathlib import Path
from datetime import datetime

SYSTEM_PROMPT = (
    "Tu es JARVIS, un assistant vocal intelligent en francais. "
    "Tu controles un systeme Windows avec des commandes vocales, "
    "tu geres un cluster de modeles d'IA locale (LM Studio, Ollama), "
    "tu analyses les marches de trading crypto sur MEXC Futures, "
    "et tu assistes l'utilisateur dans toutes ses taches quotidiennes. "
    "Tu es concis, precis et naturel. Tu reponds toujours en francais. "
    "Tu executes les commandes sans hesiter quand tu es sur de l'intention. "
    "Tu demandes confirmation uniquement pour les actions destructives ou ambigues."
)

PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "AVAXUSDT", "LINKUSDT", "ADAUSDT", "DOTUSDT", "MATICUSDT"
]

PAIRS_SLASH = {
    "BTCUSDT":  "BTC/USDT",
    "ETHUSDT":  "ETH/USDT",
    "SOLUSDT":  "SOL/USDT",
    "XRPUSDT":  "XRP/USDT",
    "DOGEUSDT": "DOGE/USDT",
    "AVAXUSDT": "AVAX/USDT",
    "LINKUSDT": "LINK/USDT",
    "ADAUSDT":  "ADA/USDT",
    "DOTUSDT":  "DOT/USDT",
    "MATICUSDT":"MATIC/USDT",
}

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
TIMEFRAMES_FULL = {
    "1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes",
    "1h": "1 heure", "4h": "4 heures", "1d": "journalier"
}

DIRECTIONS = ["LONG", "SHORT"]
CONFIANCES = list(range(72, 96))

# Scores et metriques realistes
def rand_price(pair):
    prices = {
        "BTCUSDT": (85000, 105000), "ETHUSDT": (2800, 4200), "SOLUSDT": (140, 280),
        "XRPUSDT": (0.45, 0.85), "DOGEUSDT": (0.08, 0.22), "AVAXUSDT": (18, 45),
        "LINKUSDT": (10, 22), "ADAUSDT": (0.35, 0.75), "DOTUSDT": (5, 12),
        "MATICUSDT": (0.45, 1.20),
    }
    lo, hi = prices.get(pair, (1, 100))
    return round(random.uniform(lo, hi), 4 if lo < 1 else 2)

def rand_change():
    return round(random.uniform(-8.5, 12.3), 2)

def rand_volume_m():
    return round(random.uniform(2.5, 850.0), 1)

def rand_rsi():
    return round(random.uniform(28, 78), 1)

def rand_score():
    return random.randint(70, 94)

def rand_tp_sl(price, direction):
    if direction == "LONG":
        tp = round(price * random.uniform(1.003, 0.005 + 1), 4 if price < 1 else 2)
        sl = round(price * random.uniform(0.997, 0.9975), 4 if price < 1 else 2)
    else:
        tp = round(price * random.uniform(0.994, 0.997), 4 if price < 1 else 2)
        sl = round(price * random.uniform(1.002, 1.0035), 4 if price < 1 else 2)
    return tp, sl


# ============================================================
# TEMPLATES DE CONVERSATIONS
# ============================================================

def gen_analyse_paire():
    """Demandes d'analyse technique d'une paire specifique"""
    pair = random.choice(PAIRS)
    tf = random.choice(TIMEFRAMES)
    tf_full = TIMEFRAMES_FULL[tf]
    price = rand_price(pair)
    change = rand_change()
    volume = rand_volume_m()
    rsi = rand_rsi()
    direction = random.choice(DIRECTIONS)
    confiance = random.choice(CONFIANCES)
    tp, sl = rand_tp_sl(price, direction)

    pair_short = pair.replace("USDT", "")
    pair_slash = PAIRS_SLASH[pair]

    user_variants = [
        f"analyse {pair_short} en {tf}",
        f"analyse moi {pair_short} sur le {tf}",
        f"que penses-tu de {pair_short} en {tf}",
        f"analyse technique {pair_short} {tf}",
        f"donne moi l'analyse de {pair_short} timeframe {tf}",
        f"analyse {pair_short} timeframe {tf}",
        f"comment tu vois {pair_short} sur le {tf} ?",
        f"check {pair_short} en {tf}",
    ]
    user = random.choice(user_variants)

    trend_desc = "haussiere" if change > 0 else "baissiere"
    rsi_desc = "survente" if rsi < 35 else ("surachat" if rsi > 70 else "neutre")

    assistant = (
        f"J'utilise deep_analyze_coin sur {pair_slash} ({tf}).\n\n"
        f"**{pair_short} — Analyse {tf_full}**\n"
        f"- Prix: {price} USDT | Variation 24h: {change:+.2f}%\n"
        f"- Volume: {volume}M USDT | RSI: {rsi} ({rsi_desc})\n"
        f"- Tendance: {trend_desc}\n"
        f"- **Signal: {direction}** — Confiance {confiance}%\n"
        f"- Entry: {price} | TP: {tp} | SL: {sl}\n"
        f"Score composite: {rand_score()}/100 — {'Opportunite valide.' if confiance >= 78 else 'Signal a surveiller.'}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_scan_marche():
    """Scans de marche generaux"""
    scan_types = [
        ("scan_mexc", "scan general", "scanne le marche", "scanne les opportunites du marche"),
        ("scan_all_pumps", "scan pumps", "scanne les pumps", "cherche les pumps du moment"),
        ("scan_best_opportunities", "meilleures opportunites", "meilleures opportunites du moment", "top opportunites maintenant"),
        ("scan_sniper", "scan sniper", "lance le scan sniper", "scan sniper maintenant"),
        ("turbo_scan", "turbo scan", "lance le turbo scan", "turbo scan"),
        ("scan_breakout_imminent", "breakout imminent", "cherche les breakouts imminents", "scan breakout"),
    ]
    tool_name, label, *user_variants = random.choice(scan_types)
    user = random.choice(user_variants)

    n_results = random.randint(3, 8)
    results = []
    pairs_sample = random.sample(PAIRS, min(n_results, len(PAIRS)))
    for p in pairs_sample:
        price = rand_price(p)
        change = rand_change()
        direction = random.choice(DIRECTIONS)
        score = rand_score()
        confiance = random.choice(CONFIANCES)
        tp, sl = rand_tp_sl(price, direction)
        results.append(
            f"  {p.replace('USDT','')}: {direction} | Score {score} | Conf {confiance}% | "
            f"Entry {price} TP {tp} SL {sl} | {change:+.2f}%"
        )

    assistant = (
        f"J'execute {tool_name} — scan en cours...\n\n"
        f"**Resultats {label.upper()}** ({len(results)} signaux):\n"
        + "\n".join(results) +
        f"\n\nMeilleure opportunite: {pairs_sample[0].replace('USDT','')}. "
        f"Veux-tu que j'envoie les signaux sur Telegram ?"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_positions():
    """Questions sur les positions ouvertes et marges"""
    user_variants = [
        "mes positions",
        "montre moi mes positions ouvertes",
        "check mes positions MEXC",
        "positions en cours",
        "quelles sont mes positions actives",
        "etat de mes positions",
        "positions ouvertes sur MEXC",
        "combien de positions j'ai",
    ]
    user = random.choice(user_variants)

    n_positions = random.randint(1, 5)
    pairs_sample = random.sample(PAIRS, n_positions)
    pos_lines = []
    total_pnl = 0
    for p in pairs_sample:
        price = rand_price(p)
        direction = random.choice(DIRECTIONS)
        entry = round(price * random.uniform(0.97, 1.03), 2 if price > 1 else 4)
        pnl = round((price - entry) * (1 if direction == "LONG" else -1) * random.uniform(0.5, 3) * 10, 2)
        total_pnl += pnl
        margin = round(random.uniform(6, 35), 1)
        margin_status = "CRITIQUE" if margin < 8 else ("DANGER" if margin < 12 else "OK")
        pos_lines.append(
            f"  {p.replace('USDT','')}: {direction} | Entry {entry} | Prix {price} | "
            f"PnL {pnl:+.2f}$ | Marge {margin}% [{margin_status}]"
        )
        total_pnl = round(total_pnl, 2)

    assistant = (
        f"J'interroge l'API MEXC pour tes positions...\n\n"
        f"**{n_positions} position(s) ouverte(s):**\n"
        + "\n".join(pos_lines) +
        f"\n\n**PnL total: {total_pnl:+.2f}$**\n"
        f"{'Attention, marges critiques detectees!' if any('CRITIQUE' in l for l in pos_lines) else 'Marges correctes.'}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_marges_critiques():
    """Alertes et check des marges critiques"""
    user_variants = [
        "marges critiques",
        "check les marges",
        "quelles positions sont en danger",
        "marges en danger",
        "alerte marge",
        "positions avec marge faible",
        "verifier les marges MEXC",
    ]
    user = random.choice(user_variants)

    n_critical = random.randint(1, 3)
    pairs_sample = random.sample(PAIRS, n_critical)
    critical_lines = []
    for p in pairs_sample:
        margin = round(random.uniform(3.5, 7.9), 1)
        price = rand_price(p)
        liq_price = round(price * random.uniform(0.92, 0.97), 2 if price > 1 else 4)
        critical_lines.append(
            f"  {p.replace('USDT','')}: Marge {margin}% | Liquidation a {liq_price} USDT — CRITIQUE"
        )

    assistant = (
        f"Je scanne les marges via l'API MEXC...\n\n"
        f"** {n_critical} position(s) en ZONE CRITIQUE:**\n"
        + "\n".join(critical_lines) +
        f"\n\nRecommandation: Ajouter des fonds ou reduire les positions. "
        f"Veux-tu que j'envoie une alerte Telegram ?"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_signal():
    """Demandes de signal pour une paire"""
    pair = random.choice(PAIRS)
    pair_short = pair.replace("USDT", "")
    pair_slash = PAIRS_SLASH[pair]
    tf = random.choice(TIMEFRAMES)
    price = rand_price(pair)
    direction = random.choice(DIRECTIONS)
    confiance = random.choice(CONFIANCES)
    tp, sl = rand_tp_sl(price, direction)
    score = rand_score()
    rsi = rand_rsi()

    user_variants = [
        f"signal pour {pair_short}",
        f"signal {pair_short}",
        f"donne moi un signal sur {pair_short}",
        f"signal de trading {pair_short}",
        f"trade signal {pair_short}",
        f"signal {pair_short} {tf}",
        f"recommandation pour {pair_short}",
    ]
    user = random.choice(user_variants)

    assistant = (
        f"Je genere le signal via turbo_consensus pour {pair_slash}...\n\n"
        f"**Signal {pair_short}**\n"
        f"- Direction: **{direction}**\n"
        f"- Confiance: {confiance}%\n"
        f"- Prix actuel: {price} USDT\n"
        f"- Entry: {price} | TP: {tp} (+0.4%) | SL: {sl} (-0.25%)\n"
        f"- RSI: {rsi} | Score: {score}/100\n"
        f"Signal {'valide, execution possible.' if confiance >= 78 else 'a surveiller, confiance insuffisante.'}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_consensus():
    """Demandes de consensus multi-modeles"""
    pair = random.choice(PAIRS)
    pair_short = pair.replace("USDT", "")
    price = rand_price(pair)
    change = rand_change()
    volume = rand_volume_m()
    range_pos = round(random.uniform(0.1, 0.9), 2)
    direction = random.choice(DIRECTIONS)

    model_votes = []
    models = ["qwen3-30b (M1)", "deepseek-coder (M2)", "kimi-k2.5 (OL1)", "minimax-m2.5 (OL1)"]
    for m in random.sample(models, random.randint(3, 4)):
        vote = direction if random.random() > 0.2 else ("SHORT" if direction == "LONG" else "LONG")
        conf = random.choice(CONFIANCES)
        model_votes.append(f"  {m}: {vote} ({conf}%)")

    user_variants = [
        f"consensus sur {pair_short}",
        f"que dit le cluster sur {pair_short}",
        f"consensus {pair_short}",
        f"avis du cluster pour {pair_short}",
        f"multi-IA consensus {pair_short}",
        f"consensus multi modeles {pair_short}",
    ]
    user = random.choice(user_variants)

    tp, sl = rand_tp_sl(price, direction)
    confiance = random.choice(CONFIANCES)

    assistant = (
        f"Je lance turbo_consensus sur {pair_short} avec 4 modeles paralleles...\n\n"
        f"**Consensus {pair_short}** — Prix: {price} | {change:+.2f}% | Vol: {volume}M\n"
        f"Votes:\n" + "\n".join(model_votes) +
        f"\n\n**Verdict: {direction}** — Confiance aggregee: {confiance}%\n"
        f"Entry: {price} | TP: {tp} | SL: {sl}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_open_tradingview():
    """Actions d'ouverture TradingView"""
    pair = random.choice(PAIRS)
    pair_short = pair.replace("USDT", "")

    user_variants = [
        f"ouvre TradingView {pair_short}",
        f"ouvre le graphe {pair_short}",
        f"TradingView {pair_short}",
        f"ouvre le chart {pair_short}",
        f"montre moi le graphe {pair_short}",
        f"graphique {pair_short} sur TradingView",
        f"ouvre TradingView sur {pair_short}",
    ]
    user = random.choice(user_variants)

    tv_urls = {
        "BTCUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3ABTCUSDT.P",
        "ETHUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3AETHUSDT.P",
        "SOLUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3ASOLUSDT.P",
        "XRPUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3AXRPUSDT.P",
        "DOGEUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3ADOGEUSDT.P",
        "AVAXUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3AAVAXUSDT.P",
        "LINKUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3ALINKUSDT.P",
        "ADAUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3AADAUSDT.P",
        "DOTUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3ADOTUSDT.P",
        "MATICUSDT": "https://www.tradingview.com/chart/?symbol=MEXC%3AMATICUSDT.P",
    }
    url = tv_urls.get(pair, f"https://www.tradingview.com/chart/?symbol=MEXC%3A{pair}.P")

    assistant = (
        f"J'utilise open_url pour ouvrir TradingView {pair_short}.\n"
        f"URL: {url}\n"
        f"Graphe {pair_short} MEXC Futures ouvert dans le navigateur."
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_envoyer_signal_telegram():
    """Actions d'envoi de signaux sur Telegram"""
    pair = random.choice(PAIRS)
    pair_short = pair.replace("USDT", "")
    price = rand_price(pair)
    direction = random.choice(DIRECTIONS)
    confiance = random.choice(CONFIANCES)
    tp, sl = rand_tp_sl(price, direction)

    user_variants = [
        f"envoie le signal {pair_short} sur Telegram",
        f"envoie sur Telegram le signal {pair_short}",
        f"partage le signal {pair_short} sur Telegram",
        f"send Telegram {pair_short}",
        f"alerte Telegram {pair_short}",
        f"envoie l'alerte {pair_short}",
        f"push le signal {pair_short} sur Telegram",
    ]
    user = random.choice(user_variants)

    assistant = (
        f"J'utilise send_telegram_alert pour envoyer le signal {pair_short}...\n\n"
        f"Signal envoye sur le canal Telegram:\n"
        f"**{direction} {pair_short}**\n"
        f"- Entry: {price} USDT\n"
        f"- TP: {tp} (+0.4%)\n"
        f"- SL: {sl} (-0.25%)\n"
        f"- Levier: 10x | Confiance: {confiance}%\n"
        f"Message Telegram delivre avec succes."
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_pnl_bilan():
    """Bilan PnL et performance"""
    user_variants = [
        "quel est mon PnL du jour",
        "bilan trading du jour",
        "mes profits aujourd'hui",
        "PnL journalier",
        "combien j'ai gagne aujourd'hui",
        "performance trading",
        "bilan de la journee trading",
        "resultats du jour",
    ]
    user = random.choice(user_variants)

    n_trades = random.randint(3, 12)
    wins = random.randint(1, n_trades)
    losses = n_trades - wins
    pnl_total = round(random.uniform(-150, 450), 2)
    win_rate = round((wins / n_trades) * 100, 1)
    best_trade = round(random.uniform(20, 120), 2)
    worst_trade = round(random.uniform(-80, -10), 2)

    assistant = (
        f"Je consulte la base SQLite trading pour le bilan du jour...\n\n"
        f"**Bilan Trading — {datetime.now().strftime('%d/%m/%Y')}**\n"
        f"- Trades: {n_trades} ({wins} wins / {losses} losses)\n"
        f"- Win rate: {win_rate}%\n"
        f"- PnL total: {pnl_total:+.2f} USDT\n"
        f"- Meilleur trade: +{best_trade} USDT\n"
        f"- Pire trade: {worst_trade} USDT\n"
        f"{'Performance positive, continue comme ca.' if pnl_total > 0 else 'Journee negative, revise ta strategie.'}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_status_pipeline():
    """Status du pipeline trading"""
    user_variants = [
        "status trading",
        "etat du pipeline",
        "trading actif ?",
        "le pipeline tourne ?",
        "status du bot trading",
        "check le pipeline",
        "trading status",
        "est-ce que le scanner tourne",
    ]
    user = random.choice(user_variants)

    statuses = ["ACTIF", "EN PAUSE", "ERREUR", "MAINTENANCE"]
    status = random.choice(statuses)
    last_scan = f"il y a {random.randint(1, 59)} minutes"
    signals_en_attente = random.randint(0, 8)
    cluster_ok = random.choice([True, True, True, False])

    assistant = (
        f"Je verifie l'etat du pipeline via run_script trading_status...\n\n"
        f"**Status Pipeline Trading**\n"
        f"- Bot: {status}\n"
        f"- Dernier scan: {last_scan}\n"
        f"- Signaux en attente: {signals_en_attente}\n"
        f"- Cluster M1/M2: {'OK' if cluster_ok else 'ALERTE'}\n"
        f"- MEXC API: connectee\n"
        f"{'Tout fonctionne normalement.' if status == 'ACTIF' and cluster_ok else 'Anomalie detectee, verification recommandee.'}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_mode_trading():
    """Activation du mode trading"""
    user_variants = [
        "lance le mode trading",
        "active le trading",
        "demarre la session trading",
        "ouvre le mode trading",
        "mode trading",
        "start trading",
        "passe en mode trading",
    ]
    user = random.choice(user_variants)

    assistant = (
        f"J'active le mode trading — execution du skill en cours...\n\n"
        f"1. open_url → TradingView MEXC ouvert\n"
        f"2. run_script → trading_status verifie — ACTIF\n"
        f"3. scan_mexc → scan initial lance\n"
        f"4. lm_cluster_status → M1 OK (qwen3-30b charge), M2 OK\n\n"
        f"Mode trading actif. Scanner demarre, graphes ouverts. "
        f"Je surveille le marche et t'alerte des qu'un signal se forme."
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_analyse_rapide():
    """Analyse rapide multi-paires"""
    pairs_sample = random.sample(PAIRS, random.randint(3, 5))
    pairs_shorts = [p.replace("USDT", "") for p in pairs_sample]

    user_variants = [
        f"analyse rapide du marche",
        f"vue d'ensemble du marche",
        f"quick scan marche crypto",
        f"tour du marche en rapide",
        f"resume du marche",
        f"que se passe-t-il sur le marche",
    ]
    user = random.choice(user_variants)

    lines = []
    for pair, short in zip(pairs_sample, pairs_shorts):
        price = rand_price(pair)
        change = rand_change()
        direction = random.choice(DIRECTIONS)
        icon = "+" if change > 0 else ""
        lines.append(f"  {short}: {price} ({icon}{change}%) → {direction}")

    assistant = (
        f"Je fais un scan rapide via scan_mexc et lm_query sur M1...\n\n"
        f"**Vue d'ensemble marche — {datetime.now().strftime('%H:%M')}**\n"
        + "\n".join(lines) +
        f"\n\nTendance generale: {'haussiere' if sum(1 for l in lines if '+' in l or '%' in l and random.random() > 0.5) > len(lines) // 2 else 'mixte'}. "
        f"Veux-tu un signal precis sur une paire ?"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_historique_signaux():
    """Historique et statistiques des signaux"""
    user_variants = [
        "historique des signaux",
        "signaux passes",
        "derniers signaux envoyes",
        "historique trades",
        "quels signaux ont ete envoyes",
        "signaux recents",
        "top signaux de la semaine",
    ]
    user = random.choice(user_variants)

    n = random.randint(4, 8)
    pairs_sample = random.sample(PAIRS, min(n, len(PAIRS)))
    sig_lines = []
    for p in pairs_sample:
        direction = random.choice(DIRECTIONS)
        price = rand_price(p)
        result = random.choice(["TP atteint", "SL touche", "En cours", "Expire"])
        pnl = round(random.uniform(-30, 60), 2)
        time_ago = f"il y a {random.randint(5, 240)} min"
        sig_lines.append(
            f"  {p.replace('USDT','')}: {direction} @ {price} | {result} | {pnl:+.2f}$ | {time_ago}"
        )

    wins = sum(1 for l in sig_lines if "TP atteint" in l)

    assistant = (
        f"Je consulte la base SQL via sql_get_signals...\n\n"
        f"**{len(sig_lines)} derniers signaux:**\n"
        + "\n".join(sig_lines) +
        f"\n\nTaux de reussite: {wins}/{len(sig_lines)} ({round(wins/len(sig_lines)*100)}%)"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_config_trading():
    """Questions sur la configuration trading"""
    user_variants = [
        "quelle est ma config trading",
        "parametres du bot",
        "voir la configuration MEXC",
        "config trading actuelle",
        "parametres de trading",
        "quel levier utilise le bot",
        "quels sont les TP et SL configures",
    ]
    user = random.choice(user_variants)

    assistant = (
        f"Je lis la configuration via read_text_file sur config.py...\n\n"
        f"**Configuration Trading MEXC Futures**\n"
        f"- Exchange: MEXC Futures\n"
        f"- Levier: 10x\n"
        f"- Paires: 10 (BTC, ETH, SOL, XRP, DOGE, AVAX, LINK, ADA, DOT, MATIC)\n"
        f"- TP: +0.4% | SL: -0.25%\n"
        f"- Score minimum signal: 70/100\n"
        f"- Age max signal: 60 minutes\n"
        f"- Cluster: M1 (qwen3-30b) + M2 (deepseek-coder) + OL1 (kimi/minimax)\n"
        f"Configuration chargee depuis config.py."
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_conversation_multi_tour():
    """Conversations multi-tours realistes"""
    pair = random.choice(PAIRS)
    pair_short = pair.replace("USDT", "")
    pair_slash = PAIRS_SLASH[pair]
    price = rand_price(pair)
    direction = random.choice(DIRECTIONS)
    confiance = random.choice(CONFIANCES)
    tp, sl = rand_tp_sl(price, direction)
    rsi = rand_rsi()

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"analyse {pair_short}"},
        {"role": "assistant", "content": (
            f"J'analyse {pair_slash} via deep_analyze_coin...\n\n"
            f"**{pair_short}** — Prix: {price} | RSI: {rsi}\n"
            f"Signal: **{direction}** | Confiance: {confiance}%\n"
            f"Entry: {price} | TP: {tp} | SL: {sl}"
        )},
        {"role": "user", "content": "envoie le signal sur Telegram"},
        {"role": "assistant", "content": (
            f"J'envoie via send_telegram_alert...\n\n"
            f"**{direction} {pair_short}** poste sur Telegram:\n"
            f"Entry {price} | TP {tp} | SL {sl} | 10x | Conf {confiance}%\n"
            f"Signal delivre avec succes."
        )},
    ]}


def gen_ollama_trading_analysis():
    """Utilisation de l'outil ollama_trading_analysis"""
    pair = random.choice(PAIRS)
    pair_short = pair.replace("USDT", "")
    pair_slash = PAIRS_SLASH[pair]
    tf = random.choice(TIMEFRAMES)
    price = rand_price(pair)
    direction = random.choice(DIRECTIONS)
    confiance = random.choice(CONFIANCES)
    tp, sl = rand_tp_sl(price, direction)

    user_variants = [
        f"analyse IA multi-agents {pair_short}",
        f"analyse cloud {pair_short}",
        f"3 agents sur {pair_short}",
        f"minimax kimi sur {pair_short}",
        f"analyse parallele {pair_short}",
    ]
    user = random.choice(user_variants)

    assistant = (
        f"Je lance ollama_trading_analysis sur {pair_slash} ({tf}) avec 3 agents cloud...\n\n"
        f"=== TRADING ANALYSIS {pair_short} ({tf}) - 3 AGENTS ===\n\n"
        f"SCANNER (minimax-m2.5): Tendance {'haussiere' if direction=='LONG' else 'baissiere'}, "
        f"volume {rand_volume_m()}M USDT, RSI {rand_rsi()}\n\n"
        f"ANALYSTE (kimi-k2.5): Setup {direction} confirme, price action propre, "
        f"support/resistance valide\n\n"
        f"STRATEGE (kimi-k2.5): {direction} {pair_short} — Entry {price} | TP {tp} | SL {sl} | "
        f"Confiance {confiance}% | Score {rand_score()}/100"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_gestion_risque():
    """Questions sur la gestion du risque"""
    user_variants = [
        "quel est mon risque actuel",
        "exposition totale au marche",
        "check le risque du portefeuille",
        "combien je risque en ce moment",
        "risque global",
        "exposure totale",
        "bilan risque",
    ]
    user = random.choice(user_variants)

    n_positions = random.randint(2, 6)
    total_exposure = round(random.uniform(500, 5000), 2)
    max_loss = round(total_exposure * 0.025, 2)
    margin_used = round(random.uniform(15, 65), 1)

    assistant = (
        f"Je calcule l'exposition via l'API MEXC...\n\n"
        f"**Bilan Risque Portefeuille**\n"
        f"- Positions ouvertes: {n_positions}\n"
        f"- Exposition totale: {total_exposure} USDT (10x levier)\n"
        f"- Perte max potentielle (SL -0.25%): -{max_loss} USDT\n"
        f"- Marge utilisee: {margin_used}%\n"
        f"- Risque global: {'ELEVE' if margin_used > 50 else ('MODERE' if margin_used > 30 else 'FAIBLE')}\n"
        f"{'Attention, exposition importante.' if margin_used > 50 else 'Gestion du risque correcte.'}"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def gen_rapport_matin():
    """Rapport du matin trading"""
    user_variants = [
        "rapport du matin",
        "briefing matin trading",
        "resume de la nuit",
        "qu'est-ce qui s'est passe cette nuit",
        "bilan nuit trading",
        "rapport matinal",
    ]
    user = random.choice(user_variants)

    btc_change = rand_change()
    eth_change = rand_change()
    sol_change = rand_change()
    market_mood = "bullish" if btc_change > 1 else ("bearish" if btc_change < -1 else "neutre")

    assistant = (
        f"Je compile le rapport via lm_cluster_status + scan_mexc + ollama_trading_analysis...\n\n"
        f"**Briefing Trading — {datetime.now().strftime('%d/%m/%Y %H:%M')}**\n\n"
        f"**Marche:**\n"
        f"- BTC: {rand_price('BTCUSDT')} ({btc_change:+.2f}%)\n"
        f"- ETH: {rand_price('ETHUSDT')} ({eth_change:+.2f}%)\n"
        f"- SOL: {rand_price('SOLUSDT')} ({sol_change:+.2f}%)\n"
        f"- Sentiment: {market_mood}\n\n"
        f"**Cluster:**\n"
        f"- M1 (qwen3-30b): OK — {random.randint(80, 150)} tok/s\n"
        f"- M2 (deepseek): OK\n"
        f"- OL1 (Ollama): OK\n\n"
        f"**Signaux nocturnes:** {random.randint(2, 8)} signaux generes\n"
        f"Pret pour la session. Veux-tu lancer le scan ?"
    )

    return {"messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


# ============================================================
# GENERATION DU DATASET
# ============================================================

GENERATORS = [
    (gen_analyse_paire, 18),
    (gen_scan_marche, 11),
    (gen_positions, 6),
    (gen_marges_critiques, 5),
    (gen_signal, 10),
    (gen_consensus, 7),
    (gen_open_tradingview, 5),
    (gen_envoyer_signal_telegram, 5),
    (gen_pnl_bilan, 4),
    (gen_status_pipeline, 4),
    (gen_mode_trading, 3),
    (gen_analyse_rapide, 4),
    (gen_historique_signaux, 3),
    (gen_config_trading, 2),
    (gen_conversation_multi_tour, 4),
    (gen_ollama_trading_analysis, 4),
    (gen_gestion_risque, 3),
    (gen_rapport_matin, 2),
]

# Verification: total = 100
total_expected = sum(n for _, n in GENERATORS)
assert total_expected == 100, f"Total attendu 100, got {total_expected}"


def generate_dataset():
    random.seed(42)
    examples = []
    for gen_func, count in GENERATORS:
        for _ in range(count):
            try:
                ex = gen_func()
                examples.append(ex)
            except Exception as e:
                print(f"Erreur dans {gen_func.__name__}: {e}")

    random.shuffle(examples)
    return examples


def main():
    output_dir = Path("F:/BUREAU/turbo/finetuning/dataset")
    output_dir.mkdir(parents=True, exist_ok=True)

    augmented_path = output_dir / "jarvis_trading_augmented.jsonl"
    train_path = output_dir / "jarvis_finetune_train.jsonl"

    print("=" * 60)
    print("JARVIS — Generateur d'exemples trading")
    print("=" * 60)

    # Generation
    examples = generate_dataset()
    print(f"[1/3] Generation: {len(examples)} exemples crees")

    # Sauvegarde fichier augmente
    with open(augmented_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"[2/3] Sauvegarde: {augmented_path}")

    # Fusion avec le dataset principal
    original_count = 0
    if train_path.exists():
        with open(train_path, "r", encoding="utf-8") as f:
            original_lines = f.readlines()
        original_count = len(original_lines)
        print(f"      Dataset principal: {original_count} exemples existants")

        # Ajout des nouveaux exemples a la fin
        with open(train_path, "a", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"[3/3] Fusion: {original_count} + {len(examples)} = {original_count + len(examples)} exemples")
    else:
        print(f"      Dataset principal introuvable: {train_path}")
        print(f"[3/3] Skipped (fichier principal absent)")

    print("=" * 60)
    print(f"OK — {len(examples)} exemples trading generes et ajoutes")
    print(f"Fichier augmente: {augmented_path}")
    if original_count > 0:
        print(f"Dataset total: {original_count + len(examples)} exemples")
    print("=" * 60)

    # Affichage d'un exemple aleatoire
    sample = random.choice(examples)
    print("\n--- Exemple aleatoire ---")
    user_msg = next((m["content"] for m in sample["messages"] if m["role"] == "user"), "")
    asst_msg = next((m["content"] for m in sample["messages"] if m["role"] == "assistant"), "")
    print(f"User: {user_msg}")
    print(f"Assistant: {asst_msg[:300]}...")


if __name__ == "__main__":
    main()
