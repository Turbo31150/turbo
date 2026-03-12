#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LIVE DATA CONNECTOR - Connexion temps reel MEXC + Multi-IA
"""
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import ccxt
import asyncio
import aiohttp
import numpy as np
import time
from datetime import datetime
from typing import Dict, List, Optional
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "exchange": "mexc",
    "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "timeframe": "15m",
    "lookback": 100,
    "lm_studio": {
        "url": "http://192.168.1.85:1234/v1/chat/completions",
        "models": ["qwen/qwen3-coder-30b", "openai/gpt-oss-20b"]
    },
    "update_interval": 60,  # secondes
    "mode": "SIMULATION"
}


class MEXCConnector:
    """Connecteur MEXC via ccxt"""

    def __init__(self, config: Dict = CONFIG):
        self.config = config
        self.exchange = ccxt.mexc({
            'apiKey': os.environ.get('MEXC_API_KEY', ''),
            'secret': os.environ.get('MEXC_API_SECRET', ''),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        print(f"[MEXC] Connecteur initialise")

    def fetch_ohlcv(self, symbol: str, timeframe: str = "15m", limit: int = 100) -> Dict[str, np.ndarray]:
        """Recupere les donnees OHLCV"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            data = {
                'timestamp': np.array([x[0] for x in ohlcv], dtype=np.float64),
                'open': np.array([x[1] for x in ohlcv], dtype=np.float32),
                'high': np.array([x[2] for x in ohlcv], dtype=np.float32),
                'low': np.array([x[3] for x in ohlcv], dtype=np.float32),
                'close': np.array([x[4] for x in ohlcv], dtype=np.float32),
                'volume': np.array([x[5] for x in ohlcv], dtype=np.float32)
            }

            return data
        except Exception as e:
            print(f"[MEXC] Erreur fetch {symbol}: {e}")
            return None

    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Recupere le ticker actuel"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'price': ticker['last'],
                'change_24h': ticker.get('percentage', 0),
                'volume_24h': ticker.get('quoteVolume', 0),
                'high_24h': ticker.get('high', 0),
                'low_24h': ticker.get('low', 0)
            }
        except Exception as e:
            print(f"[MEXC] Erreur ticker {symbol}: {e}")
            return None

    def get_balance(self) -> Dict:
        """Recupere le solde (mode live uniquement)"""
        if self.config['mode'] == 'SIMULATION':
            return {'USDT': 10000, 'BTC': 0, 'ETH': 0}
        try:
            balance = self.exchange.fetch_balance()
            return {k: v['free'] for k, v in balance['total'].items() if v > 0}
        except Exception as e:
            print(f"[MEXC] Erreur balance: {e}")
            return {}


class LiveTradingSystem:
    """Systeme de trading en temps reel"""

    def __init__(self, config: Dict = CONFIG):
        self.config = config
        self.mexc = MEXCConnector(config)
        self.running = False
        self.last_signals = {}

        print("\n" + "="*60)
        print(" LIVE TRADING SYSTEM")
        print("="*60)
        print(f" Mode: {config['mode']}")
        print(f" Symboles: {', '.join(config['symbols'])}")
        print(f" Timeframe: {config['timeframe']}")
        print("="*60 + "\n")

    async def analyze_symbol(self, symbol: str) -> Dict:
        """Analyse un symbole"""
        print(f"\n[ANALYSE] {symbol}")

        # Fetch donnees
        ohlcv = self.mexc.fetch_ohlcv(symbol, self.config['timeframe'], self.config['lookback'])
        if ohlcv is None:
            return None

        ticker = self.mexc.get_ticker(symbol)

        # Importer les strategies
        from gpu_strategies_hybrid import StrategyOrchestrator

        orchestrator = StrategyOrchestrator(max_workers=4)
        signals = orchestrator.analyze(ohlcv)
        consensus = orchestrator.get_consensus(signals)

        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'signals': signals,
            'consensus': consensus
        }

        # Afficher
        signal_icon = {"BUY": "[+++]", "SELL": "[---]", "HOLD": "[===]"}
        sig_val = consensus['signal'].value
        print(f"  {signal_icon.get(sig_val, '[???]')} {sig_val} | Conf: {consensus['confidence']:.0%}")

        return result

    async def run_cycle(self):
        """Execute un cycle d'analyse"""
        print(f"\n{'='*60}")
        print(f" CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        results = []
        for symbol in self.config['symbols']:
            result = await self.analyze_symbol(symbol)
            if result:
                results.append(result)
                self.last_signals[symbol] = result

        # Sauvegarder
        with open('last_signals.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'signals': [{
                    'symbol': r['symbol'],
                    'signal': r['consensus']['signal'].value,
                    'confidence': r['consensus']['confidence'],
                    'price': r['ticker']['price'] if r['ticker'] else None
                } for r in results]
            }, f, indent=2)

        return results

    async def run(self):
        """Boucle principale"""
        self.running = True
        print("[LIVE] Demarrage boucle de trading...")

        while self.running:
            try:
                await self.run_cycle()
                print(f"\n[LIVE] Prochaine analyse dans {self.config['update_interval']}s...")
                await asyncio.sleep(self.config['update_interval'])
            except KeyboardInterrupt:
                print("\n[LIVE] Arret demande...")
                self.running = False
            except Exception as e:
                print(f"[LIVE] Erreur: {e}")
                await asyncio.sleep(10)

    def stop(self):
        """Arrete le systeme"""
        self.running = False


# ============================================================================
# MAIN
# ============================================================================

async def main():
    print("\n" + "#"*60)
    print(" LIVE DATA CONNECTOR - DEMARRAGE")
    print("#"*60 + "\n")

    system = LiveTradingSystem(CONFIG)

    try:
        await system.run()
    except KeyboardInterrupt:
        print("\n[STOP] Arret du systeme...")
        system.stop()


if __name__ == "__main__":
    asyncio.run(main())
