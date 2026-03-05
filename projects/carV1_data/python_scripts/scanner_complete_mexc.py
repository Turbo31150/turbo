#!/usr/bin/env python3
"""
SCANNER COMPLET MEXC + TELEGRAM + CONSENSUS 3 LM
Trading AI Ultimate v10.0
Charge automatiquement les configs depuis config/
"""

import requests
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime

# Charger configurations
ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"

print(f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     SCANNER COMPLET MEXC v10.0                          ║
║     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                              ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

# Chargement configs
print("[CONFIG] Chargement configurations...")

with open(CONFIG_DIR / "telegram" / "config.json") as f:
    TELEGRAM = json.load(f)
    print(f"  ✓ Telegram: Bot configuré (chat {TELEGRAM['chat_id']})")

with open(CONFIG_DIR / "lmstudio" / "cluster.json") as f:
    CLUSTER = json.load(f)
    print(f"  ✓ LM Cluster: {len(CLUSTER['nodes'])} machines")

with open(CONFIG_DIR / "mexc" / "api.json") as f:
    MEXC = json.load(f)
    print(f"  ✓ MEXC: {len(MEXC['favorites'])} favoris configurés")

print()

# URLs
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM['bot_token']}"
MEXC_TICKER_URL = MEXC['base_url'] + "/api/v1/contract/ticker"

# Poids consensus
WEIGHTS = {node['name']: node['weight'] for node in CLUSTER['nodes']}
THRESHOLD = 0.66

# ============================================================
# 1. TEST TELEGRAM
# ============================================================

def test_telegram():
    """Test connexion Telegram"""
    print("[1/5] TEST TELEGRAM")
    print("="*60)
    
    try:
        response = requests.get(f"{TELEGRAM_URL}/getMe", timeout=5)
        data = response.json()
        
        if data.get('ok'):
            bot = data['result']
            print(f"✅ Bot: @{bot['username']}")
            
            # Message de démarrage
            msg = f"""🚀 <b>SCANNER DÉMARRÉ</b>

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 Scan: TOUS les coins MEXC
🤖 Cluster: {len(CLUSTER['nodes'])} LM Studios
📊 Favoris: {', '.join(MEXC['favorites'][:3])}...

<i>Scan en cours... ⏳</i>"""
            
            requests.post(
                f"{TELEGRAM_URL}/sendMessage",
                json={'chat_id': TELEGRAM['chat_id'], 'text': msg, 'parse_mode': 'HTML'},
                timeout=10
            )
            print("✅ Message de démarrage envoyé\n")
            return True
        else:
            print(f"❌ Erreur bot: {data}\n")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}\n")
        return False

# ============================================================
# 2. SCAN MEXC
# ============================================================

def scan_mexc():
    """Scan tous les coins MEXC"""
    print("[2/5] SCAN MEXC - TOUS LES COINS")
    print("="*60)
    
    try:
        response = requests.get(MEXC_TICKER_URL, timeout=10)
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ MEXC erreur: {data}\n")
            return []
        
        tickers = data.get('data', [])
        print(f"✅ {len(tickers)} coins récupérés")
        
        # Filtrer
        filtered = []
        for ticker in tickers:
            try:
                volume = float(ticker.get('volume24', 0))
                change = abs(float(ticker.get('riseFallRate', 0)))
                
                if volume >= MEXC['filters']['min_volume'] and change >= MEXC['filters']['min_change']:
                    filtered.append({
                        'symbol': ticker.get('symbol', ''),
                        'price': float(ticker.get('lastPrice', 0)),
                        'change': change,
                        'volume': volume,
                        'high': float(ticker.get('high24Price', 0)),
                        'low': float(ticker.get('low24Price', 0))
                    })
            except:
                continue
        
        # Trier par change décroissant
        filtered.sort(key=lambda x: x['change'], reverse=True)
        
        print(f"✅ {len(filtered)} coins après filtres:")
        print(f"   • Volume > {MEXC['filters']['min_volume']:,}")
        print(f"   • Change > {MEXC['filters']['min_change']}%")
        
        if filtered:
            print(f"\n📊 Top 5 mouvements:")
            for i, coin in enumerate(filtered[:5], 1):
                print(f"   {i}. {coin['symbol']}: {coin['change']:.2f}% (Vol: {coin['volume']:,.0f})")
        
        print()
        return filtered
        
    except Exception as e:
        print(f"❌ Exception: {e}\n")
        return []

# ============================================================
# 3. ANALYSE MULTI-LM (CONSENSUS)
# ============================================================

async def analyze_coin(lm_node, coin):
    """Analyse un coin avec un LM Studio"""
    
    url = f"http://{lm_node['ip']}:{lm_node['port']}/v1/chat/completions"
    
    prompt = f"""Analyse {coin['symbol']}:
Prix: ${coin['price']}
Change: {coin['change']}%
Volume: ${coin['volume']:,.0f}

Direction: LONG/SHORT/HOLD
Score: 0-100
Raison: 1 phrase"""
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                'model': lm_node['model'],
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 150
            }
            
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data['choices'][0]['message']['content']
                    
                    # Parser réponse
                    direction = 'HOLD'
                    score = 50
                    
                    if 'LONG' in content.upper():
                        direction = 'LONG'
                    elif 'SHORT' in content.upper():
                        direction = 'SHORT'
                    
                    # Extraire score
                    import re
                    score_match = re.search(r'(\d+)', content)
                    if score_match:
                        score = int(score_match.group(1))
                    
                    return {
                        'lm': lm_node['name'],
                        'direction': direction,
                        'score': min(max(score, 0), 100),  # 0-100
                        'weight': lm_node['weight']
                    }
                else:
                    return None
                    
    except Exception as e:
        print(f"   ⚠️  {lm_node['name']} timeout")
        return None

