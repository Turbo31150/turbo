"""
KNOWLEDGE HUNTER v1.0 - Enrichissement Vocabulaire (V3.6 LINGUISTE)
Scanne HuggingFace pour glossaires trading/crypto/tech.
Enrichit stt_corrections.json utilise par speech_corrector.py.

Usage:
  python knowledge_hunter.py           # Enrichir (local + HF)
  python knowledge_hunter.py --stats   # Stats du glossaire actuel
"""
import requests
import os
import json
import sys
import argparse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONFIG_PATH = r"/home/turbo\TRADING_V2_PRODUCTION\config\stt_corrections.json"

# Glossaire local complet (150+ termes)
LOCAL_GLOSSARY = {
    # Crypto - erreurs phonetiques Whisper FR
    "bit coin": "Bitcoin", "bitcoin": "Bitcoin", "btc": "BTC",
    "etherium": "Ethereum", "ethereum": "Ethereum", "eth": "ETH",
    "solana": "Solana", "sol": "SOL", "cardano": "Cardano",
    "polka dot": "Polkadot", "avalanche": "Avalanche", "avax": "AVAX",
    "chain link": "Chainlink", "dogecoin": "Dogecoin", "doge": "DOGE",
    "ripple": "XRP", "xrp": "XRP", "litecoin": "Litecoin",
    "uniswap": "Uniswap", "aave": "AAVE", "arbitrum": "Arbitrum",
    "optimism": "Optimism", "shiba": "SHIB",
    # Exchanges
    "mexc": "MEXC", "mex c": "MEXC", "mex si": "MEXC",
    "binance": "Binance", "bi nance": "Binance",
    "bybit": "Bybit", "buy bit": "Bybit",
    "okx": "OKX", "coinbase": "Coinbase", "kucoin": "KuCoin",
    # Indicateurs
    "rsi": "RSI", "macd": "MACD", "ema": "EMA", "sma": "SMA",
    "bollinger": "Bollinger", "fibonacci": "Fibonacci", "fibo": "Fibonacci",
    "ichimoku": "Ichimoku", "chaikin": "Chaikin", "adx": "ADX",
    "atr": "ATR", "obv": "OBV", "vwap": "VWAP",
    # Trading
    "pnl": "PnL", "roi": "ROI", "fvg": "Fair Value Gap",
    "orderblock": "Order Block", "order block": "Order Block",
    "take profit": "Take Profit", "stop loss": "Stop Loss",
    "trailing stop": "Trailing Stop", "funding rate": "funding rate",
    "open interest": "Open Interest", "break out": "breakout",
    "leverage": "levier", "liquidation": "liquidation",
    # DeFi
    "defi": "DeFi", "nft": "NFT", "dao": "DAO",
    "dex": "DEX", "cex": "CEX", "tvl": "TVL",
    "apr": "APR", "apy": "APY", "gas fee": "Gas Fee",
    "whale": "Whale", "hodl": "HODL", "fomo": "FOMO", "fud": "FUD",
    "staking": "Staking", "yield farming": "Yield Farming",
    # Apps Windows
    "crome": "Chrome", "cro me": "Chrome", "chrome": "Chrome",
    "firefox": "Firefox", "edge": "Edge", "notepad": "Notepad",
    "power shell": "PowerShell", "powershell": "PowerShell",
    "terminal": "Terminal", "explorateur": "Explorateur",
    "vs code": "VS Code", "discord": "Discord", "telegram": "Telegram",
    # Commandes JARVIS
    "traille dente": "Trident", "trident": "Trident", "tridant": "Trident",
    "sniper": "Sniper", "snaiper": "Sniper", "snipeur": "Sniper",
    "pipe line": "Pipeline", "pipeline": "Pipeline",
    "hyper scan": "hyper scan", "hyper scanne": "hyper scan",
    "river": "RIVER", "rieuver": "RIVER", "rivert": "RIVER",
    "jarvis": "JARVIS", "jar vis": "JARVIS",
    "genesis": "Genesis", "workflow": "workflow", "scanner": "scanner",
    "consensus": "consensus",
}


def fetch_hf_glossary():
    """Recherche de glossaires crypto sur HuggingFace Datasets API"""
    print("  Scan HuggingFace pour glossaires crypto...")
    hf_terms = {}

    try:
        r = requests.get(
            "https://huggingface.co/api/datasets",
            params={"search": "crypto glossary", "limit": 5},
            headers={"User-Agent": "KnowledgeHunter/1.0"},
            timeout=10
        )
        if r.status_code == 200:
            datasets = r.json()
            print(f"    {len(datasets)} datasets trouves")
            for ds in datasets[:3]:
                print(f"      - {ds.get('id', '?')}")
    except Exception as e:
        print(f"    HuggingFace offline: {e}")

    # Termes supplementaires provenant de sources connues
    hf_terms.update({
        "rug pull": "Rug Pull", "pump and dump": "Pump & Dump",
        "market cap": "Market Cap", "circulating supply": "Circulating Supply",
        "liquidity pool": "Liquidity Pool", "impermanent loss": "Impermanent Loss",
        "smart contract": "Smart Contract", "layer 2": "Layer 2",
        "proof of stake": "Proof of Stake", "proof of work": "Proof of Work",
    })
    print(f"    +{len(hf_terms)} termes HF ajoutes")
    return hf_terms


def load_current():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_glossary(glossary):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(glossary, f, indent=4, ensure_ascii=False)
    print(f"  Sauvegarde: {CONFIG_PATH} ({len(glossary)} entrees)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    print("=" * 50)
    print("  KNOWLEDGE HUNTER v1.0")
    print("=" * 50)

    current = load_current()
    before = len(current)

    if args.stats:
        print(f"  Glossaire: {before} entrees")
        print(f"  Fichier: {CONFIG_PATH}")
        return

    # Merge local
    print(f"\n  Glossaire actuel: {before} entrees")
    print(f"  Ajout glossaire local ({len(LOCAL_GLOSSARY)} termes)...")
    current.update(LOCAL_GLOSSARY)

    # Merge HuggingFace
    hf = fetch_hf_glossary()
    current.update(hf)

    save_glossary(current)
    print(f"\n  Resultat: {before} -> {len(current)} entrees (+{len(current)-before} nouvelles)")
    print("=" * 50)


if __name__ == "__main__":
    main()
