#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COINGLASS CLIENT - Données de liquidation et Open Interest
Intègre les métriques de liquidation dans le scoring
"""
import setup_cuda

import requests
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta


@dataclass
class LiquidationData:
    """Données de liquidation pour un symbole"""
    symbol: str
    timestamp: datetime
    long_liquidations: float  # Volume liquidé long (USD)
    short_liquidations: float  # Volume liquidé short (USD)
    total_liquidations: float
    liquidation_ratio: float  # long/short ratio
    open_interest: float
    oi_change_24h: float  # % change OI


class CoinglassClient:
    """Client pour l'API Coinglass (données de liquidation)"""

    # API publique (sans clé)
    BASE_URL = "https://open-api.coinglass.com/public/v2"

    # Alternative: API non-officielle (scraping-style)
    ALT_URL = "https://fapi.coinglass.com/api"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
        if api_key:
            self.session.headers['coinglassSecret'] = api_key

        self.cache = {}
        self.cache_ttl = 60  # 60 secondes

    def _is_cached(self, key: str) -> bool:
        """Vérifie si une donnée est en cache et valide"""
        if key not in self.cache:
            return False
        cached_time, _ = self.cache[key]
        return (time.time() - cached_time) < self.cache_ttl

    def _get_cached(self, key: str):
        """Récupère une donnée du cache"""
        if self._is_cached(key):
            return self.cache[key][1]
        return None

    def _set_cache(self, key: str, value):
        """Met en cache une donnée"""
        self.cache[key] = (time.time(), value)

    def fetch_liquidation_chart(self, symbol: str = "BTC", interval: str = "h1") -> Optional[Dict]:
        """
        Récupère les données de liquidation agrégées
        interval: h1, h4, h12, h24
        """
        cache_key = f"liq_{symbol}_{interval}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            # Essayer l'API alternative (plus fiable sans clé)
            url = f"{self.ALT_URL}/futures/liquidation/chart"
            params = {
                'symbol': symbol.upper(),
                'interval': interval
            }
            resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') or data.get('code') == '0':
                    result = data.get('data', [])
                    self._set_cache(cache_key, result)
                    return result
        except Exception as e:
            print(f"[Coinglass] Erreur liquidation chart: {e}")

        return None

    def fetch_liquidation_aggregated(self, symbol: str = "BTC") -> Optional[Dict]:
        """
        Récupère les liquidations agrégées 24h
        """
        cache_key = f"liq_agg_{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.ALT_URL}/futures/liquidation/info"
            params = {'symbol': symbol.upper()}
            resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') or data.get('code') == '0':
                    result = data.get('data', {})
                    self._set_cache(cache_key, result)
                    return result
        except Exception as e:
            print(f"[Coinglass] Erreur liquidation aggregated: {e}")

        return None

    def fetch_open_interest(self, symbol: str = "BTC") -> Optional[Dict]:
        """
        Récupère l'Open Interest agrégé multi-exchange
        """
        cache_key = f"oi_{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.ALT_URL}/futures/openInterest/chart"
            params = {
                'symbol': symbol.upper(),
                'interval': '0'  # Current
            }
            resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') or data.get('code') == '0':
                    result = data.get('data', {})
                    self._set_cache(cache_key, result)
                    return result
        except Exception as e:
            print(f"[Coinglass] Erreur open interest: {e}")

        return None

    def fetch_funding_rate(self, symbol: str = "BTC") -> Optional[List]:
        """
        Récupère les funding rates multi-exchange
        """
        cache_key = f"funding_{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.ALT_URL}/futures/funding/info"
            params = {'symbol': symbol.upper()}
            resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') or data.get('code') == '0':
                    result = data.get('data', [])
                    self._set_cache(cache_key, result)
                    return result
        except Exception as e:
            print(f"[Coinglass] Erreur funding rate: {e}")

        return None

    def get_liquidation_analysis(self, symbol: str) -> Optional[LiquidationData]:
        """
        Analyse complète des liquidations pour un symbole
        Retourne un objet LiquidationData avec toutes les métriques
        """
        # Récupérer les données
        liq_data = self.fetch_liquidation_aggregated(symbol)
        oi_data = self.fetch_open_interest(symbol)

        if not liq_data:
            return None

        try:
            # Parser les liquidations
            long_liq = float(liq_data.get('longLiquidationUsd', 0) or 0)
            short_liq = float(liq_data.get('shortLiquidationUsd', 0) or 0)
            total_liq = long_liq + short_liq

            # Ratio: >1 = plus de longs liquidés, <1 = plus de shorts
            ratio = (long_liq / short_liq) if short_liq > 0 else 1.0

            # Open Interest
            oi = 0.0
            oi_change = 0.0
            if oi_data:
                oi = float(oi_data.get('openInterest', 0) or 0)
                oi_change = float(oi_data.get('h24Change', 0) or 0)

            return LiquidationData(
                symbol=symbol,
                timestamp=datetime.now(),
                long_liquidations=long_liq,
                short_liquidations=short_liq,
                total_liquidations=total_liq,
                liquidation_ratio=ratio,
                open_interest=oi,
                oi_change_24h=oi_change
            )
        except Exception as e:
            print(f"[Coinglass] Erreur parsing {symbol}: {e}")
            return None

    def calculate_liquidation_score(self, symbol: str) -> float:
        """
        Calcule un score de liquidation pour le trading

        Score positif = favorable aux longs (shorts liquidés, OI en hausse)
        Score négatif = favorable aux shorts (longs liquidés, OI en baisse)
        """
        analysis = self.get_liquidation_analysis(symbol)

        if not analysis:
            return 0.0

        score = 0.0

        # 1. Ratio de liquidation (-1 à +1)
        # Plus de shorts liquidés = bullish
        if analysis.liquidation_ratio < 1:
            # Plus de shorts liquidés
            score += min(0.5, (1 - analysis.liquidation_ratio) * 0.5)
        else:
            # Plus de longs liquidés
            score -= min(0.5, (analysis.liquidation_ratio - 1) * 0.5)

        # 2. OI change
        # OI en hausse avec price up = continuation
        oi_factor = analysis.oi_change_24h / 100  # Normaliser
        score += max(-0.3, min(0.3, oi_factor))

        return score

    def get_top_liquidated(self, top_n: int = 10) -> List[Dict]:
        """
        Récupère les coins avec le plus de liquidations 24h
        """
        try:
            url = f"{self.ALT_URL}/futures/liquidation/order"
            resp = self.session.get(url, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') or data.get('code') == '0':
                    coins = data.get('data', [])
                    # Trier par total liquidations
                    sorted_coins = sorted(
                        coins,
                        key=lambda x: float(x.get('totalVolUsd', 0) or 0),
                        reverse=True
                    )
                    return sorted_coins[:top_n]
        except Exception as e:
            print(f"[Coinglass] Erreur top liquidated: {e}")

        return []


class MEXCOpenInterest:
    """Fallback: Open Interest via MEXC API directement"""

    MEXC_FUTURES_BASE = "https://contract.mexc.com/api/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })

    def fetch_open_interest(self, symbol: str) -> Optional[Dict]:
        """Récupère l'OI depuis MEXC"""
        try:
            url = f"{self.MEXC_FUTURES_BASE}/contract/ticker"
            params = {'symbol': symbol}
            resp = self.session.get(url, params=params, timeout=5)
            data = resp.json()

            if data.get('success') and data.get('data'):
                ticker = data['data']
                return {
                    'symbol': symbol,
                    'open_interest': float(ticker.get('holdVol', 0)),
                    'volume_24h': float(ticker.get('volume24', 0)),
                    'last_price': float(ticker.get('lastPrice', 0)),
                    'change_24h': float(ticker.get('riseFallRate', 0))
                }
        except Exception as e:
            pass
        return None

    def get_oi_analysis(self, symbol: str) -> Dict:
        """Analyse OI pour scoring"""
        oi_data = self.fetch_open_interest(symbol)

        if not oi_data:
            return {'score': 0, 'oi': 0, 'volume': 0}

        oi = oi_data['open_interest']
        volume = oi_data['volume_24h']
        change = oi_data['change_24h']

        # Score basé sur OI et volume
        # High OI + volume = liquidité
        import numpy as np
        liquidity_score = np.log1p(oi) * 0.5 + np.log1p(volume) * 0.5

        # Ajuster par momentum
        momentum_factor = 1.0 + (change / 100)

        return {
            'score': liquidity_score * momentum_factor,
            'oi': oi,
            'volume': volume,
            'change': change
        }


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "#"*80)
    print(" OPEN INTEREST & LIQUIDATION CLIENT - TEST")
    print("#"*80)
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test MEXC OI (fallback, fonctionne sans clé API)
    print("\n" + "="*80)
    print(" MEXC OPEN INTEREST (Fallback)")
    print("="*80)

    mexc_oi = MEXCOpenInterest()
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "HBAR_USDT"]

    for symbol in symbols:
        print(f"\n[{symbol}]")
        analysis = mexc_oi.get_oi_analysis(symbol)

        if analysis['oi'] > 0:
            print(f"  Open Interest: {analysis['oi']:,.0f} contrats")
            print(f"  Volume 24h: {analysis['volume']:,.0f}")
            print(f"  Change 24h: {analysis['change']:+.2f}%")
            print(f"  Liquidity Score: {analysis['score']:.2f}")
        else:
            print(f"  [!] Données non disponibles")

    # Test Coinglass (nécessite clé API)
    print("\n" + "="*80)
    print(" COINGLASS API (nécessite clé API)")
    print("="*80)

    client = CoinglassClient()
    analysis = client.get_liquidation_analysis("BTC")

    if analysis:
        print(f"  Long Liq: ${analysis.long_liquidations:,.0f}")
        print(f"  Short Liq: ${analysis.short_liquidations:,.0f}")
    else:
        print("  [INFO] API Coinglass nécessite une clé API payante")
        print("  [INFO] Utilisez MEXCOpenInterest comme fallback")

    print("\n[OK] Test terminé!")
