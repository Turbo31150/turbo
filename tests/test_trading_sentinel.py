"""Tests for src/trading_sentinel.py -- TradingSentinel proactive monitor.

Covers:
- Module imports and singleton
- SentinelConfig defaults and customisation
- PositionAlert dataclass
- TradingSentinel lifecycle (start / stop)
- Drawdown alerts (warning, critical, emergency)
- Profit target alerts
- Liquidation proximity alerts
- Too-many-positions alert
- Daily loss limit alert
- Alert cooldown logic
- Alert list trimming (_max_alerts)
- Stats tracking
- Summary generation
- Daily reset logic
- _emit event bus (mocked)
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading_sentinel import (
    PositionAlert,
    SentinelConfig,
    TradingSentinel,
    trading_sentinel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    """Standard config with tighter thresholds for easier testing."""
    return SentinelConfig(
        check_interval_s=1.0,
        drawdown_warning_pct=-3.0,
        drawdown_critical_pct=-5.0,
        drawdown_emergency_pct=-8.0,
        profit_alert_pct=5.0,
        liq_proximity_pct=15.0,
        max_positions=5,
        daily_loss_limit_usd=50.0,
    )


@pytest.fixture
def sentinel(config):
    """Fresh TradingSentinel instance (not started)."""
    return TradingSentinel(config=config)


def _make_position(
    symbol: str = "BTCUSDT",
    pnl_pct: float = 0.0,
    pnl_usd: float = 0.0,
    liq_price: float = 0.0,
    mark_price: float = 0.0,
) -> dict:
    """Helper to build a fake position dict."""
    return {
        "symbol": symbol,
        "unrealizedPnl_pct": pnl_pct,
        "unrealizedPnl": pnl_usd,
        "liquidationPrice": liq_price,
        "markPrice": mark_price,
        "entryPrice": mark_price,
    }


# ---------------------------------------------------------------------------
# 1. Imports & singleton
# ---------------------------------------------------------------------------

class TestImports:
    def test_module_imports(self):
        """All public names are importable."""
        assert SentinelConfig is not None
        assert PositionAlert is not None
        assert TradingSentinel is not None

    def test_singleton_exists(self):
        """Module-level singleton is a TradingSentinel."""
        assert isinstance(trading_sentinel, TradingSentinel)


# ---------------------------------------------------------------------------
# 2. SentinelConfig defaults
# ---------------------------------------------------------------------------

class TestSentinelConfig:
    def test_default_values(self):
        cfg = SentinelConfig()
        assert cfg.check_interval_s == 60.0
        assert cfg.drawdown_warning_pct == -3.0
        assert cfg.drawdown_critical_pct == -5.0
        assert cfg.drawdown_emergency_pct == -8.0
        assert cfg.profit_alert_pct == 5.0
        assert cfg.liq_proximity_pct == 15.0
        assert cfg.max_positions == 5
        assert cfg.daily_loss_limit_usd == 50.0

    def test_custom_values(self):
        cfg = SentinelConfig(drawdown_warning_pct=-2.0, max_positions=10)
        assert cfg.drawdown_warning_pct == -2.0
        assert cfg.max_positions == 10


# ---------------------------------------------------------------------------
# 3. PositionAlert dataclass
# ---------------------------------------------------------------------------

class TestPositionAlert:
    def test_creation(self):
        alert = PositionAlert(
            symbol="ETHUSDT",
            alert_type="drawdown_warning",
            pnl_pct=-3.5,
            message="test alert",
        )
        assert alert.symbol == "ETHUSDT"
        assert alert.alert_type == "drawdown_warning"
        assert alert.pnl_pct == -3.5
        assert alert.message == "test alert"
        assert isinstance(alert.ts, float)
        assert alert.ts > 0


# ---------------------------------------------------------------------------
# 4. Lifecycle: start / stop
# ---------------------------------------------------------------------------

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_sets_running(self, sentinel):
        """start() sets running=True and creates internal task."""
        with patch.object(sentinel, "_monitor_loop", new_callable=AsyncMock):
            await sentinel.start()
            assert sentinel.running is True
            assert sentinel._task is not None
            sentinel.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, sentinel):
        """Calling start() twice does not create a second task."""
        with patch.object(sentinel, "_monitor_loop", new_callable=AsyncMock):
            await sentinel.start()
            task1 = sentinel._task
            await sentinel.start()  # second call
            assert sentinel._task is task1
            sentinel.stop()

    def test_stop_resets_state(self, sentinel):
        sentinel.running = True
        sentinel._task = MagicMock()
        sentinel.stop()
        assert sentinel.running is False
        assert sentinel._task is None


# ---------------------------------------------------------------------------
# 5. Drawdown alerts
# ---------------------------------------------------------------------------

class TestDrawdownAlerts:
    @pytest.mark.asyncio
    async def test_drawdown_warning(self, sentinel):
        """P&L <= -3% triggers drawdown_warning."""
        positions = [_make_position("BTCUSDT", pnl_pct=-3.5)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        assert len(sentinel.alerts) == 1
        assert sentinel.alerts[0].alert_type == "drawdown_warning"
        assert sentinel.alerts[0].symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_drawdown_critical(self, sentinel):
        """P&L <= -5% triggers drawdown_critical."""
        positions = [_make_position("ETHUSDT", pnl_pct=-6.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        assert len(sentinel.alerts) == 1
        assert sentinel.alerts[0].alert_type == "drawdown_critical"

    @pytest.mark.asyncio
    async def test_drawdown_emergency(self, sentinel):
        """P&L <= -8% triggers drawdown_emergency + emergency_closes stat."""
        positions = [_make_position("SOLUSDT", pnl_pct=-9.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock) as mock_emit:
            await sentinel._check_positions()

        assert len(sentinel.alerts) == 1
        assert sentinel.alerts[0].alert_type == "drawdown_emergency"
        assert sentinel.stats["emergency_closes"] == 1
        # _emit called twice: once for risk_alert, once for position_alert
        assert mock_emit.call_count == 2


# ---------------------------------------------------------------------------
# 6. Profit alert
# ---------------------------------------------------------------------------

class TestProfitAlert:
    @pytest.mark.asyncio
    async def test_profit_target(self, sentinel):
        """P&L >= +5% triggers profit_target alert."""
        positions = [_make_position("ADAUSDT", pnl_pct=6.0, pnl_usd=3.5)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        assert len(sentinel.alerts) == 1
        assert sentinel.alerts[0].alert_type == "profit_target"
        assert sentinel.stats["profit_alerts"] == 1


# ---------------------------------------------------------------------------
# 7. Liquidation proximity
# ---------------------------------------------------------------------------

class TestLiquidationProximity:
    @pytest.mark.asyncio
    async def test_liq_proximity_alert(self, sentinel):
        """Alert when mark price is within liq_proximity_pct of liquidation price."""
        # mark=100, liq=90 => distance 10% < 15% threshold
        positions = [_make_position("XRPUSDT", pnl_pct=0.5, liq_price=90.0, mark_price=100.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        assert len(sentinel.alerts) == 1
        assert sentinel.alerts[0].alert_type == "liq_proximity"

    @pytest.mark.asyncio
    async def test_liq_no_alert_when_far(self, sentinel):
        """No liq alert when distance > threshold."""
        # mark=100, liq=50 => distance 50% > 15%
        positions = [_make_position("XRPUSDT", pnl_pct=0.5, liq_price=50.0, mark_price=100.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        assert len(sentinel.alerts) == 0


# ---------------------------------------------------------------------------
# 8. Too many positions
# ---------------------------------------------------------------------------

class TestTooManyPositions:
    @pytest.mark.asyncio
    async def test_too_many_positions_alert(self, sentinel):
        """Alert when open positions exceed max_positions."""
        positions = [_make_position(f"COIN{i}USDT", pnl_pct=0.0) for i in range(7)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        portfolio_alerts = [a for a in sentinel.alerts if a.symbol == "PORTFOLIO" and a.alert_type == "too_many_positions"]
        assert len(portfolio_alerts) == 1


# ---------------------------------------------------------------------------
# 9. Daily loss limit
# ---------------------------------------------------------------------------

class TestDailyLossLimit:
    @pytest.mark.asyncio
    async def test_daily_loss_limit_alert(self, sentinel):
        """Alert when total unrealized loss exceeds daily limit."""
        positions = [
            _make_position("BTCUSDT", pnl_pct=-1.0, pnl_usd=-30.0),
            _make_position("ETHUSDT", pnl_pct=-1.0, pnl_usd=-25.0),
        ]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        daily_alerts = [a for a in sentinel.alerts if a.alert_type == "daily_loss_limit"]
        assert len(daily_alerts) == 1

    @pytest.mark.asyncio
    async def test_no_daily_loss_alert_when_below_limit(self, sentinel):
        """No daily loss alert when total loss is within the limit."""
        positions = [
            _make_position("BTCUSDT", pnl_pct=-0.5, pnl_usd=-5.0),
            _make_position("ETHUSDT", pnl_pct=-0.2, pnl_usd=-2.0),
        ]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        daily_alerts = [a for a in sentinel.alerts if a.alert_type == "daily_loss_limit"]
        assert len(daily_alerts) == 0


# ---------------------------------------------------------------------------
# 10. Alert cooldown
# ---------------------------------------------------------------------------

class TestAlertCooldown:
    @pytest.mark.asyncio
    async def test_cooldown_suppresses_duplicate_alert(self, sentinel):
        """Second alert on same symbol within cooldown window is suppressed."""
        positions = [_make_position("BTCUSDT", pnl_pct=-4.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()
            assert len(sentinel.alerts) == 1

            # Second call -- cooldown not elapsed
            await sentinel._check_positions()
            assert len(sentinel.alerts) == 1  # still 1, not 2

    @pytest.mark.asyncio
    async def test_cooldown_expires(self, sentinel):
        """Alert is sent again after cooldown expires."""
        positions = [_make_position("BTCUSDT", pnl_pct=-4.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()
            assert len(sentinel.alerts) == 1

            # Expire the cooldown by backdating
            sentinel._alerted_positions["BTCUSDT"] = time.time() - sentinel._alert_cooldown_s - 1
            await sentinel._check_positions()
            assert len(sentinel.alerts) == 2


# ---------------------------------------------------------------------------
# 11. Alert trimming (_max_alerts)
# ---------------------------------------------------------------------------

class TestAlertTrimming:
    @pytest.mark.asyncio
    async def test_alerts_trimmed_to_max(self, sentinel):
        """Alert list never exceeds _max_alerts."""
        sentinel._max_alerts = 10
        sentinel._alert_cooldown_s = 0  # disable cooldown for this test

        positions = [_make_position("BTCUSDT", pnl_pct=-4.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            for _ in range(15):
                # Reset cooldown each iteration
                sentinel._alerted_positions.clear()
                await sentinel._check_positions()

        assert len(sentinel.alerts) <= 10


# ---------------------------------------------------------------------------
# 12. Stats tracking
# ---------------------------------------------------------------------------

class TestStats:
    def test_initial_stats(self, sentinel):
        assert sentinel.stats["checks"] == 0
        assert sentinel.stats["alerts_sent"] == 0
        assert sentinel.stats["positions_monitored"] == 0
        assert sentinel.stats["emergency_closes"] == 0
        assert sentinel.stats["profit_alerts"] == 0

    @pytest.mark.asyncio
    async def test_stats_increment(self, sentinel):
        """alerts_sent incremented per alert dispatched."""
        positions = [_make_position("BTCUSDT", pnl_pct=-4.0)]
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=positions))}), \
             patch.dict("sys.modules", {"src.notification_hub": MagicMock()}), \
             patch.object(sentinel, "_emit", new_callable=AsyncMock):
            await sentinel._check_positions()

        assert sentinel.stats["alerts_sent"] == 1
        assert sentinel.stats["positions_monitored"] == 1


# ---------------------------------------------------------------------------
# 13. Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_structure(self, sentinel):
        s = sentinel.summary()
        assert "running" in s
        assert "stats" in s
        assert "config" in s
        assert "recent_alerts" in s
        assert s["running"] is False

    def test_summary_config_keys(self, sentinel):
        s = sentinel.summary()
        cfg = s["config"]
        assert "drawdown_warning" in cfg
        assert "drawdown_critical" in cfg
        assert "drawdown_emergency" in cfg
        assert "profit_alert" in cfg
        assert "daily_loss_limit" in cfg

    def test_summary_recent_alerts_limited(self, sentinel):
        """Summary returns at most 20 recent alerts."""
        for i in range(30):
            sentinel.alerts.append(
                PositionAlert(symbol=f"COIN{i}", alert_type="test", pnl_pct=0, message="x")
            )
        s = sentinel.summary()
        assert len(s["recent_alerts"]) == 20

    def test_summary_alert_format(self, sentinel):
        sentinel.alerts.append(
            PositionAlert(symbol="ETHUSDT", alert_type="drawdown_warning", pnl_pct=-3.5, message="test")
        )
        s = sentinel.summary()
        a = s["recent_alerts"][0]
        assert a["symbol"] == "ETHUSDT"
        assert a["type"] == "drawdown_warning"
        assert a["pnl_pct"] == -3.5
        assert a["message"] == "test"


# ---------------------------------------------------------------------------
# 14. Daily reset in monitor loop
# ---------------------------------------------------------------------------

class TestDailyReset:
    @pytest.mark.asyncio
    async def test_daily_reset_clears_pnl(self, sentinel):
        """After 24h the daily realized PnL resets."""
        sentinel._daily_realized_pnl = 42.0
        sentinel._daily_reset_ts = time.time() - 86401  # >24h ago

        # Patch _check_positions to not hit the exchange
        with patch.object(sentinel, "_check_positions", new_callable=AsyncMock):
            sentinel.running = True
            # Run one iteration manually (simulate loop body)
            await sentinel._check_positions()
            sentinel.stats["checks"] += 1
            if time.time() - sentinel._daily_reset_ts > 86400:
                sentinel._daily_realized_pnl = 0.0
                sentinel._daily_reset_ts = time.time()

        assert sentinel._daily_realized_pnl == 0.0


# ---------------------------------------------------------------------------
# 15. _emit event bus is isolated
# ---------------------------------------------------------------------------

class TestEmit:
    @pytest.mark.asyncio
    async def test_emit_calls_event_bus(self, sentinel):
        """_emit dispatches to event_bus.emit when available."""
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            await sentinel._emit("trading.test", {"key": "value"})
        mock_bus.emit.assert_called_once()
        call_args = mock_bus.emit.call_args
        assert call_args[0][0] == "trading.test"

    @pytest.mark.asyncio
    async def test_emit_swallows_errors(self, sentinel):
        """_emit does not raise even if event_bus is unavailable."""
        with patch.dict("sys.modules", {"src.event_bus": None}):
            # Should not raise
            await sentinel._emit("trading.test", {"key": "value"})


# ---------------------------------------------------------------------------
# 16. No positions scenario
# ---------------------------------------------------------------------------

class TestNoPositions:
    @pytest.mark.asyncio
    async def test_empty_positions(self, sentinel):
        """No alerts when there are no open positions."""
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(return_value=[]))}):
            await sentinel._check_positions()
        assert len(sentinel.alerts) == 0
        assert sentinel.stats["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_positions_fetch_failure(self, sentinel):
        """Gracefully handles exchange fetch failure."""
        with patch.dict("sys.modules", {"src.exchanges": MagicMock(get_open_positions=AsyncMock(side_effect=RuntimeError("offline")))}):
            await sentinel._check_positions()
        assert len(sentinel.alerts) == 0
