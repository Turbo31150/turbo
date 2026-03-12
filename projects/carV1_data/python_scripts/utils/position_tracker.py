#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POSITION TRACKER - Suivi des positions avec analyse IA
Intègre LM Studio pour analyse intelligente des positions
"""
import setup_cuda

import json
import os
import requests
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Position:
    """Position de trading"""
    symbol: str
    side: PositionSide
    leverage: int
    entry_price: float
    current_price: float
    liquidation_price: float
    position_size: float  # En USDT
    margin: float
    pnl_usdt: float
    pnl_percent: float
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    margin_ratio: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['side'] = self.side.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> 'Position':
        d['side'] = PositionSide(d['side'])
        return cls(**d)

    def distance_to_liquidation(self) -> float:
        """Distance en % jusqu'à la liquidation"""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.liquidation_price) / self.current_price * 100
        else:
            return (self.liquidation_price - self.current_price) / self.current_price * 100

    def distance_to_entry(self) -> float:
        """Distance en % par rapport à l'entrée"""
        return (self.current_price - self.entry_price) / self.entry_price * 100

    def distance_to_tp(self) -> Optional[float]:
        """Distance en % jusqu'au TP"""
        if self.take_profit is None:
            return None
        return (self.take_profit - self.current_price) / self.current_price * 100


class PositionTracker:
    """Gestionnaire de positions avec sauvegarde"""

    def __init__(self, filepath: str = None):
        self.filepath = filepath or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "positions.json"
        )
        self.positions: Dict[str, Position] = {}
        self.load()

    def add_position(self, position: Position):
        """Ajoute ou met à jour une position"""
        position.timestamp = datetime.now().isoformat()
        self.positions[position.symbol] = position
        self.save()
        print(f"[Position] {position.symbol} ajoutée/mise à jour")

    def remove_position(self, symbol: str):
        """Supprime une position"""
        if symbol in self.positions:
            del self.positions[symbol]
            self.save()
            print(f"[Position] {symbol} supprimée")

    def update_price(self, symbol: str, current_price: float):
        """Met à jour le prix actuel d'une position"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.current_price = current_price

            # Recalculer PnL
            if pos.side == PositionSide.LONG:
                pnl_pct = (current_price - pos.entry_price) / pos.entry_price * 100
            else:
                pnl_pct = (pos.entry_price - current_price) / pos.entry_price * 100

            pos.pnl_percent = pnl_pct * pos.leverage
            pos.pnl_usdt = pos.margin * (pnl_pct * pos.leverage / 100)
            pos.timestamp = datetime.now().isoformat()

            self.save()

    def save(self):
        """Sauvegarde les positions"""
        data = {k: v.to_dict() for k, v in self.positions.items()}
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self):
        """Charge les positions"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.positions = {k: Position.from_dict(v) for k, v in data.items()}
                print(f"[Position] {len(self.positions)} positions chargées")
            except Exception as e:
                print(f"[!] Erreur chargement positions: {e}")
                self.positions = {}

    def get_total_pnl(self) -> float:
        """PnL total de toutes les positions"""
        return sum(p.pnl_usdt for p in self.positions.values())

    def get_total_margin(self) -> float:
        """Marge totale utilisée"""
        return sum(p.margin for p in self.positions.values())

    def get_risk_summary(self) -> Dict:
        """Résumé des risques"""
        if not self.positions:
            return {}

        positions = list(self.positions.values())
        return {
            'total_positions': len(positions),
            'total_pnl': self.get_total_pnl(),
            'total_margin': self.get_total_margin(),
            'avg_leverage': np.mean([p.leverage for p in positions]),
            'most_at_risk': min(positions, key=lambda p: p.distance_to_liquidation()).symbol,
            'min_liq_distance': min(p.distance_to_liquidation() for p in positions)
        }

    def print_summary(self):
        """Affiche un résumé des positions"""
        print("\n" + "="*80)
        print(" POSITIONS ACTIVES")
        print("="*80)

        if not self.positions:
            print(" Aucune position")
            return

        for symbol, pos in self.positions.items():
            pnl_color = "+" if pos.pnl_usdt >= 0 else ""
            liq_dist = pos.distance_to_liquidation()

            print(f"\n [{pos.side.value}] {symbol} @ {pos.leverage}x")
            print(f"   Entrée: {pos.entry_price:.6f} | Actuel: {pos.current_price:.6f}")
            print(f"   PnL: {pnl_color}{pos.pnl_usdt:.2f} USDT ({pnl_color}{pos.pnl_percent:.1f}%)")
            print(f"   Liquidation: {pos.liquidation_price:.6f} (distance: {liq_dist:.1f}%)")
            print(f"   Marge: {pos.margin:.2f} USDT | Position: {pos.position_size:.2f} USDT")
            if pos.take_profit:
                tp_dist = pos.distance_to_tp()
                print(f"   TP: {pos.take_profit:.6f} (distance: {tp_dist:.1f}%)")

        risk = self.get_risk_summary()
        print("\n" + "-"*80)
        print(f" TOTAL PnL: {risk['total_pnl']:+.2f} USDT")
        print(f" Marge utilisée: {risk['total_margin']:.2f} USDT")
        print(f" Position la plus risquée: {risk['most_at_risk']} ({risk['min_liq_distance']:.1f}% de liq)")
        print("-"*80)


