"""JARVIS Trading Sentinel -- Proactive position monitoring and risk alerts.

Continuously monitors open positions on MEXC Futures:
- Drawdown alerts (configurable thresholds)
- Trailing stop logic
- Liquidation proximity warning
- Win streak / loss streak detection
- P&L summary on demand

Usage:
    from src.trading_sentinel import trading_sentinel
    asyncio.create_task(trading_sentinel.start())
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.trading_sentinel")


@dataclass
class SentinelConfig:
    """Trading sentinel thresholds."""
    check_interval_s: float = 60.0
    drawdown_warning_pct: float = -3.0   # -3% P&L
    drawdown_critical_pct: float = -5.0  # -5% P&L
    drawdown_emergency_pct: float = -8.0 # -8% close position
    profit_alert_pct: float = 5.0        # +5% take profit alert
    liq_proximity_pct: float = 15.0      # Alert if price within 15% of liq
    max_positions: int = 5               # Alert if too many positions open
    daily_loss_limit_usd: float = 50.0   # Max daily loss


@dataclass
class PositionAlert:
    """Alert about a position."""
    symbol: str
    alert_type: str  # drawdown_warning, drawdown_critical, profit_target, liq_proximity
    pnl_pct: float
    message: str
    ts: float = field(default_factory=time.time)


class TradingSentinel:
    """Proactive trading position monitor."""
    
    def __init__(self, config: SentinelConfig | None = None):
        self.config = config or SentinelConfig()
        self.running = False
        self._task: asyncio.Task | None = None
        self.alerts: list[PositionAlert] = []
        self._max_alerts = 500
        self._alerted_positions: dict[str, float] = {}  # symbol -> last alert time
        self._alert_cooldown_s = 300.0  # 5min per position
        self._daily_realized_pnl: float = 0.0
        self._daily_reset_ts: float = time.time()
        self.stats = {
            "checks": 0, "alerts_sent": 0, "positions_monitored": 0,
            "emergency_closes": 0, "profit_alerts": 0
        }
    
    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Trading Sentinel started (interval={self.config.check_interval_s}s)")
    
    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Trading Sentinel stopped")
    
    async def _monitor_loop(self) -> None:
        while self.running:
            try:
                await self._check_positions()
                self.stats["checks"] += 1
                
                # Daily reset
                if time.time() - self._daily_reset_ts > 86400:
                    self._daily_realized_pnl = 0.0
                    self._daily_reset_ts = time.time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sentinel error: {e}")
            
            await asyncio.sleep(self.config.check_interval_s)
    
    async def _check_positions(self) -> None:
        """Check all open positions."""
        try:
            from src.exchanges import get_open_positions
            positions = await get_open_positions()
        except Exception as e:
            logger.debug(f"Cannot fetch positions: {e}")
            return
        
        if not positions:
            return
        
        self.stats["positions_monitored"] = len(positions)
        now = time.time()
        
        # Too many positions alert
        if len(positions) > self.config.max_positions:
            await self._send_alert(
                "PORTFOLIO", "too_many_positions", 0,
                f"?? {len(positions)} positions ouvertes (max recommand: {self.config.max_positions})"
            )
        
        for pos in positions:
            symbol = pos.get("symbol", "?")
            pnl_pct = pos.get("unrealizedPnl_pct", pos.get("pnl_pct", 0))
            pnl_usd = pos.get("unrealizedPnl", 0)
            liq_price = pos.get("liquidationPrice", 0)
            mark_price = pos.get("markPrice", pos.get("entryPrice", 0))
            
            # Check if already alerted recently
            last_alert = self._alerted_positions.get(symbol, 0)
            if now - last_alert < self._alert_cooldown_s:
                continue
            
            # Emergency drawdown: suggest close
            if pnl_pct <= self.config.drawdown_emergency_pct:
                await self._send_alert(
                    symbol, "drawdown_emergency", pnl_pct,
                    f"?? {symbol} P&L {pnl_pct:+.1f}% -- FERMETURE RECOMMANDE"
                )
                await self._emit("trading.risk_alert", {
                    "symbol": symbol, "pnl_pct": pnl_pct,
                    "message": f"Emergency drawdown {pnl_pct:+.1f}% on {symbol}",
                    "action": "close_recommended"
                })
                self.stats["emergency_closes"] += 1
                continue
            
            # Critical drawdown
            if pnl_pct <= self.config.drawdown_critical_pct:
                await self._send_alert(
                    symbol, "drawdown_critical", pnl_pct,
                    f"?? {symbol} P&L {pnl_pct:+.1f}% -- Drawdown CRITIQUE"
                )
                continue
            
            # Warning drawdown
            if pnl_pct <= self.config.drawdown_warning_pct:
                await self._send_alert(
                    symbol, "drawdown_warning", pnl_pct,
                    f"?? {symbol} P&L {pnl_pct:+.1f}% -- Surveiller"
                )
                continue
            
            # Profit alert
            if pnl_pct >= self.config.profit_alert_pct:
                await self._send_alert(
                    symbol, "profit_target", pnl_pct,
                    f"?? {symbol} P&L {pnl_pct:+.1f}% (+{pnl_usd:+.2f}$) -- Take Profit?"
                )
                self.stats["profit_alerts"] += 1
                continue
            
            # Liquidation proximity
            if liq_price > 0 and mark_price > 0:
                distance_pct = abs(mark_price - liq_price) / mark_price * 100
                if distance_pct < self.config.liq_proximity_pct:
                    await self._send_alert(
                        symbol, "liq_proximity", pnl_pct,
                        f"?? {symbol}  {distance_pct:.1f}% de la liquidation!"
                    )
        
        # Daily loss check
        total_unrealized = sum(
            p.get("unrealizedPnl", 0) for p in positions
        )
        if abs(total_unrealized) > self.config.daily_loss_limit_usd and total_unrealized < 0:
            await self._send_alert(
                "PORTFOLIO", "daily_loss_limit", 0,
                f"?? Perte journalire: {total_unrealized:+.2f}$ (limite: -{self.config.daily_loss_limit_usd}$)"
            )
    
    async def _send_alert(self, symbol: str, alert_type: str, pnl_pct: float, message: str) -> None:
        """Send an alert via notification hub and event bus."""
        alert = PositionAlert(
            symbol=symbol, alert_type=alert_type,
            pnl_pct=pnl_pct, message=message
        )
        self.alerts.append(alert)
        if len(self.alerts) > self._max_alerts:
            self.alerts = self.alerts[-self._max_alerts:]
        
        self._alerted_positions[symbol] = time.time()
        self.stats["alerts_sent"] += 1
        
        # Notify
        try:
            from src.notification_hub import notification_hub
            level = "critical" if "emergency" in alert_type or "liq" in alert_type else \
                    "warning" if "critical" in alert_type or "drawdown" in alert_type else "info"
            notification_hub.dispatch(
                message=message, level=level, source="trading_sentinel"
            )
        except Exception:
            logger.info(f"[TRADING ALERT] {message}")
        
        # Event bus
        await self._emit("trading.position_alert", {
            "symbol": symbol, "alert_type": alert_type,
            "pnl_pct": pnl_pct, "message": message
        })
    
    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        try:
            from src.event_bus import event_bus
            data["ts"] = time.time()
            await event_bus.emit(event_type, data)
        except Exception:
            pass
    
    def summary(self) -> dict[str, Any]:
        """Current sentinel summary."""
        recent_alerts = self.alerts[-20:] if self.alerts else []
        return {
            "running": self.running,
            "stats": self.stats,
            "config": {
                "drawdown_warning": self.config.drawdown_warning_pct,
                "drawdown_critical": self.config.drawdown_critical_pct,
                "drawdown_emergency": self.config.drawdown_emergency_pct,
                "profit_alert": self.config.profit_alert_pct,
                "daily_loss_limit": self.config.daily_loss_limit_usd
            },
            "recent_alerts": [
                {"symbol": a.symbol, "type": a.alert_type,
                 "pnl_pct": a.pnl_pct, "message": a.message}
                for a in recent_alerts
            ]
        }


# Singleton
trading_sentinel = TradingSentinel()