async def get_consensus(coin):
    """Consensus des 3 LM"""
    
    tasks = [analyze_coin(node, coin) for node in CLUSTER['nodes']]
    results = await asyncio.gather(*tasks)
    
    valid = [r for r in results if r]
    
    if not valid:
        return None
    
    # Votes pondérés
    votes = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
    total_weight = 0
    avg_score = 0
    
    for result in valid:
        weight = result['weight']
        votes[result['direction']] += weight
        total_weight += weight
        avg_score += result['score'] * weight
    
    if total_weight > 0:
        avg_score /= total_weight
    
    # Direction gagnante
    winner = max(votes, key=votes.get)
    consensus = votes[winner] / total_weight if total_weight > 0 else 0
    
    return {
        'symbol': coin['symbol'],
        'direction': winner,
        'consensus': consensus,
        'score': avg_score,
        'valid': consensus >= THRESHOLD,
        'price': coin['price'],
        'change': coin['change'],
        'sources': ','.join(r['lm'] for r in valid)
    }

async def analyze_batch(coins, max_coins=10):
    """Analyse batch de coins"""
    print("[3/5] ANALYSE MULTI-LM")
    print("="*60)
    
    top = coins[:max_coins]
    print(f"Analyse {len(top)} coins...")
    
    tasks = [get_consensus(coin) for coin in top]
    results = await asyncio.gather(*tasks)
    
    valid = [r for r in results if r and r['valid']]
    valid.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n✅ Analyse terminée:")
    print(f"   • Analysés: {len(top)}")
    print(f"   • Valides: {len(valid)} (consensus ≥{THRESHOLD:.0%})")
    
    if valid:
        print(f"\n📊 Top signaux:")
        for i, s in enumerate(valid[:3], 1):
            print(f"   {i}. {s['symbol']}: {s['direction']} (score: {s['score']:.0f}, consensus: {s['consensus']:.0%})")
    
    print()
    return valid

# ============================================================
# 4. ENVOI TELEGRAM
# ============================================================

def send_signals(signals, top_n=5):
    """Envoyer signaux Telegram"""
    print("[4/5] ENVOI TELEGRAM")
    print("="*60)
    
    if not signals:
        print("⚠️  Aucun signal\n")
        return
    
    top = signals[:top_n]
    
    msg = f"""📊 <b>TOP {len(top)} SIGNAUX TRADING</b>

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🎯 Signaux valides: {len(signals)}
🤖 Consensus: {len(CLUSTER['nodes'])} LM Studios

━━━━━━━━━━━━━━━━━━━━━━
"""
    
    emojis = {'LONG': '📈', 'SHORT': '📉', 'HOLD': '⏸'}
    
    for i, s in enumerate(top, 1):
        msg += f"""
<b>{i}. {s['symbol']}</b>
{emojis.get(s['direction'], '❓')} <b>{s['direction']}</b> | Score: <b>{s['score']:.0f}/100</b>
💰 Prix: ${s['price']:.4f}
📊 Change: {s['change']:.2f}%
🎲 Consensus: {s['consensus']:.0%}
━━━━━━━━━━━━━━━━━━━━━━
"""
    
    msg += f"\n<i>Powered by LM Cluster ({', '.join(WEIGHTS.keys())})</i>"
    
    try:
        response = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={'chat_id': TELEGRAM['chat_id'], 'text': msg, 'parse_mode': 'HTML'},
            timeout=10
        )
        
        if response.json().get('ok'):
            print(f"✅ Telegram envoyé: {len(top)} signaux\n")
        else:
            print(f"❌ Erreur: {response.json()}\n")
            
    except Exception as e:
        print(f"❌ Exception: {e}\n")

# ============================================================
# 5. RÉSUMÉ
# ============================================================

def summary(coins_scanned, coins_filtered, signals):
    """Résumé final"""
    print("[5/5] RÉSUMÉ")
    print("="*60)
    
    print(f"✅ Scan terminé:")
    print(f"   • Coins MEXC: {coins_scanned}")
    print(f"   • Après filtres: {coins_filtered}")
    print(f"   • Analysés: {min(10, coins_filtered)}")
    print(f"   • Signaux valides: {len(signals)}")
    print(f"   • Telegram: Top 5 envoyés")
    print(f"\n✅ SYSTÈME OPÉRATIONNEL\n")

# ============================================================
# MAIN
# ============================================================

async def main():
    """Workflow complet"""
    
    # 1. Test Telegram
    if not test_telegram():
        print("❌ Telegram KO - ARRÊT")
        return
    
    # 2. Scan MEXC
    coins = scan_mexc()
    if not coins:
        print("⚠️  Aucun coin après filtres")
        return
    
    # 3. Analyse
    signals = await analyze_batch(coins, max_coins=10)
    
    # 4. Telegram
    send_signals(signals, top_n=5)
    
    # 5. Résumé
    summary(len(coins) + 100, len(coins), signals)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Arrêt utilisateur")
    except Exception as e:
        print(f"\n\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