class LMStudioAnalyzer:
    """Analyseur IA via LM Studio"""

    def __init__(self, base_url: str = "http://192.168.1.85:1234"):
        self.base_url = base_url
        self.endpoint = f"{base_url}/v1/chat/completions"
        self.model = "local-model"  # LM Studio utilise ce nom générique
        self.available = self._check_connection()

    def _check_connection(self) -> bool:
        """Vérifie si LM Studio est accessible"""
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if resp.status_code == 200:
                print(f"[LM Studio] Connecté à {self.base_url}")
                return True
        except:
            pass
        print(f"[LM Studio] Non disponible à {self.base_url}")
        return False

    def analyze_position(self, position: Position, market_data: Dict = None) -> str:
        """Analyse une position avec l'IA"""
        if not self.available:
            return "LM Studio non disponible"

        # Construire le prompt
        prompt = f"""Analyse cette position de trading crypto et donne des recommandations concrètes:

POSITION:
- Symbole: {position.symbol}
- Direction: {position.side.value}
- Levier: {position.leverage}x
- Prix d'entrée: {position.entry_price}
- Prix actuel: {position.current_price}
- Prix de liquidation: {position.liquidation_price}
- Distance liquidation: {position.distance_to_liquidation():.1f}%
- PnL: {position.pnl_usdt:+.2f} USDT ({position.pnl_percent:+.1f}%)
- Marge: {position.margin:.2f} USDT
- Take Profit: {position.take_profit if position.take_profit else 'Non défini'}

QUESTIONS:
1. Quel est le niveau de risque actuel (faible/moyen/élevé/critique)?
2. Faut-il ajouter de la marge pour éviter la liquidation?
3. Le TP actuel est-il réaliste?
4. Recommandation: HOLD, ADD MARGIN, REDUCE POSITION, ou CLOSE?

Réponds de manière concise et actionnable."""

        try:
            resp = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Tu es un expert en trading crypto. Donne des conseils clairs et directs."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                return data['choices'][0]['message']['content']
            else:
                return f"Erreur API: {resp.status_code}"

        except Exception as e:
            return f"Erreur: {e}"

    def analyze_portfolio(self, positions: List[Position]) -> str:
        """Analyse le portfolio complet"""
        if not self.available:
            return "LM Studio non disponible"

        if not positions:
            return "Aucune position à analyser"

        # Résumé des positions
        summary = []
        total_pnl = 0
        total_margin = 0

        for pos in positions:
            total_pnl += pos.pnl_usdt
            total_margin += pos.margin
            summary.append(f"- {pos.symbol} {pos.side.value} {pos.leverage}x: {pos.pnl_usdt:+.2f} USDT ({pos.pnl_percent:+.1f}%), liq à {pos.distance_to_liquidation():.1f}%")

        prompt = f"""Analyse ce portfolio de positions crypto:

POSITIONS:
{chr(10).join(summary)}

TOTAUX:
- PnL total: {total_pnl:+.2f} USDT
- Marge totale: {total_margin:.2f} USDT
- Nombre de positions: {len(positions)}

QUESTIONS:
1. Quelle est la santé globale du portfolio?
2. Quelle position est la plus urgente à gérer?
3. Stratégie recommandée pour limiter les pertes?
4. Faut-il hedger avec des shorts?

Réponds de manière concise avec des actions prioritaires."""

        try:
            resp = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Tu es un expert en gestion de risque crypto."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 600
                },
                timeout=90
            )

            if resp.status_code == 200:
                data = resp.json()
                return data['choices'][0]['message']['content']
            else:
                return f"Erreur API: {resp.status_code}"

        except Exception as e:
            return f"Erreur: {e}"


