"""Tests for src/exchanges.py — UnifiedExchange, ExchangeConfig, multi-exchange helpers.

All external dependencies (ccxt, network) are fully mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# 1. Import smoke tests
# ---------------------------------------------------------------------------


class TestImports:
    """Verify that all public symbols can be imported."""

    def test_import_exchange_config(self):
        from src.exchanges import ExchangeConfig
        assert ExchangeConfig is not None

    def test_import_unified_exchange(self):
        from src.exchanges import UnifiedExchange
        assert UnifiedExchange is not None

    def test_import_exchange_configs_registry(self):
        from src.exchanges import EXCHANGE_CONFIGS
        assert isinstance(EXCHANGE_CONFIGS, dict)

    def test_import_helper_functions(self):
        from src.exchanges import get_enabled_exchanges, get_best_price, get_all_positions
        assert callable(get_enabled_exchanges)
        assert callable(get_best_price)
        assert callable(get_all_positions)


# ---------------------------------------------------------------------------
# 2. ExchangeConfig dataclass
# ---------------------------------------------------------------------------


class TestExchangeConfig:
    """Tests for the ExchangeConfig dataclass."""

    def test_defaults(self):
        from src.exchanges import ExchangeConfig
        cfg = ExchangeConfig(name="test_ex")
        assert cfg.name == "test_ex"
        assert cfg.api_key == ""
        assert cfg.secret_key == ""
        assert cfg.passphrase == ""
        assert cfg.testnet is False
        assert cfg.leverage == 10
        assert cfg.tp_percent == 0.4
        assert cfg.sl_percent == 0.25
        assert cfg.size_usdt == 10.0
        assert cfg.enabled is True

    def test_custom_values(self):
        from src.exchanges import ExchangeConfig
        cfg = ExchangeConfig(
            name="binance",
            api_key="key123",
            secret_key="sec456",
            passphrase="pass789",
            testnet=True,
            leverage=20,
            tp_percent=1.0,
            sl_percent=0.5,
            size_usdt=50.0,
            enabled=False,
        )
        assert cfg.name == "binance"
        assert cfg.api_key == "key123"
        assert cfg.secret_key == "sec456"
        assert cfg.passphrase == "pass789"
        assert cfg.testnet is True
        assert cfg.leverage == 20
        assert cfg.tp_percent == 1.0
        assert cfg.sl_percent == 0.5
        assert cfg.size_usdt == 50.0
        assert cfg.enabled is False


# ---------------------------------------------------------------------------
# 3. EXCHANGE_CONFIGS registry
# ---------------------------------------------------------------------------


class TestExchangeRegistry:
    """Tests for the global EXCHANGE_CONFIGS dict."""

    def test_contains_mexc(self):
        from src.exchanges import EXCHANGE_CONFIGS
        assert "mexc" in EXCHANGE_CONFIGS
        assert EXCHANGE_CONFIGS["mexc"].name == "mexc"

    def test_contains_binance(self):
        from src.exchanges import EXCHANGE_CONFIGS
        assert "binance" in EXCHANGE_CONFIGS
        assert EXCHANGE_CONFIGS["binance"].name == "binance"

    def test_contains_bybit(self):
        from src.exchanges import EXCHANGE_CONFIGS
        assert "bybit" in EXCHANGE_CONFIGS
        assert EXCHANGE_CONFIGS["bybit"].name == "bybit"

    def test_mexc_enabled_by_default(self):
        from src.exchanges import EXCHANGE_CONFIGS
        assert EXCHANGE_CONFIGS["mexc"].enabled is True


# ---------------------------------------------------------------------------
# 4. UnifiedExchange — initialization
# ---------------------------------------------------------------------------


class TestUnifiedExchangeInit:
    """Tests for UnifiedExchange constructor and lazy init."""

    def test_valid_exchange_name(self):
        from src.exchanges import UnifiedExchange
        ex = UnifiedExchange("mexc")
        assert ex.name == "mexc"
        assert ex.config is not None
        assert ex._exchange is None  # lazy, not yet created

    def test_unknown_exchange_raises(self):
        from src.exchanges import UnifiedExchange
        with pytest.raises(ValueError, match="Unknown exchange"):
            UnifiedExchange("nonexistent_exchange")

    @patch("src.exchanges.EXCHANGE_CONFIGS", {
        "fake": MagicMock(
            name="fake", api_key="k", secret_key="s", passphrase="", testnet=False
        ),
    })
    def test_get_exchange_ccxt_not_supported(self):
        """If ccxt does not have the exchange class, raise ValueError."""
        from src.exchanges import UnifiedExchange
        mock_ccxt = MagicMock()
        mock_ccxt.fake = None  # getattr returns None
        del mock_ccxt.fake  # make getattr return default None
        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            ex = UnifiedExchange("fake")
            with pytest.raises(ValueError, match="ccxt does not support"):
                ex._get_exchange()

    @patch("src.exchanges.EXCHANGE_CONFIGS", {
        "fake": MagicMock(
            api_key="k", secret_key="s", passphrase="pw", testnet=True
        ),
    })
    def test_get_exchange_with_passphrase_and_testnet(self):
        """Passphrase and testnet flags propagate to ccxt options."""
        from src.exchanges import UnifiedExchange

        mock_exchange_cls = MagicMock(return_value=MagicMock())
        mock_ccxt = MagicMock()
        mock_ccxt.fake = mock_exchange_cls

        with patch.dict("sys.modules", {"ccxt": mock_ccxt}):
            ex = UnifiedExchange("fake")
            result = ex._get_exchange()

            call_args = mock_exchange_cls.call_args[0][0]
            assert call_args["password"] == "pw"
            assert call_args["sandbox"] is True
            assert call_args["enableRateLimit"] is True
            assert result is not None


# ---------------------------------------------------------------------------
# 5. UnifiedExchange — API wrappers (all ccxt calls mocked)
# ---------------------------------------------------------------------------


def _make_exchange(name: str = "mexc") -> "UnifiedExchange":
    """Helper: create a UnifiedExchange with a pre-injected mock ccxt instance."""
    from src.exchanges import UnifiedExchange
    ex = UnifiedExchange(name)
    ex._exchange = MagicMock()
    return ex


class TestGetBalance:
    def test_returns_usdt_balance(self):
        ex = _make_exchange()
        ex._exchange.fetch_balance.return_value = {
            "USDT": {"total": 500.0, "free": 400.0, "used": 100.0},
        }
        result = ex.get_balance()
        assert result["exchange"] == "mexc"
        assert result["total"] == 500.0
        assert result["free"] == 400.0
        assert result["used"] == 100.0

    def test_missing_usdt_returns_zeros(self):
        ex = _make_exchange()
        ex._exchange.fetch_balance.return_value = {}
        result = ex.get_balance()
        assert result["total"] == 0
        assert result["free"] == 0
        assert result["used"] == 0


class TestGetPositions:
    def test_returns_active_positions(self):
        ex = _make_exchange()
        ex._exchange.fetch_positions.return_value = [
            {
                "symbol": "BTC/USDT:USDT",
                "side": "long",
                "contracts": 0.001,
                "entryPrice": 60000.0,
                "markPrice": 61000.0,
                "unrealizedPnl": 1.0,
                "leverage": 10,
                "initialMargin": 6.0,
            },
            {
                "symbol": "ETH/USDT:USDT",
                "side": "short",
                "contracts": 0,  # inactive — should be filtered
                "entryPrice": 3000.0,
                "markPrice": 3100.0,
                "unrealizedPnl": -0.5,
                "leverage": 10,
                "initialMargin": 3.0,
            },
        ]
        positions = ex.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "BTC/USDT:USDT"
        assert positions[0]["pnl"] == 1.0

    def test_no_positions_returns_empty(self):
        ex = _make_exchange()
        ex._exchange.fetch_positions.return_value = []
        assert ex.get_positions() == []


class TestGetTicker:
    def test_returns_ticker_data(self):
        ex = _make_exchange()
        ex._exchange.fetch_ticker.return_value = {
            "last": 60000.0,
            "bid": 59999.0,
            "ask": 60001.0,
            "baseVolume": 1234.5,
            "percentage": 2.3,
        }
        result = ex.get_ticker("BTC/USDT:USDT")
        assert result["exchange"] == "mexc"
        assert result["symbol"] == "BTC/USDT:USDT"
        assert result["last"] == 60000.0
        assert result["bid"] == 59999.0
        assert result["ask"] == 60001.0
        assert result["volume"] == 1234.5
        assert result["change_24h"] == 2.3

    def test_missing_percentage_defaults_zero(self):
        ex = _make_exchange()
        ex._exchange.fetch_ticker.return_value = {
            "last": 100.0,
            "bid": 99.0,
            "ask": 101.0,
            "baseVolume": 10.0,
        }
        result = ex.get_ticker("SOL/USDT:USDT")
        assert result["change_24h"] == 0


# ---------------------------------------------------------------------------
# 6. place_order (dry run and live)
# ---------------------------------------------------------------------------


class TestPlaceOrder:
    def _setup_exchange(self, price: float = 50000.0):
        ex = _make_exchange()
        ex._exchange.fetch_ticker.return_value = {"last": price}
        return ex

    def test_dry_run_long(self):
        ex = self._setup_exchange(price=50000.0)
        result = ex.place_order("BTC/USDT:USDT", "long", size_usdt=10.0, dry_run=True)
        assert result["dry_run"] is True
        assert result["status"] == "simulated"
        assert result["side"] == "long"
        assert result["order_side"] == "buy"
        assert result["price"] == 50000.0
        assert result["quantity"] == pytest.approx(10.0 / 50000.0)
        assert result["tp_price"] > result["price"]
        assert result["sl_price"] < result["price"]
        # ccxt should NOT be called for market order
        ex._exchange.create_market_order.assert_not_called()

    def test_dry_run_short(self):
        ex = self._setup_exchange(price=2000.0)
        result = ex.place_order("ETH/USDT:USDT", "short", size_usdt=20.0, dry_run=True)
        assert result["order_side"] == "sell"
        assert result["tp_price"] < result["price"]
        assert result["sl_price"] > result["price"]

    def test_live_order_success(self):
        ex = self._setup_exchange(price=100.0)
        ex._exchange.create_market_order.return_value = {"id": "ord123", "status": "filled"}
        ex._exchange.create_order.return_value = {}

        result = ex.place_order("SOL/USDT:USDT", "long", size_usdt=10.0, dry_run=False)
        assert result["dry_run"] is False
        assert result["order_id"] == "ord123"
        assert result["status"] == "filled"
        assert result["tp_placed"] is True
        assert result["sl_placed"] is True
        ex._exchange.set_leverage.assert_called_once()
        ex._exchange.create_market_order.assert_called_once()
        assert ex._exchange.create_order.call_count == 2  # TP + SL

    def test_live_order_tp_fails(self):
        ex = self._setup_exchange(price=100.0)
        ex._exchange.create_market_order.return_value = {"id": "o1", "status": "filled"}
        # First create_order (TP) fails, second (SL) succeeds
        ex._exchange.create_order.side_effect = [Exception("TP error"), MagicMock()]
        result = ex.place_order("SOL/USDT:USDT", "long", dry_run=False)
        assert result["tp_placed"] is False
        assert "TP error" in result["tp_error"]
        assert result["sl_placed"] is True

    def test_live_order_sl_fails(self):
        ex = self._setup_exchange(price=100.0)
        ex._exchange.create_market_order.return_value = {"id": "o2", "status": "filled"}
        # First create_order (TP) succeeds, second (SL) fails
        ex._exchange.create_order.side_effect = [MagicMock(), Exception("SL error")]
        result = ex.place_order("SOL/USDT:USDT", "short", dry_run=False)
        assert result["tp_placed"] is True
        assert result["sl_placed"] is False
        assert "SL error" in result["sl_error"]

    def test_leverage_failure_does_not_block_order(self):
        ex = self._setup_exchange(price=100.0)
        ex._exchange.set_leverage.side_effect = Exception("leverage unsupported")
        ex._exchange.create_market_order.return_value = {"id": "o3", "status": "filled"}
        ex._exchange.create_order.return_value = {}
        # Should still place the order despite leverage failure
        result = ex.place_order("SOL/USDT:USDT", "long", dry_run=False)
        assert result["status"] == "filled"

    def test_uses_config_defaults_when_none(self):
        ex = self._setup_exchange(price=200.0)
        result = ex.place_order("X/USDT:USDT", "long", dry_run=True)
        # Should use config defaults: size_usdt=10, leverage=10, tp=0.4, sl=0.25
        assert result["size_usdt"] == 10.0
        assert result["leverage"] == 10


# ---------------------------------------------------------------------------
# 7. close_position
# ---------------------------------------------------------------------------


class TestClosePosition:
    def test_close_long_position(self):
        ex = _make_exchange()
        ex._exchange.fetch_positions.return_value = [
            {"side": "long", "contracts": 0.5, "unrealizedPnl": 12.0},
        ]
        ex._exchange.create_market_order.return_value = {"id": "close1"}
        result = ex.close_position("BTC/USDT:USDT")
        assert result["status"] == "closed"
        assert result["order_id"] == "close1"
        assert result["pnl"] == 12.0
        # Long position should be closed with sell
        ex._exchange.create_market_order.assert_called_once_with(
            "BTC/USDT:USDT", "sell", 0.5, params={"reduceOnly": True}
        )

    def test_close_short_position(self):
        ex = _make_exchange()
        ex._exchange.fetch_positions.return_value = [
            {"side": "short", "contracts": 1.0, "unrealizedPnl": -5.0},
        ]
        ex._exchange.create_market_order.return_value = {"id": "close2"}
        result = ex.close_position("ETH/USDT:USDT")
        assert result["status"] == "closed"
        # Short position should be closed with buy
        ex._exchange.create_market_order.assert_called_once_with(
            "ETH/USDT:USDT", "buy", 1.0, params={"reduceOnly": True}
        )

    def test_no_position_returns_no_position(self):
        ex = _make_exchange()
        ex._exchange.fetch_positions.return_value = []
        result = ex.close_position("BTC/USDT:USDT")
        assert result["status"] == "no_position"
        ex._exchange.create_market_order.assert_not_called()

    def test_inactive_positions_filtered(self):
        ex = _make_exchange()
        ex._exchange.fetch_positions.return_value = [
            {"side": "long", "contracts": 0, "unrealizedPnl": 0},
        ]
        result = ex.close_position("BTC/USDT:USDT")
        assert result["status"] == "no_position"


# ---------------------------------------------------------------------------
# 8. Multi-exchange helpers
# ---------------------------------------------------------------------------


class TestMultiExchangeHelpers:
    @patch("src.exchanges.EXCHANGE_CONFIGS", {
        "ex_a": MagicMock(enabled=True, api_key="key_a"),
        "ex_b": MagicMock(enabled=False, api_key="key_b"),
        "ex_c": MagicMock(enabled=True, api_key=""),
    })
    def test_get_enabled_exchanges(self):
        from src.exchanges import get_enabled_exchanges
        result = get_enabled_exchanges()
        assert "ex_a" in result
        assert "ex_b" not in result  # disabled
        assert "ex_c" not in result  # no api key

    @patch("src.exchanges.get_enabled_exchanges", return_value=["mexc"])
    @patch("src.exchanges.UnifiedExchange")
    def test_get_best_price(self, MockUE, mock_enabled):
        from src.exchanges import get_best_price
        instance = MockUE.return_value
        instance.get_ticker.return_value = {
            "exchange": "mexc", "symbol": "BTC/USDT:USDT",
            "last": 60000.0, "bid": 59999.0, "ask": 60001.0,
            "volume": 100.0, "change_24h": 1.0,
        }
        result = get_best_price("BTC/USDT:USDT")
        assert result["last"] == 60000.0
        assert result["exchange"] == "mexc"

    @patch("src.exchanges.get_enabled_exchanges", return_value=["mexc"])
    @patch("src.exchanges.UnifiedExchange")
    def test_get_best_price_picks_lowest(self, MockUE, mock_enabled):
        """When multiple exchanges, pick the one with lowest price."""
        from src.exchanges import get_best_price
        mock_enabled.return_value = ["ex1", "ex2"]
        call_count = [0]

        def make_instance(name):
            m = MagicMock()
            prices = {"ex1": 60000.0, "ex2": 59000.0}
            m.get_ticker.return_value = {
                "exchange": name, "symbol": "BTC/USDT:USDT",
                "last": prices.get(name, 99999), "bid": 0, "ask": 0,
                "volume": 0, "change_24h": 0,
            }
            return m

        MockUE.side_effect = make_instance
        result = get_best_price("BTC/USDT:USDT")
        assert result["last"] == 59000.0

    @patch("src.exchanges.get_enabled_exchanges", return_value=[])
    def test_get_best_price_no_exchange(self, mock_enabled):
        from src.exchanges import get_best_price
        result = get_best_price("BTC/USDT:USDT")
        assert "error" in result

    @patch("src.exchanges.get_enabled_exchanges", return_value=["mexc"])
    @patch("src.exchanges.UnifiedExchange")
    def test_get_best_price_exchange_error(self, MockUE, mock_enabled):
        from src.exchanges import get_best_price
        MockUE.return_value.get_ticker.side_effect = Exception("network")
        result = get_best_price("BTC/USDT:USDT")
        assert "error" in result

    @patch("src.exchanges.get_enabled_exchanges", return_value=["mexc"])
    @patch("src.exchanges.UnifiedExchange")
    def test_get_all_positions(self, MockUE, mock_enabled):
        from src.exchanges import get_all_positions
        MockUE.return_value.get_positions.return_value = [
            {"exchange": "mexc", "symbol": "BTC/USDT:USDT", "side": "long"},
        ]
        result = get_all_positions()
        assert len(result) == 1
        assert result[0]["symbol"] == "BTC/USDT:USDT"

    @patch("src.exchanges.get_enabled_exchanges", return_value=["mexc"])
    @patch("src.exchanges.UnifiedExchange")
    def test_get_all_positions_exchange_error(self, MockUE, mock_enabled):
        from src.exchanges import get_all_positions
        MockUE.return_value.get_positions.side_effect = Exception("fail")
        result = get_all_positions()
        assert result == []


# ---------------------------------------------------------------------------
# 9. Edge cases — TP/SL price calculations
# ---------------------------------------------------------------------------


class TestPriceCalculations:
    def test_long_tp_sl_math(self):
        ex = _make_exchange()
        ex._exchange.fetch_ticker.return_value = {"last": 10000.0}
        result = ex.place_order("X/USDT:USDT", "long", tp_percent=1.0, sl_percent=0.5, dry_run=True)
        assert result["tp_price"] == pytest.approx(10100.0)  # +1%
        assert result["sl_price"] == pytest.approx(9950.0)   # -0.5%

    def test_short_tp_sl_math(self):
        ex = _make_exchange()
        ex._exchange.fetch_ticker.return_value = {"last": 10000.0}
        result = ex.place_order("X/USDT:USDT", "short", tp_percent=1.0, sl_percent=0.5, dry_run=True)
        assert result["tp_price"] == pytest.approx(9900.0)   # -1%
        assert result["sl_price"] == pytest.approx(10050.0)  # +0.5%