class MultiStrategyAnalyzer:
    """Analyse multi-stratégie pour une position"""

    def __init__(self):
        from unified_orchestrator import UnifiedOrchestrator
        self.orchestrator = UnifiedOrchestrator()

    def fetch_ohlcv(self, symbol: str, limit: int = 200) -> Optional[Dict]:
        """Récupère les données OHLCV depuis MEXC"""
        try:
            # Convertir format: HBARUSDT -> HBAR_USDT
            mexc_symbol = symbol.replace('USDT', '_USDT')

            url = f"https://contract.mexc.com/api/v1/contract/kline/{mexc_symbol}"
            params = {'interval': 'Min60', 'limit': limit}
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if data.get('success'):
                kline = data.get('data', {})
                return {
                    'open': np.array([float(x) for x in kline.get('open', [])]),
                    'high': np.array([float(x) for x in kline.get('high', [])]),
                    'low': np.array([float(x) for x in kline.get('low', [])]),
                    'close': np.array([float(x) for x in kline.get('close', [])]),
                    'volume': np.array([float(x) for x in kline.get('vol', [])])
                }
        except Exception as e:
            print(f"[!] Erreur fetch OHLCV {symbol}: {e}")
        return None

    def analyze_position_strategies(self, symbol: str) -> Dict:
        """Analyse une position avec toutes les stratégies"""
        ohlcv = self.fetch_ohlcv(symbol)

        if ohlcv is None or len(ohlcv['close']) < 50:
            return {'error': 'Données insuffisantes'}

        # Exécuter les stratégies
        signals = self.orchestrator.analyze(ohlcv)
        consensus = self.orchestrator.get_consensus(signals)

        # Détail par stratégie
        strategy_details = []
        for signal in signals:
            strategy_details.append({
                'name': signal.strategy,
                'signal': signal.signal_type.name,
                'confidence': signal.confidence
            })

        return {
            'symbol': symbol,
            'current_price': float(ohlcv['close'][-1]),
            'signal': consensus['signal'].name,
            'buy_score': consensus['buy_score'],
            'sell_score': consensus['sell_score'],
            'confidence': consensus['confidence'],
            'strategies': strategy_details,
            'buy_count': sum(1 for s in signals if s.signal_type.name == 'BUY'),
            'sell_count': sum(1 for s in signals if s.signal_type.name == 'SELL'),
            'hold_count': sum(1 for s in signals if s.signal_type.name == 'HOLD')
        }


# ============================================================================
# POSITIONS UTILISATEUR
# ============================================================================

def load_user_positions() -> PositionTracker:
    """Charge les positions de l'utilisateur"""
    tracker = PositionTracker()

    # Ajouter les positions manuellement si pas encore sauvegardées
    if not tracker.positions:
        # Position 1: HBAR/USDT
        tracker.add_position(Position(
            symbol="HBARUSDT",
            side=PositionSide.LONG,
            leverage=200,
            entry_price=0.11194,
            current_price=0.10886,
            liquidation_price=0.09471,
            position_size=485.8310,
            margin=78.9300,
            pnl_usdt=-13.7583,
            pnl_percent=-550.29,
            take_profit=0.15000,
            margin_ratio=3.07
        ))

        # Position 2: IP/USDT
        tracker.add_position(Position(
            symbol="IPUSDT",
            side=PositionSide.LONG,
            leverage=50,
            entry_price=1.483,
            current_price=1.431,
            liquidation_price=1.226,
            position_size=385.2080,
            margin=70.6650,
            pnl_usdt=-13.9880,
            pnl_percent=-171.88,
            take_profit=2.000,
            margin_ratio=2.92
        ))

        # Position 3: POWER/USDT
        tracker.add_position(Position(
            symbol="POWERUSDT",
            side=PositionSide.LONG,
            leverage=50,
            entry_price=0.35468,
            current_price=0.23729,
            liquidation_price=0.14470,
            position_size=260.1975,
            margin=234.2776,
            pnl_usdt=-128.7847,
            pnl_percent=-1638.55,
            margin_ratio=3.73
        ))

    return tracker


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "#"*80)
    print(" POSITION TRACKER + ANALYSE IA")
    print("#"*80)
    print(f" Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Charger les positions
    tracker = load_user_positions()
    tracker.print_summary()

    # Analyse multi-stratégie
    print("\n" + "="*80)
    print(" ANALYSE MULTI-STRATEGIE")
    print("="*80)

    analyzer = MultiStrategyAnalyzer()

    for symbol in tracker.positions.keys():
        print(f"\n[{symbol}] Analyse en cours...")
        result = analyzer.analyze_position_strategies(symbol)

        if 'error' not in result:
            print(f"   Signal: {result['signal']}")
            print(f"   Buy: {result['buy_score']:.1%} | Sell: {result['sell_score']:.1%}")
            print(f"   Stratégies: {result['buy_count']} BUY / {result['sell_count']} SELL / {result['hold_count']} HOLD")
        else:
            print(f"   {result['error']}")

    # Analyse IA
    print("\n" + "="*80)
    print(" ANALYSE IA (LM Studio)")
    print("="*80)

    lm = LMStudioAnalyzer()

    if lm.available:
        positions = list(tracker.positions.values())
        analysis = lm.analyze_portfolio(positions)
        print(f"\n{analysis}")
    else:
        print("\n[INFO] LM Studio non disponible")
        print("[INFO] Démarrez LM Studio sur http://192.168.1.85:1234")

    print("\n[OK] Analyse terminée!")
